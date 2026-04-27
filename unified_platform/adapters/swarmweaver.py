"""
SwarmWeaver — The NecroSwarm Adapter

Weaves multiple agents into a unified workforce through the NecroSwarm council.
Part of the Unified Agentic Platform.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..interfaces import (
    IAgentService, AgentConfig, Agent, Task, TaskResult,
    CoordinationStrategy, CoordinationResult, AgentStatus,
    AgentNotFoundError, TaskExecutionError, ResourceLimit
)

logger = logging.getLogger(__name__)


@dataclass
class NecroSwarmConfig:
    """Configuration for SwarmWeaver"""
    # Council settings
    council_size: int = 10
    consensus_threshold: float = 0.7
    token_budget_per_agent: int = 100000
    
    # Swarm behavior
    enable_cost_optimization: bool = True
    enable_token_economics: bool = True
    rebalance_interval_seconds: int = 300
    
    # ACS-ACP Flywheel
    acs_enabled: bool = True  # Agent Creation System
    acp_enabled: bool = True  # Agent Consumption Protocol
    
    # Connection to native NecroSwarm
    necroswarm_path: Optional[str] = None
    redis_url: str = "redis://localhost:6379"
    
    def to_necroswarm_dict(self) -> Dict[str, Any]:
        """Convert to NecroSwarm native config"""
        return {
            "council": {
                "size": self.council_size,
                "consensus_threshold": self.consensus_threshold
            },
            "token_budget": self.token_budget_per_agent,
            "cost_optimization": self.enable_cost_optimization,
            "token_economics": self.enable_token_economics,
            "acs_acp": {
                "creation": self.acs_enabled,
                "consumption": self.acp_enabled
            },
            "redis_url": self.redis_url
        }


class SwarmAgent:
    """Wrapper for NecroSwarm agents with unified interface"""
    
    def __init__(self, agent_id: str, native_agent: Any, adapter: "SwarmWeaver"):
        self.id = agent_id
        self.native = native_agent
        self.adapter = adapter
        self.created_at = datetime.now()
        self.task_count = 0
        self.success_count = 0
        
    @property
    def status(self) -> AgentStatus:
        """Map native status to unified status"""
        native_status = getattr(self.native, 'status', 'idle')
        status_map = {
            'idle': AgentStatus.IDLE,
            'busy': AgentStatus.BUSY,
            'error': AgentStatus.ERROR,
            'offline': AgentStatus.OFFLINE,
            'spawning': AgentStatus.BUSY,
            'terminating': AgentStatus.BUSY
        }
        return status_map.get(native_status, AgentStatus.IDLE)
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute a task through native NecroSwarm"""
        return await self.adapter._execute_on_agent(self, task)


class SwarmWeaver(IAgentService):
    """
    The NecroSwarm Adapter — Weaves agents into a unified workforce.
    
    Features:
    - 10-Dimensional Council for cost-optimized decisions
    - ACS-ACP Flywheel for agent lifecycle management
    - Token economics for swarm coordination
    - Automatic rebalancing and scaling
    
    Usage:
        weaver = SwarmWeaver(config)
        await weaver.initialize()
        
        # Create agent
        agent = await weaver.create_agent(config)
        
        # Dispatch task
        result = await weaver.dispatch_task(agent.id, task)
        
        # Coordinate swarm
        result = await weaver.coordinate([agent1.id, agent2.id], 
                                          CoordinationStrategy.CONSENSUS)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = NecroSwarmConfig(**(config or {}))
        self._necroswarm: Optional[Any] = None
        self._agents: Dict[str, SwarmAgent] = {}
        self._initialized = False
        self._rebalance_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Initialize SwarmWeaver and connect to NecroSwarm"""
        if self._initialized:
            return
            
        try:
            # Import NecroSwarm (lazy to avoid dependency issues)
            import sys
            if self.config.necroswarm_path:
                sys.path.insert(0, self.config.necroswarm_path)
            
            from necroswarm import SwarmController, CouncilConfig
            
            # Initialize NecroSwarm controller
            council_config = CouncilConfig(
                size=self.config.council_size,
                consensus_threshold=self.config.consensus_threshold
            )
            
            self._necroswarm = SwarmController(
                council=council_config,
                token_budget=self.config.token_budget_per_agent,
                cost_optimization=self.config.enable_cost_optimization,
                token_economics=self.config.enable_token_economics,
                redis_url=self.config.redis_url
            )
            
            await self._necroswarm.initialize()
            
            # Start ACS-ACP flywheel if enabled
            if self.config.acs_enabled or self.config.acp_enabled:
                await self._start_flywheel()
            
            # Start rebalancing
            if self.config.rebalance_interval_seconds > 0:
                self._rebalance_task = asyncio.create_task(
                    self._rebalance_loop()
                )
            
            self._initialized = True
            logger.info("SwarmWeaver initialized successfully")
            
        except ImportError as e:
            logger.error(f"NecroSwarm not available: {e}")
            raise RuntimeError("NecroSwarm framework required but not installed")
        except Exception as e:
            logger.error(f"Failed to initialize SwarmWeaver: {e}")
            raise
    
    async def _start_flywheel(self) -> None:
        """Start the ACS-ACP flywheel for agent lifecycle"""
        if not self._necroswarm:
            return
            
        # ACS: Monitor demand and create agents
        if self.config.acs_enabled:
            await self._necroswarm.enable_acs(
                spawn_threshold=0.7,  # Spawn when 70% capacity
                max_agents=100
            )
        
        # ACP: Monitor usage and retire agents
        if self.config.acp_enabled:
            await self._necroswarm.enable_acp(
                retire_threshold=0.1,  # Retire when <10% utilization
                min_agents=2
            )
    
    async def _rebalance_loop(self) -> None:
        """Background task for swarm rebalancing"""
        while True:
            try:
                await asyncio.sleep(self.config.rebalance_interval_seconds)
                
                if self._necroswarm and self._agents:
                    # Rebalance token budgets
                    await self._necroswarm.rebalance_resources()
                    
                    # Update agent statuses
                    for agent_id, agent in self._agents.items():
                        native_status = await self._necroswarm.get_agent_status(agent_id)
                        if native_status:
                            # Sync status if needed
                            pass
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rebalance error: {e}")
    
    # ==================== IAgentService Implementation ====================
    
    async def create_agent(self, config: AgentConfig) -> Agent:
        """Create a new agent through NecroSwarm"""
        await self._ensure_initialized()
        
        try:
            # Transform unified config to NecroSwarm format
            necro_config = self._transform_agent_config(config)
            
            # Spawn agent through NecroSwarm
            native_agent = await self._necroswarm.spawn_agent(necro_config)
            
            # Wrap in SwarmAgent
            swarm_agent = SwarmAgent(
                agent_id=config.id,
                native_agent=native_agent,
                adapter=self
            )
            
            self._agents[config.id] = swarm_agent
            
            # Create unified Agent
            agent = Agent(
                id=config.id,
                adapter=self,
                native_instance=swarm_agent,
                status=AgentStatus.IDLE
            )
            
            logger.info(f"Created agent {config.id} through SwarmWeaver")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent {config.id}: {e}")
            raise
    
    async def dispatch_task(self, agent_id: str, task: Task) -> TaskResult:
        """Dispatch task to an agent"""
        await self._ensure_initialized()
        
        swarm_agent = self._agents.get(agent_id)
        if not swarm_agent:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        try:
            result = await swarm_agent.execute(task)
            swarm_agent.task_count += 1
            if result.success:
                swarm_agent.success_count += 1
            return result
            
        except Exception as e:
            logger.error(f"Task dispatch failed for {agent_id}: {e}")
            raise TaskExecutionError(f"Task failed: {e}")
    
    async def get_agent_status(self, agent_id: str) -> AgentStatus:
        """Get agent status"""
        swarm_agent = self._agents.get(agent_id)
        if not swarm_agent:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        return swarm_agent.status
    
    async def terminate_agent(self, agent_id: str) -> None:
        """Terminate an agent"""
        await self._ensure_initialized()
        
        swarm_agent = self._agents.get(agent_id)
        if not swarm_agent:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        try:
            await self._necroswarm.terminate_agent(agent_id)
            del self._agents[agent_id]
            logger.info(f"Terminated agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to terminate agent {agent_id}: {e}")
            raise
    
    async def coordinate(
        self,
        agent_ids: List[str],
        strategy: CoordinationStrategy,
        objective: str = ""
    ) -> CoordinationResult:
        """Coordinate multiple agents using the 10-D Council"""
        await self._ensure_initialized()
        
        # Verify all agents exist
        for agent_id in agent_ids:
            if agent_id not in self._agents:
                raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        try:
            # Map strategy to NecroSwarm format
            necro_strategy = self._map_strategy(strategy)
            
            # Use NecroSwarm's council deliberation
            council_result = await self._necroswarm.council_deliberate(
                agent_ids=agent_ids,
                objective=objective,
                strategy=necro_strategy
            )
            
            # Transform to unified format
            return CoordinationResult(
                consensus=council_result.consensus_reached,
                decision=council_result.decision,
                votes=dict(council_result.votes),
                confidence=council_result.confidence,
                dissenters=list(council_result.dissenters)
            )
            
        except Exception as e:
            logger.error(f"Coordination failed: {e}")
            raise
    
    async def list_agents(self) -> List[Agent]:
        """List all agents"""
        return [
            Agent(
                id=swarm_agent.id,
                adapter=self,
                native_instance=swarm_agent,
                status=swarm_agent.status
            )
            for swarm_agent in self._agents.values()
        ]
    
    # ==================== Internal Methods ====================
    
    async def _ensure_initialized(self) -> None:
        """Ensure SwarmWeaver is initialized"""
        if not self._initialized:
            await self.initialize()
    
    def _transform_agent_config(self, config: AgentConfig) -> Dict[str, Any]:
        """Transform unified config to NecroSwarm format"""
        return {
            "agent_id": config.id,
            "name": config.name,
            "cognitive_dimensions": self._map_capabilities(config.capabilities),
            "token_budget": config.resources.token_limit,
            "memory_limit_mb": config.resources.memory_mb,
            "timeout_seconds": config.resources.timeout_seconds,
            "metadata": config.metadata,
            "consensus_weight": config.metadata.get("consensus_weight", 1.0),
            "voting_power": config.metadata.get("voting_power", 1.0)
        }
    
    def _map_capabilities(self, capabilities: List[str]) -> List[str]:
        """Map unified capabilities to NecroSwarm cognitive dimensions"""
        # Map to NecroSwarm's 10-D council dimensions
        dimension_map = {
            "reasoning": "analytical",
            "coding": "technical",
            "creative": "creative",
            "research": "research",
            "planning": "strategic",
            "execution": "operational",
            "communication": "social",
            "analysis": "analytical",
            "design": "creative",
            "testing": "technical"
        }
        
        dimensions = set()
        for cap in capabilities:
            dim = dimension_map.get(cap.lower())
            if dim:
                dimensions.add(dim)
        
        return list(dimensions) if dimensions else ["general"]
    
    def _map_strategy(self, strategy: CoordinationStrategy) -> str:
        """Map unified strategy to NecroSwarm format"""
        strategy_map = {
            CoordinationStrategy.CONSENSUS: "consensus_voting",
            CoordinationStrategy.HIERARCHICAL: "hierarchical_delegation",
            CoordinationStrategy.MARKET: "token_weighted_voting",
            CoordinationStrategy.ROUND_ROBIN: "round_robin"
        }
        return strategy_map.get(strategy, "consensus_voting")
    
    async def _execute_on_agent(self, swarm_agent: SwarmAgent, task: Task) -> TaskResult:
        """Execute task on a specific agent"""
        # Transform task to NecroSwarm format
        necro_task = {
            "task_id": task.id,
            "objective": task.objective,
            "context": task.context,
            "constraints": task.constraints,
            "priority": task.priority.value,
            "timeout": task.timeout_seconds
        }
        
        # Execute through NecroSwarm
        native_result = await self._necroswarm.execute_task(
            agent_id=swarm_agent.id,
            task=necro_task
        )
        
        # Transform result
        metrics = TaskMetrics(
            tokens_used=native_result.get("tokens_used", 0),
            latency_ms=native_result.get("latency_ms", 0.0),
            cost_estimate=native_result.get("cost", 0.0),
            cache_hit=native_result.get("cache_hit", False)
        )
        
        return TaskResult(
            task_id=task.id,
            success=native_result.get("status") == "completed",
            output=native_result.get("output"),
            error=native_result.get("error"),
            metrics=metrics
        )
    
    # ==================== Lifecycle ====================
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self._rebalance_task:
            self._rebalance_task.cancel()
            try:
                await self._rebalance_task
            except asyncio.CancelledError:
                pass
        
        if self._necroswarm:
            # Terminate all agents
            for agent_id in list(self._agents.keys()):
                try:
                    await self._necroswarm.terminate_agent(agent_id)
                except Exception as e:
                    logger.warning(f"Error terminating agent {agent_id}: {e}")
            
            await self._necroswarm.shutdown()
        
        self._initialized = False
        logger.info("SwarmWeaver cleaned up")
    
    # ==================== Utility Methods ====================
    
    def get_swarm_stats(self) -> Dict[str, Any]:
        """Get SwarmWeaver statistics"""
        total_tasks = sum(a.task_count for a in self._agents.values())
        total_success = sum(a.success_count for a in self._agents.values())
        
        return {
            "agents_total": len(self._agents),
            "agents_active": sum(1 for a in self._agents.values() 
                               if a.status == AgentStatus.BUSY),
            "agents_idle": sum(1 for a in self._agents.values() 
                             if a.status == AgentStatus.IDLE),
            "tasks_total": total_tasks,
            "tasks_success": total_success,
            "success_rate": total_success / total_tasks if total_tasks > 0 else 0.0,
            "council_size": self.config.council_size,
            "token_economics_enabled": self.config.enable_token_economics
        }
