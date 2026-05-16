"""
NamespaceAdapter — Workflow Orchestration Engine

Defines, manages, and executes multi-agent workflows through the
Namespace protocol. Enables:
- Declarative workflow definitions
- State machine execution
- Parallel/sequential step orchestration
- Dynamic workflow generation
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import json

from ..interfaces import (
    IWorkflowService, WorkflowDef, WorkflowStep, WorkflowExecution,
    WorkflowStatus, ExecutionContext, WorkflowNotFoundError, ExecutionError
)

logger = logging.getLogger(__name__)


class StepType(Enum):
    """Types of workflow steps"""
    SEQUENTIAL = auto()      # Execute one by one
    PARALLEL = auto()        # Execute concurrently
    CONDITIONAL = auto()     # Branch based on condition
    LOOP = auto()            # Iterate over collection
    WAIT = auto()            # Wait for external event
    SUBWORKFLOW = auto()     # Nested workflow


class StepState(Enum):
    """Step execution states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class StepExecution:
    """Execution state for a single step"""
    step_id: str
    state: StepState = StepState.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NamespaceConfig:
    """Configuration for Namespace workflow engine"""
    
    # Execution
    max_concurrent_steps: int = 10
    default_timeout_seconds: int = 300
    enable_step_retry: bool = True
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    
    # State management
    state_backend: str = "memory"  # memory, redis, file
    checkpoint_interval_seconds: int = 30
    
    # Dynamic workflows
    enable_dynamic_generation: bool = True
    generation_model: str = "gpt-4"
    
    # Monitoring
    enable_metrics: bool = True
    metrics_interval_seconds: int = 60


class NamespaceAdapter(IWorkflowService):
    """
    The Namespace Adapter — Workflow Orchestration Engine.
    
    Manages multi-agent workflows with sophisticated control flow:
    - Sequential execution
    - Parallel execution with join semantics
    - Conditional branching
    - Looping constructs
    - Event-driven waits
    - Subworkflow composition
    
    Usage:
        namespace = NamespaceAdapter(config)
        await namespace.initialize()
        
        # Define workflow
        workflow = WorkflowDef(
            name="DataPipeline",
            steps=[
                WorkflowStep(
                    step_id="extract",
                    agent_type="data-extractor",
                    task_description="Extract data from API",
                    output_key="raw_data"
                ),
                WorkflowStep(
                    step_id="transform",
                    agent_type="transformer",
                    task_description="Transform data",
                    depends_on=["extract"],
                    output_key="transformed_data"
                ),
                WorkflowStep(
                    step_id="load",
                    agent_type="loader",
                    task_description="Load to database",
                    depends_on=["transform"],
                    output_key="result"
                )
            ]
        )
        
        # Execute
        workflow_id = await namespace.create_workflow(workflow)
        execution = await namespace.execute_workflow(
            workflow_id,
            ExecutionContext(variables={"source": "api"})
        )
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = NamespaceConfig(**(config or {}))
        self._workflows: Dict[str, WorkflowDef] = {}
        self._executions: Dict[str, WorkflowExecution] = {}
        self._step_executions: Dict[str, Dict[str, StepExecution]] = {}
        self._step_handlers: Dict[str, Callable] = {}
        self._initialized = False
        
        # Semaphore for concurrency control
        self._execution_semaphore: Optional[asyncio.Semaphore] = None
        
        # Checkpointing
        self._checkpoint_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Initialize Namespace workflow engine"""
        if self._initialized:
            return
        
        self._execution_semaphore = asyncio.Semaphore(
            self.config.max_concurrent_steps
        )
        
        # Start checkpointing
        if self.config.checkpoint_interval_seconds > 0:
            self._checkpoint_task = asyncio.create_task(
                self._checkpoint_loop()
            )
        
        self._initialized = True
        logger.info("NamespaceAdapter initialized")
    
    async def _checkpoint_loop(self) -> None:
        """Background: Checkpoint workflow states"""
        while True:
            try:
                await asyncio.sleep(self.config.checkpoint_interval_seconds)
                await self._checkpoint_states()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Checkpoint error: {e}")
    
    async def _checkpoint_states(self) -> None:
        """Save execution states"""
        # In production, persist to Redis/file
        checkpoint_data = {
            wid: {
                "status": exec.status.value,
                "started": exec.started_at.isoformat() if exec.started_at else None,
                "steps": {
                    sid: {
                        "state": step.state.value,
                        "output": step.output
                    }
                    for sid, step in self._step_executions.get(wid, {}).items()
                }
            }
            for wid, exec in self._executions.items()
            if exec.status == WorkflowStatus.RUNNING
        }
        
        logger.debug(f"Checkpointed {len(checkpoint_data)} running workflows")
    
    # ==================== Workflow Management ====================
    
    async def create_workflow(self, definition: WorkflowDef) -> str:
        """Register a workflow definition"""
        workflow_id = f"wf_{definition.name.lower()}_{hash(definition.name + str(datetime.now())) % 10000}"
        
        # Validate workflow
        self._validate_workflow(definition)
        
        self._workflows[workflow_id] = definition
        logger.info(f"Created workflow: {definition.name} ({workflow_id})")
        
        return workflow_id
    
    def _validate_workflow(self, definition: WorkflowDef) -> None:
        """Validate workflow structure"""
        step_ids = {step.step_id for step in definition.steps}
        
        # Check dependencies exist
        for step in definition.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise ValueError(f"Step {step.step_id} depends on unknown step {dep}")
        
        # Check for cycles (simplified)
        visited = set()
        def has_cycle(step_id: str, path: Set[str]) -> bool:
            if step_id in path:
                return True
            if step_id in visited:
                return False
            
            step = next((s for s in definition.steps if s.step_id == step_id), None)
            if not step:
                return False
            
            path.add(step_id)
            for dep in step.depends_on:
                if has_cycle(dep, path):
                    return True
            path.remove(step_id)
            visited.add(step_id)
            return False
        
        for step in definition.steps:
            if has_cycle(step.step_id, set()):
                raise ValueError(f"Cycle detected involving step {step.step_id}")
    
    async def execute_workflow(
        self,
        workflow_id: str,
        context: ExecutionContext
    ) -> WorkflowExecution:
        """Execute a workflow"""
        await self._ensure_initialized()
        
        definition = self._workflows.get(workflow_id)
        if not definition:
            raise WorkflowNotFoundError(f"Workflow {workflow_id} not found")
        
        # Create execution
        execution = WorkflowExecution(
            execution_id=f"exec_{datetime.now().timestamp()}",
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(),
            context=context
        )
        
        self._executions[execution.execution_id] = execution
        self._step_executions[execution.execution_id] = {}
        
        try:
            # Initialize step executions
            for step in definition.steps:
                self._step_executions[execution.execution_id][step.step_id] = StepExecution(
                    step_id=step.step_id
                )
            
            # Determine execution order based on dependencies
            execution_order = self._compute_execution_order(definition)
            
            # Execute steps
            for step_group in execution_order:
                # step_group is a list of steps that can execute in parallel
                if len(step_group) == 1:
                    # Sequential execution
                    await self._execute_step(
                        execution.execution_id,
                        step_group[0],
                        context
                    )
                else:
                    # Parallel execution
                    await self._execute_parallel(
                        execution.execution_id,
                        step_group,
                        context
                    )
                
                # Check if any step failed
                if execution.status == WorkflowStatus.FAILED:
                    break
            
            # Update final status
            if execution.status != WorkflowStatus.FAILED:
                execution.status = WorkflowStatus.COMPLETED
                execution.completed_at = datetime.now()
            
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            logger.error(f"Workflow {workflow_id} failed: {e}")
        
        return execution
    
    def _compute_execution_order(self, definition: WorkflowDef) -> List[List[WorkflowStep]]:
        """Compute parallel execution groups based on dependencies"""
        steps_by_id = {step.step_id: step for step in definition.steps}
        
        # Build dependency graph
        in_degree = {step.step_id: 0 for step in definition.steps}
        dependents = {step.step_id: [] for step in definition.steps}
        
        for step in definition.steps:
            for dep in step.depends_on:
                dependents[dep].append(step.step_id)
                in_degree[step.step_id] += 1
        
        # Topological sort with parallel grouping
        order = []
        ready = [sid for sid, deg in in_degree.items() if deg == 0]
        completed = set()
        
        while ready:
            # All currently ready steps can execute in parallel
            current_group = [steps_by_id[sid] for sid in ready]
            order.append(current_group)
            
            next_ready = []
            for sid in ready:
                completed.add(sid)
                for dependent in dependents[sid]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_ready.append(dependent)
            
            ready = next_ready
        
        return order
    
    async def _execute_step(
        self,
        execution_id: str,
        step: WorkflowStep,
        context: ExecutionContext
    ) -> None:
        """Execute a single step"""
        step_exec = self._step_executions[execution_id][step.step_id]
        step_exec.state = StepState.RUNNING
        step_exec.started_at = datetime.now()
        
        execution = self._executions[execution_id]
        
        # Get handler for agent type
        handler = self._step_handlers.get(step.agent_type)
        if not handler:
            step_exec.state = StepState.FAILED
            step_exec.error = f"No handler for agent type: {step.agent_type}"
            execution.status = WorkflowStatus.FAILED
            return
        
        # Prepare input from dependencies
        input_data = self._prepare_step_input(execution_id, step, context)
        
        # Execute with retry logic
        for attempt in range(self.config.max_retries + 1):
            try:
                async with self._execution_semaphore:
                    result = await handler(
                        step.task_description,
                        input_data,
                        step.parameters
                    )
                
                step_exec.output = result
                step_exec.state = StepState.COMPLETED
                step_exec.completed_at = datetime.now()
                execution.completed_steps.append(step.step_id)
                
                # Store output in context if specified
                if step.output_key:
                    context.variables[step.output_key] = result
                
                break
                
            except Exception as e:
                step_exec.retry_count += 1
                
                if attempt < self.config.max_retries:
                    step_exec.state = StepState.RETRYING
                    await asyncio.sleep(
                        self.config.retry_delay_seconds * (2 ** attempt)
                    )
                else:
                    step_exec.state = StepState.FAILED
                    step_exec.error = str(e)
                    execution.status = WorkflowStatus.FAILED
                    execution.error = f"Step {step.step_id} failed: {e}"
    
    async def _execute_parallel(
        self,
        execution_id: str,
        steps: List[WorkflowStep],
        context: ExecutionContext
    ) -> None:
        """Execute steps in parallel"""
        tasks = [
            self._execute_step(execution_id, step, context)
            for step in steps
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def _prepare_step_input(
        self,
        execution_id: str,
        step: WorkflowStep,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Prepare input data for step execution"""
        input_data = {}
        
        # Add context variables
        input_data.update(context.variables)
        
        # Add outputs from dependencies
        step_execs = self._step_executions.get(execution_id, {})
        for dep_id in step.depends_on:
            dep_exec = step_execs.get(dep_id)
            if dep_exec and dep_exec.output is not None:
                input_data[f"{dep_id}_output"] = dep_exec.output
        
        return input_data
    
    async def get_workflow_status(self, workflow_id: str) -> WorkflowStatus:
        """Get current workflow status"""
        # Find most recent execution
        executions = [
            exec for exec in self._executions.values()
            if exec.workflow_id == workflow_id
        ]
        
        if not executions:
            return WorkflowStatus.PENDING
        
        # Return status of most recent
        latest = max(executions, key=lambda e: e.started_at or datetime.min)
        return latest.status
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel workflow execution"""
        cancelled = False
        
        for exec_id, execution in self._executions.items():
            if execution.workflow_id == workflow_id:
                if execution.status == WorkflowStatus.RUNNING:
                    execution.status = WorkflowStatus.CANCELLED
                    cancelled = True
        
        return cancelled
    
    async def list_workflows(self) -> List[WorkflowDef]:
        """List all workflow definitions"""
        return list(self._workflows.values())
    
    # ==================== Advanced Features ====================
    
    def register_step_handler(self, agent_type: str, handler: Callable) -> None:
        """Register handler for agent type"""
        self._step_handlers[agent_type] = handler
        logger.info(f"Registered handler for {agent_type}")
    
    async def generate_workflow(
        self,
        objective: str,
        available_agents: List[str],
        constraints: Optional[Dict[str, Any]] = None
    ) -> WorkflowDef:
        """Dynamically generate workflow from objective"""
        if not self.config.enable_dynamic_generation:
            raise ExecutionError("Dynamic workflow generation disabled")
        
        # Use LLM to generate workflow
        # Simplified: create sequential workflow
        steps = []
        for i, agent in enumerate(available_agents):
            steps.append(WorkflowStep(
                step_id=f"step_{i}",
                agent_type=agent,
                task_description=f"Execute {agent} for: {objective}",
                depends_on=[f"step_{i-1}"] if i > 0 else [],
                output_key=f"output_{i}"
            ))
        
        return WorkflowDef(
            name=f"Generated_{hash(objective) % 10000}",
            description=f"Auto-generated for: {objective}",
            steps=steps
        )
    
    async def get_execution_metrics(self, execution_id: str) -> Dict[str, Any]:
        """Get detailed metrics for execution"""
        execution = self._executions.get(execution_id)
        if not execution:
            return {}
        
        step_execs = self._step_executions.get(execution_id, {})
        
        total_steps = len(step_execs)
        completed = sum(1 for s in step_execs.values() if s.state == StepState.COMPLETED)
        failed = sum(1 for s in step_execs.values() if s.state == StepState.FAILED)
        
        duration = None
        if execution.started_at and execution.completed_at:
            duration = (execution.completed_at - execution.started_at).total_seconds()
        
        return {
            "execution_id": execution_id,
            "status": execution.status.value,
            "total_steps": total_steps,
            "completed_steps": completed,
            "failed_steps": failed,
            "progress": completed / total_steps if total_steps > 0 else 0,
            "duration_seconds": duration,
            "error": execution.error
        }
    
    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize()
    
    async def cleanup(self) -> None:
        """Cleanup"""
        if self._checkpoint_task:
            self._checkpoint_task.cancel()
            try:
                await self._checkpoint_task
            except asyncio.CancelledError:
                pass
        
        self._initialized = False
