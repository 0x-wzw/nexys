"""
NeuroWeaver — The NeuroSwarm Adapter

Weaves Brain + Swarm dual-phase architecture into unified agent intelligence.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..interfaces import (
    IAgentService, IMemoryService, AgentConfig, Agent, Task, TaskResult,
    CoordinationStrategy, CoordinationResult, AgentStatus,
    AgentNotFoundError, TaskExecutionError, ResourceLimit,
    MemoryEntry, SearchResult, Metadata
)

logger = logging.getLogger(__name__)


@dataclass
class NeuroSwarmConfig:
    """Configuration for NeuroWeaver"""
    
    # Dual-phase configuration
    brain_model: str = "gpt-4"  # Strategic decision model
    swarm_council_size: int = 5  # Tactical deliberation
    
    # Phase thresholds
    complexity_threshold: float = 0.7  # Use Brain above this
    deliberation_timeout: int = 60  # Swarm phase timeout
    
    # Knowledge compounding
    enable_knowledge_compounding: bool = True
    compound_interval_minutes: int = 30
    
    # GBrain integration
    gbrain_enabled: bool = True
    gbrain_namespace: str = "neuroswarm"
    
    # Connection
    neuroswarm_path: Optional[str] = None
    redis_url: str = "redis://localhost:6379"


class NeuroPhase(Enum):
    """Decision phases in NeuroSwarm"""
    BRAIN = "brain"  # Strategic: WHAT
    SWARM = "swarm"  # Tactical: HOW
    COMPOUND = "compound"  # Learning: SYNTHESIZE


class NeuroWeaver(IAgentService, IMemoryService):
    """
    The NeuroSwarm Adapter — Brain decides WHAT, Swarm decides HOW.
    
    Dual-phase architecture:
    1. BRAIN: High-level strategic decisions
    2. SWARM: Low-level tactical execution
    
    Features:
    - Automatic phase selection based on complexity
    - Knowledge compounding (GBrain integration)
    - Memory evolution via Brain-Swarm feedback loop
    
    Usage:
        neuroweaver = NeuroWeaver(config)
        await neuroweaver.initialize()
        
        # Auto-selects Brain or Swarm based on task
        result = await neuroweaver.dispatch_task(agent_id, task)
        
        # Explicit dual-phase coordination
        result = await neuroweaver.coordinate_brain_swarm(
            brain_agents=["strategic-1"],
            swarm_agents=["tactical-1", "tactical-2"],
            objective="Build a microservice"
        )
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = NeuroSwarmConfig(**(config or {}))
        self._neuroswarm: Optional[Any] = None
        self._brain: Optional[Any] = None
        self._agents: Dict[str, Any] = {}
        self._knowledge_graph: Dict[str, Any] = {}
        self._initialized = False
        self._compound_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Initialize NeuroWeaver with Brain + Swarm"""
        if self._initialized:
            return
            
        try:
            import sys
            if self.config.neuroswarm_path:
                sys.path.insert(0, self.config.neuroswarm_path)
            
            from neuroswarm import DualPhaseController, Brain, SwarmCouncil
            
            # Initialize Brain (strategic layer)
            self._brain = Brain(
                model=self.config.brain_model,
                namespace=self.config.gbrain_namespace
            )
            await self._brain.initialize()
            
            # Initialize Swarm (tactical layer)
            self._neuroswarm = SwarmCouncil(
                size=self.config.swarm_council_size,
                deliberation_timeout=self.config.deliberation_timeout
            )
            await self._neuroswarm.initialize()
            
            # Initialize dual-phase controller
            self._dual_phase = DualPhaseController(
                brain=self._brain,
                swarm=self._neuroswarm,
                complexity_threshold=self.config.complexity_threshold
            )
            
            # Start knowledge compounding
            if self.config.enable_knowledge_compounding:
                self._compound_task = asyncio.create_task(
                    self._knowledge_compound_loop()
                )
            
            self._initialized = True
            logger.info("NeuroWeaver initialized: Brain + Swarm ready")
            
        except ImportError as e:
            logger.error(f"NeuroSwarm not available: {e}")
            raise RuntimeError("NeuroSwarm framework required")
    
    async def _knowledge_compound_loop(self) -> None:
        """Background: Compound knowledge from Brain-Swarm interactions"""
        while True:
            try:
                await asyncio.sleep(self.config.compound_interval_minutes * 60)
                
                if self._brain and self._neuroswarm:
                    # Extract insights from recent interactions
                    brain_insights = await self._brain.extract_insights()
                    swarm_patterns = await self._neuroswarm.extract_patterns()
                    
                    # Compound into unified knowledge
                    compounded = await self._dual_phase.compound_knowledge(
                        brain_insights, swarm_patterns
                    )
                    
                    # Store in knowledge graph
                    for insight in compounded:
                        self._knowledge_graph[insight.id] = insight
                    
                    logger.debug(f"Compounded {len(compounded)} knowledge items")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Knowledge compounding error: {e}")
    
    # ==================== IAgentService Implementation ====================
    
    async def create_agent(self, config: AgentConfig) -> Agent:
        """Create an agent (Brain or Swarm based on capabilities)"""
        await self._ensure_initialized()
        
        # Determine agent type based on capabilities
        if self._is_brain_agent(config.capabilities):
            return await self._create_brain_agent(config)
        else:
            return await self._create_swarm_agent(config)
    
    def _is_brain_agent(self, capabilities: List[str]) -> bool:
        """Determine if agent should be strategic (Brain) or tactical (Swarm)"""
        brain_caps = {"strategy", "planning", "architecture", "reasoning", "analysis"}
        return any(cap.lower() in brain_caps for cap in capabilities)
    
    async def _create_brain_agent(self, config: AgentConfig) -> Agent:
        """Create strategic Brain agent"""
        brain_config = {
            "agent_id": config.id,
            "name": config.name,
            "cognitive_profile": "strategic",
            "model": self.config.brain_model,
            "capabilities": config.capabilities,
            "knowledge_access": list(self._knowledge_graph.keys())
        }
        
        native_agent = await self._brain.spawn_agent(brain_config)
        
        self._agents[config.id] = {
            "type": NeuroPhase.BRAIN,
            "native": native_agent,
            "config": config
        }
        
        return Agent(
            id=config.id,
            adapter=self,
            native_instance=native_agent,
            status=AgentStatus.IDLE
        )
    
    async def _create_swarm_agent(self, config: AgentConfig) -> Agent:
        """Create tactical Swarm agent"""
        swarm_config = {
            "agent_id": config.id,
            "name": config.name,
            "cognitive_profile": "tactical",
            "capabilities": config.capabilities,
            "council_role": "deliberator"
        }
        
        native_agent = await self._neuroswarm.spawn_agent(swarm_config)
        
        self._agents[config.id] = {
            "type": NeuroPhase.SWARM,
            "native": native_agent,
            "config": config
        }
        
        return Agent(
            id=config.id,
            adapter=self,
            native_instance=native_agent,
            status=AgentStatus.IDLE
        )
    
    async def dispatch_task(self, agent_id: str, task: Task) -> TaskResult:
        """Dispatch task with automatic phase selection"""
        await self._ensure_initialized()
        
        agent_info = self._agents.get(agent_id)
        if not agent_info:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        # Determine complexity and select phase
        complexity = self._assess_complexity(task)
        
        if complexity > self.config.complexity_threshold:
            # Brain phase: Strategic decision
            return await self._dispatch_brain_task(agent_info, task)
        else:
            # Swarm phase: Tactical execution
            return await self._dispatch_swarm_task(agent_info, task)
    
    def _assess_complexity(self, task: Task) -> float:
        """Assess task complexity (0.0 - 1.0)"""
        # Simple heuristic based on context
        complexity = 0.5  # Base
        
        # Longer objectives = more complex
        if len(task.objective) > 100:
            complexity += 0.1
        
        # More constraints = more complex
        complexity += len(task.constraints) * 0.05
        
        # High priority = might need strategic thinking
        if task.priority.value < 2:  # CRITICAL or HIGH
            complexity += 0.1
        
        return min(complexity, 1.0)
    
    async def _dispatch_brain_task(self, agent_info: Dict, task: Task) -> TaskResult:
        """Dispatch to Brain agent"""
        brain_task = {
            "type": "strategic_decision",
            "objective": task.objective,
            "context": task.context,
            "knowledge_available": list(self._knowledge_graph.keys())
        }
        
        native_result = await agent_info["native"].think(brain_task)
        
        return TaskResult(
            task_id=task.id,
            success=native_result.get("decision_made", False),
            output=native_result.get("decision"),
            metrics=None
        )
    
    async def _dispatch_swarm_task(self, agent_info: Dict, task: Task) -> TaskResult:
        """Dispatch to Swarm agent"""
        swarm_task = {
            "type": "tactical_execution",
            "objective": task.objective,
            "context": task.context,
            "constraints": task.constraints
        }
        
        native_result = await agent_info["native"].execute(swarm_task)
        
        return TaskResult(
            task_id=task.id,
            success=native_result.get("status") == "completed",
            output=native_result.get("output"),
            metrics=None
        )
    
    async def get_agent_status(self, agent_id: str) -> AgentStatus:
        """Get agent status"""
        agent_info = self._agents.get(agent_id)
        if not agent_info:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        native = agent_info["native"]
        native_status = getattr(native, 'status', 'idle')
        
        status_map = {
            'thinking': AgentStatus.BUSY,
            'deliberating': AgentStatus.BUSY,
            'idle': AgentStatus.IDLE,
            'error': AgentStatus.ERROR
        }
        return status_map.get(native_status, AgentStatus.IDLE)
    
    async def terminate_agent(self, agent_id: str) -> None:
        """Terminate agent"""
        await self._ensure_initialized()
        
        agent_info = self._agents.get(agent_id)
        if not agent_info:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        if agent_info["type"] == NeuroPhase.BRAIN:
            await self._brain.terminate_agent(agent_id)
        else:
            await self._neuroswarm.terminate_agent(agent_id)
        
        del self._agents[agent_id]
    
    async def coordinate(
        self,
        agent_ids: List[str],
        strategy: CoordinationStrategy,
        objective: str = ""
    ) -> CoordinationResult:
        """Coordinate with dual-phase (Brain decides, Swarm deliberates)"""
        await self._ensure_initialized()
        
        # Separate Brain and Swarm agents
        brain_agents = [aid for aid in agent_ids 
                       if self._agents.get(aid, {}).get("type") == NeuroPhase.BRAIN]
        swarm_agents = [aid for aid in agent_ids 
                       if self._agents.get(aid, {}).get("type") == NeuroPhase.SWARM]
        
        # Phase 1: Brain decides WHAT
        if brain_agents:
            brain_result = await self._brain.strategic_decision(
                agents=brain_agents,
                objective=objective
            )
            strategic_direction = brain_result.decision
        else:
            strategic_direction = objective
        
        # Phase 2: Swarm deliberates HOW
        if swarm_agents:
            swarm_result = await self._neuroswarm.council_deliberate(
                agents=swarm_agents,
                objective=strategic_direction
            )
            
            return CoordinationResult(
                consensus=swarm_result.consensus_reached,
                decision=swarm_result.decision,
                votes=dict(swarm_result.votes),
                confidence=swarm_result.confidence,
                dissenters=list(swarm_result.dissenters)
            )
        else:
            # Brain-only decision
            return CoordinationResult(
                consensus=True,
                decision=strategic_direction,
                votes={aid: "brain_decision" for aid in brain_agents},
                confidence=0.9,
                dissenters=[]
            )
    
    async def list_agents(self) -> List[Agent]:
        """List all agents"""
        return [
            Agent(
                id=aid,
                adapter=self,
                native_instance=info["native"],
                status=AgentStatus.IDLE  # Simplified
            )
            for aid, info in self._agents.items()
        ]
    
    # ==================== IMemoryService Implementation ====================
    
    async def store(self, key: str, data: Any, metadata: Metadata) -> None:
        """Store in Brain-Swarm knowledge graph"""
        await self._ensure_initialized()
        
        # Store in GBrain if enabled
        if self.config.gbrain_enabled and self._brain:
            await self._brain.store_knowledge(key, data, metadata)
        
        # Local cache
        self._knowledge_graph[key] = {
            "data": data,
            "metadata": metadata,
            "stored_at": datetime.now()
        }
    
    async def retrieve(self, key: str) -> Optional[MemoryEntry]:
        """Retrieve from knowledge graph"""
        await self._ensure_initialized()
        
        # Try GBrain first
        if self.config.gbrain_enabled and self._brain:
            result = await self._brain.retrieve_knowledge(key)
            if result:
                return MemoryEntry(
                    key=key,
                    data=result.data,
                    metadata=result.metadata
                )
        
        # Fall back to local
        entry = self._knowledge_graph.get(key)
        if entry:
            return MemoryEntry(
                key=key,
                data=entry["data"],
                metadata=entry["metadata"]
            )
        
        return None
    
    async def search(self, query: str, limit: int = 10, min_score: float = 0.7) -> List[SearchResult]:
        """Search knowledge graph"""
        await self._ensure_initialized()
        
        # Search through Brain's semantic memory
        if self.config.gbrain_enabled and self._brain:
            brain_results = await self._brain.semantic_search(query, limit)
            return [
                SearchResult(
                    key=r.id,
                    data=r.content,
                    score=r.relevance,
                    metadata=r.metadata
                )
                for r in brain_results
            ]
        
        # Simple local search fallback
        results = []
        for key, entry in self._knowledge_graph.items():
            if query.lower() in str(entry["data"]).lower():
                results.append(SearchResult(
                    key=key,
                    data=entry["data"],
                    score=0.8,  # Arbitrary
                    metadata=entry["metadata"]
                ))
        
        return results[:limit]
    
    async def delete(self, key: str) -> bool:
        """Delete from knowledge graph"""
        if key in self._knowledge_graph:
            del self._knowledge_graph[key]
            return True
        return False
    
    async def compress(self, criteria: Any) -> Any:
        """Compress knowledge (delegated to Obliviarch)"""
        logger.info("Compression delegated to Obliviarch adapter")
        return None
    
    async def evolve(self) -> Any:
        """Evolve knowledge structures"""
        if self._dual_phase:
            return await self._dual_phase.evolve_knowledge()
        return None
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge stats"""
        return {
            "knowledge_items": len(self._knowledge_graph),
            "brain_agents": sum(1 for a in self._agents.values() if a["type"] == NeuroPhase.BRAIN),
            "swarm_agents": sum(1 for a in self._agents.values() if a["type"] == NeuroPhase.SWARM),
            "gbrain_enabled": self.config.gbrain_enabled
        }
    
    async def _ensure_initialized(self) -> None:
        """Ensure initialized"""
        if not self._initialized:
            await self.initialize()
    
    async def cleanup(self) -> None:
        """Cleanup"""
        if self._compound_task:
            self._compound_task.cancel()
            try:
                await self._compound_task
            except asyncio.CancelledError:
                pass
        
        if self._brain:
            await self._brain.shutdown()
        if self._neuroswarm:
            await self._neuroswarm.shutdown()
        
        self._initialized = False
