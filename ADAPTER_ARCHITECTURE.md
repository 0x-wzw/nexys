# Unified Platform: Adapter Architecture

## Problem Statement
Your frameworks were built independently with different interfaces. Direct integration has **1/21 success rate**.

## Solution: Adapter Pattern + Unified Interface

```
┌─────────────────────────────────────────────────────────────────┐
│                     UNIFIED INTERFACE LAYER                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │   Agent     │ │   Memory    │ │   Workflow  │               │
│  │   Service   │ │   Service   │ │   Service   │               │
│  │  (Unified)  │ │  (Unified)  │ │  (Unified)  │               │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘               │
└─────────┼───────────────┼───────────────┼───────────────────────┘
          │               │               │
          ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ADAPTER LAYER                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │ NecroSwarm  │ │ NeuroSwarm  │ │  Obliviarch │ │ VoidTether  │ │
│  │   Adapter   │ │   Adapter   │ │   Adapter   │ │   Adapter   │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────────┐ │
│  │  Namespace  │ │   Memory    │ │   Deterministic             │ │
│  │   Adapter   │ │   Adapter   │ │   Retrieval Adapter       │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │               │               │               │
          └───────────────┴───────────────┴───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRAMEWORK IMPLEMENTATIONS                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │NecroSwarm│ │NeuroSwarm│ │Obliviarch│ │VoidTether│           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │Namespace │ │  Memory  │ │  DetRet  │ │  Others  │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Unified Interface Specification

### 1. Agent Service Interface

```python
class IAgentService(Protocol):
    """Unified interface for all agent/workforce frameworks"""
    
    async def create_agent(self, config: AgentConfig) -> Agent:
        """Create a new agent instance"""
        pass
    
    async def dispatch_task(self, agent_id: str, task: Task) -> TaskResult:
        """Send task to agent"""
        pass
    
    async def get_agent_status(self, agent_id: str) -> AgentStatus:
        """Check agent health and state"""
        pass
    
    async def coordinate(self, agents: List[str], strategy: CoordinationStrategy) -> CoordinationResult:
        """Coordinate multiple agents (swarm mode)"""
        pass
```

### 2. Memory Service Interface

```python
class IMemoryService(Protocol):
    """Unified interface for all memory frameworks"""
    
    async def store(self, key: str, data: Any, metadata: Metadata) -> None:
        """Store data with optional compression"""
        pass
    
    async def retrieve(self, key: str) -> Optional[MemoryEntry]:
        """Exact retrieval"""
        pass
    
    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Semantic/similarity search"""
        pass
    
    async def compress(self, criteria: CompressionCriteria) -> CompressionReport:
        """Trigger memory compression (Obliviarch)"""
        pass
    
    async def evolve(self) -> EvolutionReport:
        """Self-improve memory structures"""
        pass
```

### 3. Workflow Service Interface

```python
class IWorkflowService(Protocol):
    """Unified interface for all workflow frameworks"""
    
    async def define_workflow(self, definition: WorkflowDef) -> Workflow:
        """Register a new workflow"""
        pass
    
    async def execute(self, workflow_id: str, input: Any) -> ExecutionResult:
        """Run workflow"""
        pass
    
    async def get_state(self, execution_id: str) -> ExecutionState:
        """Check workflow progress"""
        pass
    
    async def pause(self, execution_id: str) -> None:
        """Pause execution"""
        pass
    
    async def resume(self, execution_id: str) -> None:
        """Resume execution"""
        pass
```

## Adapter Implementation Plan

### Priority 1: Core Adapters (Week 1)

| Adapter | Framework | Complexity | Reason |
|---------|-----------|------------|--------|
| NecroSwarmAdapter | necroswarm | High | Core workforce |
| NeuroSwarmAdapter | neuroswarm | High | Core memory+workforce |
| ObliviarchAdapter | obliviarch | Medium | Core memory |

### Priority 2: Integration Adapters (Week 2)

| Adapter | Framework | Complexity | Reason |
|---------|-----------|------------|--------|
| VoidTetherAdapter | voidtether | High | Universal bridge |
| NamespaceAdapter | openclaw-namespace | Low | Workflow foundation |
| MemoryEvolutionAdapter | openclaw-memory-evolution | Medium | Memory enhancement |

### Priority 3: Utility Adapters (Week 3)

| Adapter | Framework | Complexity | Reason |
|---------|-----------|------------|--------|
| DeterministicRetrievalAdapter | openclaw-deterministic-retrieval | Low | Retrieval optimization |
| AgentIdentityAdapter | agent-identity | Medium | Security layer |

## Adapter Template

```python
# adapters/necroswarm_adapter.py

from typing import List, Optional
import asyncio

class NecroSwarmAdapter(IAgentService):
    """Adapter for NecroSwarm workforce framework"""
    
    def __init__(self, config: NecroSwarmConfig):
        self.config = config
        self._necroswarm = None  # Lazy init
        self._agents = {}
    
    async def _init_necroswarm(self):
        """Lazy initialization of NecroSwarm"""
        if self._necroswarm is None:
            # Import here to avoid dependency issues
            from necroswarm import SwarmController
            self._necroswarm = SwarmController(self.config.to_necroswarm())
            await self._necroswarm.initialize()
    
    async def create_agent(self, config: AgentConfig) -> Agent:
        await self._init_necroswarm()
        
        # Transform unified config to NecroSwarm format
        necro_config = {
            "agent_id": config.id,
            "cognitive_dimensions": config.capabilities,
            "token_budget": config.resources.token_limit,
            "consensus_weight": config.metadata.get("consensus_weight", 1.0)
        }
        
        # Create through NecroSwarm
        necro_agent = await self._necroswarm.spawn_agent(necro_config)
        
        # Wrap in unified Agent type
        agent = Agent(
            id=neco_agent.id,
            adapter=self,
            native_instance=necro_agent
        )
        
        self._agents[agent.id] = agent
        return agent
    
    async def dispatch_task(self, agent_id: str, task: Task) -> TaskResult:
        await self._init_necroswarm()
        
        agent = self._agents.get(agent_id)
        if not agent:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        # Transform task to NecroSwarm format
        necro_task = {
            "task_id": task.id,
            "objective": task.objective,
            "constraints": task.constraints,
            "context": task.context
        }
        
        # Execute through NecroSwarm
        necro_result = await agent.native_instance.execute(necro_task)
        
        # Transform result to unified format
        return TaskResult(
            task_id=task.id,
            success=necro_result.status == "completed",
            output=necro_result.output,
            metrics=necro_result.metrics
        )
    
    async def coordinate(self, agents: List[str], strategy: CoordinationStrategy) -> CoordinationResult:
        await self._init_necroswarm()
        
        # Map to NecroSwarm council coordination
        necro_strategy = self._map_coordination_strategy(strategy)
        
        # Use NecroSwarm's 10-D council
        council_result = await self._necroswarm.council_deliberate(
            agent_ids=agents,
            strategy=necro_strategy
        )
        
        return CoordinationResult(
            consensus=council_result.consensus,
            votes=council_result.votes,
            confidence=council_result.confidence
        )
    
    def _map_coordination_strategy(self, strategy: CoordinationStrategy):
        """Map unified strategy to NecroSwarm-specific format"""
        strategy_map = {
            CoordinationStrategy.CONSENSUS: "consensus_voting",
            CoordinationStrategy.HIERARCHICAL: "hierarchical_delegation",
            CoordinationStrategy.MARKET: "token_weighted_voting"
        }
        return strategy_map.get(strategy, "consensus_voting")
```

## Implementation Roadmap (Revised)

### Week 1: Foundation
- [ ] Define unified interfaces (Protocol classes)
- [ ] Set up adapter package structure
- [ ] Implement NecroSwarmAdapter
- [ ] Implement NeuroSwarmAdapter
- [ ] Basic integration tests

### Week 2: Core Services
- [ ] Implement ObliviarchAdapter
- [ ] Implement MemoryEvolutionAdapter
- [ ] Implement NamespaceAdapter
- [ ] Create ServiceRegistry for adapter discovery
- [ ] Service composition tests

### Week 3: Integration Layer
- [ ] Implement VoidTetherAdapter
- [ ] Build adapter mesh (auto-discovery)
- [ ] Cross-adapter communication tests
- [ ] Performance benchmarking

### Week 4: Polish & Documentation
- [ ] Error handling & recovery
- [ ] Observability (metrics, tracing)
- [ ] CLI tool
- [ ] Documentation & examples

## Success Metrics

- [ ] All 7 core frameworks have working adapters
- [ ] Cross-framework operations <500ms latency
- [ ] 1000+ agents running concurrently
- [ ] Zero data loss during framework transitions
- [ ] >90% test coverage on adapters

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Framework changes break adapter | Version pinning + CI tests |
| Performance degradation | Benchmarks + caching layer |
| Circular dependencies | Dependency graph validation |
| Memory leaks | Resource tracking + limits |

---

*Next: Start implementing Priority 1 adapters*
