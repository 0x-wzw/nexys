#!/usr/bin/env python3
"""
Demo: Standalone Platform with Multiple MoA-Enabled Agents
===========================================================

Shows how to:
1. Create a platform service (MoAEnabledAgentService)
2. Spawn multiple agents, each with its own MoA configuration
3. Dispatch a task to each agent in parallel
4. Each agent runs its own MoA pipeline (local or cloud)
5. Results converge into a single synthesized answer

Usage:
    python test_moa_platform.py

Requires:
    - Ollama running locally (for local-mode agents)
    - OLLAMA_API_KEY set in ~/.hermes/.env (for cloud-mode agents)
    - local_moa.py in ~/.hermes/skills/local-mixture-of-agents/scripts/
"""

import asyncio
import json
import os
import sys

# Path setup
sys.path.insert(0, "/home/ubuntu/nexys")
sys.path.insert(0, os.path.expanduser("~/.hermes/skills/local-mixture-of-agents/scripts"))

from unified_platform.adapters.moa_enabled_agent import MoAEnabledAgentService, spawn_agent
from unified_platform.interfaces import Task, AgentConfig, ResourceLimit, CoordinationStrategy


async def main():
    print("=" * 60)
    print("STANDALONE MoA PLATFORM DEMO")
    print("=" * 60)

    # ── 1. Create platform service ──────────────────────────────
    print("\n[1] Creating MoAEnabledAgentService...")
    platform = MoAEnabledAgentService()

    # ── 2. Spawn agents with different MoA profiles ────────────
    print("\n[2] Spawning 3 agents with distinct MoA configs...")

    # Agent Alpha: local, code-focused, cost-conscious
    await platform.create_agent(AgentConfig(
        id="alpha",
        name="Code Agent Alpha",
        capabilities=["code", "moa"],
        resources=ResourceLimit(token_limit=200000, memory_mb=1024, timeout_seconds=600),
        metadata={
            "type": "code",
            "moa_mode": "local",
            "moa_refs": ["qwen2.5", "llama3.3"],
            "moa_agg": "llama3.3",
            "moa_concurrency": 2,
            "moa_budget": "cost_first",
        },
    ))
    print("   ✓ Agent Alpha (local, code, cost-first)")

    # Agent Beta: cloud, research-focused, quality-first
    await platform.create_agent(AgentConfig(
        id="beta",
        name="Research Agent Beta",
        capabilities=["research", "moa"],
        resources=ResourceLimit(token_limit=200000, memory_mb=1024, timeout_seconds=600),
        metadata={
            "type": "research",
            "moa_mode": "cloud",
            "moa_refs": ["kimi-k2.6", "gemma4:31b"],
            "moa_agg": "kimi-k2.6",
            "moa_concurrency": 4,
            "moa_budget": "quality_first",
        },
    ))
    print("   ✓ Agent Beta (cloud, research, quality-first)")

    # Agent Gamma: local, analysis-focused, balanced
    await platform.create_agent(AgentConfig(
        id="gamma",
        name="Analysis Agent Gamma",
        capabilities=["analysis", "moa"],
        resources=ResourceLimit(token_limit=200000, memory_mb=1024, timeout_seconds=600),
        metadata={
            "type": "analysis",
            "moa_mode": "local",
            "moa_refs": ["mistral", "phi4"],
            "moa_agg": "mistral",
            "moa_concurrency": 2,
            "moa_budget": "balanced",
        },
    ))
    print("   ✓ Agent Gamma (local, analysis, balanced)")

    # ── 3. Define the task ───────────────────────────────────────
    print("\n[3] Defining shared task...")
    task = Task(
        id="demo-task-001",
        objective="Explain the trade-offs between REST and GraphQL APIs for high-scale microservices",
        context={"domain": "software architecture", "audience": "senior engineers"},
        constraints={"length": "concise", "depth": "technical"},
    )
    print(f"   Task: {task.objective}")

    # ── 4. Dispatch in parallel ────────────────────────────────
    print("\n[4] Dispatching to all agents in parallel...")
    agent_ids = ["alpha", "beta", "gamma"]
    results = await asyncio.gather(*[
        platform.dispatch_task(aid, task)
        for aid in agent_ids
    ])

    print("\n[5] Results per agent:")
    for aid, result in zip(agent_ids, results):
        status = "✅ SUCCESS" if result.success else "❌ FAILED"
        print(f"\n   {aid.upper()}: {status}")
        if result.success:
            preview = result.output[:300].replace("\n", " ")
            print(f"      Preview: {preview}...")
        else:
            print(f"      Error: {result.error}")

    # ── 5. Coordinate / Converge ───────────────────────────────
    print("\n[6] Running CONVERGENCE across all outputs...")
    coord = await platform.coordinate(
        agent_ids=agent_ids,
        strategy=CoordinationStrategy.CONSENSUS,
        objective=task.objective,
    )

    print(f"\n   Consensus: {'✅ YES' if coord.consensus else '❌ NO'}")
    print(f"   Confidence: {coord.confidence:.0%}")
    print(f"   Dissenters: {coord.dissenters or 'None'}")
    print(f"\n   Converged output (first 500 chars):")
    print(f"   {coord.decision[:500]}...")

    # ── 6. Cleanup ────────────────────────────────────────────
    print("\n[7] Terminating agents...")
    for aid in agent_ids:
        await platform.terminate_agent(aid)
    print("   All agents terminated.")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
