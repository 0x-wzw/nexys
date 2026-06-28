"""
MoAEnabledAgentService Adapter
================================

Implements IAgentService for the Nexys Unified Platform.
Manages a pool of agents where each agent runs its own MoA configuration.

Key capability: multiple agents, each with their own MoA pipeline,
coordinate to complete a single task.
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Add local-mixture-of-agents to path (adjust if installed elsewhere)
MOA_PATH = os.path.expanduser("~/.hermes/skills/local-mixture-of-agents/scripts")
if MOA_PATH not in sys.path:
    sys.path.insert(0, MOA_PATH)

# Nexys unified platform interfaces
from unified_platform.interfaces import (
    AgentConfig, AgentStatus, CoordinationResult, CoordinationStrategy,
    IAgentService, Agent, Task, TaskResult, ResourceLimit
)

logger = logging.getLogger("moa_agent_service")


# ── Data structures ────────────────────────────────────────────────────────

@dataclass
class MoAProfile:
    """Per-agent MoA configuration"""
    mode: str = "local"                       # "local" | "cloud"
    reference_models: List[str] = field(default_factory=list)
    aggregator_model: Optional[str] = None
    max_concurrency: int = 4
    use_k2_routing: bool = False
    task_type: str = "analysis"
    budget: str = "balanced"
    ref_max_tokens: int = 8000
    agg_max_tokens: int = 16000
    enable_boundary: bool = True


# ── MoA Agent Instance ─────────────────────────────────────────────────────

class MoAEnabledAgent:
    """
    A single agent that carries its own MoA engine.
    Not a Protocol — a concrete instance managed by MoAEnabledAgentService.
    """

    def __init__(self, config: AgentConfig, profile: MoAProfile):
        self.config = config
        self.profile = profile
        self.status = AgentStatus.IDLE
        self.memory: List[Dict[str, Any]] = []

    async def execute(self, task: Task) -> TaskResult:
        """Run task through this agent's MoA pipeline"""
        start = time.time()

        # Build ENVELOPE
        envelope = self._build_envelope(task)
        logger.info("[%s] ENVELOPE: task=%s mode=%s", self.config.id, task.id, self.profile.mode)

        # Set execution environment
        os.environ["MOA_MODE"] = self.profile.mode
        if self.profile.mode == "cloud":
            os.environ["MOA_REF_MAX_TOKENS"] = str(self.profile.ref_max_tokens)
            os.environ["MOA_AGG_MAX_TOKENS"] = str(self.profile.agg_max_tokens)

        # Import MoA engine (late, after env vars set)
        try:
            from local_moa import mixture_of_agents_local
        except ImportError:
            return TaskResult(
                task_id=task.id,
                success=False,
                output="",
                error="local_moa not found. Check that ~/.hermes/skills/local-mixture-of-agents/scripts is on PYTHONPATH",
            )

        # Run MoA
        try:
            moa_result = await mixture_of_agents_local(
                user_prompt=envelope["prompt"],
                reference_models=self.profile.reference_models or None,
                aggregator_model=self.profile.aggregator_model,
                max_concurrency=self.profile.max_concurrency,
                use_k2_routing=self.profile.use_k2_routing,
                task_type=self.profile.task_type,
                budget=self.profile.budget,
            )
        except Exception as e:
            logger.error("[%s] MoA failed: %s", self.config.id, e)
            return TaskResult(task_id=task.id, success=False, output="", error=str(e))

        # BOUNDARY check
        if self.profile.enable_boundary:
            ok, notes = self._boundary_check(moa_result)
            if not ok:
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    output=moa_result.get("response", ""),
                    error=f"BOUNDARY: {notes}",
                )

        # Store trace
        self.memory.append({"task_id": task.id, "envelope": envelope, "result": moa_result})

        elapsed = round(time.time() - start, 2)
        logger.info("[%s] Done in %.2fs — ref_count=%d success=%s",
                    self.config.id, elapsed,
                    moa_result.get("reference_count", 0),
                    moa_result.get("success"))

        return TaskResult(
            task_id=task.id,
            success=moa_result.get("success", False),
            output=moa_result.get("response", ""),
            error=moa_result.get("error"),
        )

    # ── Helpers ─────────────────────────────────────────────────────────

    def _build_envelope(self, task: Task) -> Dict[str, Any]:
        prompt_parts = [f"Task: {task.objective}"]
        if task.context:
            prompt_parts.append(f"Context: {json.dumps(task.context)}")
        if task.constraints:
            prompt_parts.append(f"Constraints: {json.dumps(task.constraints)}")
        return {
            "agent_id": self.config.id,
            "agent_type": self.config.metadata.get("type", "general"),
            "task_id": task.id,
            "prompt": "\n\n".join(prompt_parts),
        }

    def _boundary_check(self, moa_result: Dict) -> tuple[bool, str]:
        resp = moa_result.get("response", "")
        checks = [
            ("non_empty", len(resp.strip()) > 0),
            ("no_error", not resp.startswith("[ERROR")),
            ("min_len", len(resp) > 100),
        ]
        failed = [n for n, ok in checks if not ok]
        if failed:
            return False, f"failed: {', '.join(failed)}"
        return True, "ok"


# ── Service Implementation ────────────────────────────────────────────────

class MoAEnabledAgentService(IAgentService):
    """
    Manages a pool of MoA-enabled agents.
    Each agent has its own MoA profile (local/cloud, models, concurrency).
    """

    def __init__(self):
        self._agents: Dict[str, MoAEnabledAgent] = {}
        self._lock = asyncio.Lock()

    async def create_agent(self, config: AgentConfig) -> Agent:
        """Spawn a new MoA-enabled agent"""
        profile = MoAProfile(
            mode=config.metadata.get("moa_mode", "local"),
            reference_models=config.metadata.get("moa_refs", []),
            aggregator_model=config.metadata.get("moa_agg"),
            max_concurrency=config.metadata.get("moa_concurrency", 4),
            task_type=config.metadata.get("type", "analysis"),
            budget=config.metadata.get("moa_budget", "balanced"),
        )
        agent = MoAEnabledAgent(config, profile)
        async with self._lock:
            self._agents[config.id] = agent
        return Agent(id=config.id, adapter=self, native_instance=agent)

    async def dispatch_task(self, agent_id: str, task: Task) -> TaskResult:
        """Send task to a specific agent; agent runs its own MoA"""
        async with self._lock:
            agent = self._agents.get(agent_id)
        if not agent:
            return TaskResult(task_id=task.id, success=False, output="", error=f"Agent {agent_id} not found")
        agent.status = AgentStatus.BUSY
        try:
            result = await agent.execute(task)
        finally:
            agent.status = AgentStatus.IDLE
        return result

    async def get_agent_status(self, agent_id: str) -> AgentStatus:
        async with self._lock:
            agent = self._agents.get(agent_id)
        return agent.status if agent else AgentStatus.OFFLINE

    async def terminate_agent(self, agent_id: str) -> None:
        async with self._lock:
            self._agents.pop(agent_id, None)
        logger.info("Terminated agent %s", agent_id)

    async def coordinate(
        self,
        agent_ids: List[str],
        strategy: CoordinationStrategy,
        objective: str
    ) -> CoordinationResult:
        """
        Coordinate multiple agents on a shared objective.
        Each agent runs its own MoA; results are merged via CONVERGENCE.
        """
        # Build a task for each agent
        tasks = [
            Task(
                id=str(uuid.uuid4()),
                objective=objective,
                context={"agent_id": aid, "strategy": strategy.value},
                constraints={},
            )
            for aid in agent_ids
        ]

        # Dispatch in parallel
        coros = [self.dispatch_task(aid, t) for aid, t in zip(agent_ids, tasks)]
        results: List[TaskResult] = await asyncio.gather(*coros)

        # CONVERGENCE: synthesize outputs
        outputs = [r.output for r in results if r.success]
        merged = self._converge(outputs, objective)

        return CoordinationResult(
            consensus=len(outputs) >= len(agent_ids) // 2 + 1,
            decision=merged,
            votes={aid: r.success for aid, r in zip(agent_ids, results)},
            confidence=len(outputs) / len(agent_ids) if agent_ids else 0.0,
            dissenters=[aid for aid, r in zip(agent_ids, results) if not r.success],
        )

    async def list_agents(self) -> List[Agent]:
        async with self._lock:
            return [
                Agent(id=aid, adapter=self, native_instance=ag)
                for aid, ag in self._agents.items()
            ]

    # ── CONVERGENCE helper ──────────────────────────────────────────────

    def _converge(self, outputs: List[str], objective: str) -> str:
        """Merge multiple agent outputs into one coherent answer"""
        if not outputs:
            return "No successful outputs to converge."
        if len(outputs) == 1:
            return outputs[0]

        # Simple text-based convergence (production: call aggregator model)
        merged = f"# Converged Analysis: {objective}\n\n"
        for i, out in enumerate(outputs, 1):
            merged += f"## Perspective {i}\n{out[:2000]}\n\n"
        merged += "## Synthesis\n"
        merged += "Multiple agents independently analyzed this problem. "
        merged += "Key themes and consensus points have been integrated above."
        return merged


# ── Convenience factory ──────────────────────────────────────────────────

def spawn_agent(
    service: MoAEnabledAgentService,
    agent_id: str,
    agent_type: str,
    mode: str = "local",
    **moa_overrides
) -> Agent:
    """
    Spawn an agent with a specific MoA configuration.

    Examples:
        # Code specialist — local, cost-conscious
        spawn_agent(svc, "alpha", "code", mode="local",
                    moa_refs=["qwen2.5", "llama3.3"],
                    moa_agg="llama3.3", moa_concurrency=2)

        # Research specialist — cloud, quality-first
        spawn_agent(svc, "beta", "research", mode="cloud",
                    moa_refs=["kimi-k2.6", "gemma4:31b"],
                    moa_agg="kimi-k2.6")
    """
    metadata = {
        "type": agent_type,
        "moa_mode": mode,
        **moa_overrides,
    }
    config = AgentConfig(
        id=agent_id,
        name=f"{agent_type.capitalize()} Agent {agent_id}",
        capabilities=[agent_type, "moa", "synthesis"],
        resources=ResourceLimit(token_limit=200000, memory_mb=1024, timeout_seconds=600),
        metadata=metadata,
    )
    return asyncio.get_event_loop().run_until_complete(service.create_agent(config))
