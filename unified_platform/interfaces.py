"""
Unified Interface Definitions

All frameworks must implement these protocols to participate in the platform.
"""

from typing import Protocol, runtime_checkable, Any, Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class AgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class CoordinationStrategy(Enum):
    CONSENSUS = "consensus"
    HIERARCHICAL = "hierarchical"
    MARKET = "market"
    ROUND_ROBIN = "round_robin"


class TaskPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


# ==================== Data Classes ====================

@dataclass
class ResourceLimit:
    """Resource constraints for agents"""
    token_limit: int = 100000
    memory_mb: int = 512
    timeout_seconds: int = 300


@dataclass
class AgentConfig:
    """Configuration for creating an agent"""
    id: str
    name: str
    capabilities: List[str]
    resources: ResourceLimit
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        if isinstance(self.resources, dict):
            self.resources = ResourceLimit(**self.resources)


@dataclass
class Agent:
    """Unified agent representation"""
    id: str
    adapter: "IAgentService"
    native_instance: Any
    status: AgentStatus = AgentStatus.IDLE
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class Task:
    """Task to be executed by an agent"""
    id: str
    objective: str
    context: Dict[str, Any]
    constraints: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: int = 300


@dataclass
class TaskMetrics:
    """Performance metrics for task execution"""
    tokens_used: int
    latency_ms: float
    cost_estimate: float
    cache_hit: bool


@dataclass
class TaskResult:
    """Result of task execution"""
    task_id: str
    success: bool
    output: Any
    error: Optional[str] = None
    metrics: Optional[TaskMetrics] = None


@dataclass
class CoordinationResult:
    """Result of multi-agent coordination"""
    consensus: bool
    decision: Any
    votes: Dict[str, Any]
    confidence: float
    dissenters: List[str]


@dataclass
class Metadata:
    """Metadata for memory entries"""
    source: str
    timestamp: datetime
    tags: List[str]
    importance: float = 1.0
    ttl_seconds: Optional[int] = None


@dataclass
class MemoryEntry:
    """A stored memory item"""
    key: str
    data: Any
    metadata: Metadata
    compressed: bool = False
    compression_ratio: Optional[float] = None


@dataclass
class SearchResult:
    """Result from memory search"""
    key: str
    data: Any
    score: float
    metadata: Metadata


@dataclass
class CompressionCriteria:
    """Criteria for memory compression"""
    older_than_days: int = 30
    min_access_count: int = 1
    compression_level: str = "medium"  # low, medium, high


@dataclass
class CompressionReport:
    """Report from compression operation"""
    entries_compressed: int
    bytes_before: int
    bytes_after: int
    compression_ratio: float


@dataclass
class EvolutionReport:
    """Report from memory evolution"""
    new_relationships: int
    consolidated_entries: int
    schema_changes: List[str]


@dataclass
class WorkflowDef:
    """Definition of a workflow"""
    id: str
    name: str
    steps: List[Dict[str, Any]]
    triggers: List[str]
    error_handling: str = "retry"  # retry, skip, abort


@dataclass
class Workflow:
    """Instantiated workflow"""
    id: str
    definition: WorkflowDef
    state: str = "created"
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ExecutionState:
    """Current state of workflow execution"""
    execution_id: str
    workflow_id: str
    current_step: int
    total_steps: int
    variables: Dict[str, Any]
    status: str  # running, paused, completed, error


@dataclass
class ExecutionResult:
    """Result of workflow execution"""
    execution_id: str
    workflow_id: str
    success: bool
    output: Any
    steps_completed: int
    total_steps: int
    error: Optional[str] = None


# ==================== Protocols ====================

@runtime_checkable
class IAgentService(Protocol):
    """Unified interface for all agent/workforce frameworks"""
    
    async def create_agent(self, config: AgentConfig) -> Agent:
        """Create a new agent instance"""
        ...
    
    async def dispatch_task(self, agent_id: str, task: Task) -> TaskResult:
        """Send task to agent"""
        ...
    
    async def get_agent_status(self, agent_id: str) -> AgentStatus:
        """Check agent health and state"""
        ...
    
    async def terminate_agent(self, agent_id: str) -> None:
        """Gracefully terminate an agent"""
        ...
    
    async def coordinate(
        self, 
        agent_ids: List[str], 
        strategy: CoordinationStrategy,
        objective: str
    ) -> CoordinationResult:
        """Coordinate multiple agents (swarm mode)"""
        ...
    
    async def list_agents(self) -> List[Agent]:
        """List all managed agents"""
        ...


@runtime_checkable
class IMemoryService(Protocol):
    """Unified interface for all memory frameworks"""
    
    async def store(
        self, 
        key: str, 
        data: Any, 
        metadata: Metadata
    ) -> None:
        """Store data with metadata"""
        ...
    
    async def retrieve(self, key: str) -> Optional[MemoryEntry]:
        """Exact key retrieval"""
        ...
    
    async def search(
        self, 
        query: str, 
        limit: int = 10,
        min_score: float = 0.7
    ) -> List[SearchResult]:
        """Semantic/similarity search"""
        ...
    
    async def delete(self, key: str) -> bool:
        """Delete a memory entry"""
        ...
    
    async def compress(self, criteria: CompressionCriteria) -> CompressionReport:
        """Trigger memory compression (Obliviarch-style)"""
        ...
    
    async def evolve(self) -> EvolutionReport:
        """Self-improve memory structures"""
        ...
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        ...


@runtime_checkable
class IWorkflowService(Protocol):
    """Unified interface for all workflow frameworks"""
    
    async def define_workflow(self, definition: WorkflowDef) -> Workflow:
        """Register a new workflow"""
        ...
    
    async def execute(
        self, 
        workflow_id: str, 
        input_data: Any,
        variables: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """Run workflow"""
        ...
    
    async def get_state(self, execution_id: str) -> ExecutionState:
        """Check workflow progress"""
        ...
    
    async def pause(self, execution_id: str) -> None:
        """Pause execution"""
        ...
    
    async def resume(self, execution_id: str) -> None:
        """Resume execution"""
        ...
    
    async def cancel(self, execution_id: str) -> None:
        """Cancel execution"""
        ...
    
    async def list_workflows(self) -> List[Workflow]:
        """List all defined workflows"""
        ...


# ==================== Exceptions ====================

class AgentNotFoundError(Exception):
    """Agent ID not found"""
    pass

class TaskExecutionError(Exception):
    """Task execution failed"""
    pass

class MemoryNotFoundError(Exception):
    """Memory key not found"""
    pass

class WorkflowNotFoundError(Exception):
    """Workflow ID not found"""
    pass

class ExecutionNotFoundError(Exception):
    """Execution ID not found"""
    pass

class AdapterError(Exception):
    """Adapter initialization or operation failed"""
    pass
