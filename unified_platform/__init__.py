"""
Unified Agentic AI Platform

A consolidated framework combining the best of:
- NecroSwarm (workforce coordination)
- NeuroSwarm (brain + swarm dual-phase)
- Obliviarch (memory compression)
- VoidTether (interoperability mesh)
- OpenClaw ecosystem (namespace, memory, retrieval)

Usage:
    from unified_platform import AgentService, MemoryService, WorkflowService
    
    agent_svc = AgentService.create_with_adapters(["necroswarm", "neuroswarm"])
    memory_svc = MemoryService.create_with_adapters(["obliviarch", "memory_evolution"])
"""

__version__ = "0.1.0"
__author__ = "0x-wzw"

from .interfaces import (
    IAgentService,
    IMemoryService,
    IWorkflowService,
    AgentConfig,
    Agent,
    Task,
    TaskResult,
    MemoryEntry,
    SearchResult,
    Workflow,
    WorkflowDef,
    ExecutionResult
)

from .service_registry import ServiceRegistry
from .adapter_manager import AdapterManager

__all__ = [
    "IAgentService",
    "IMemoryService", 
    "IWorkflowService",
    "AgentConfig",
    "Agent",
    "Task",
    "TaskResult",
    "MemoryEntry",
    "SearchResult",
    "Workflow",
    "WorkflowDef",
    "ExecutionResult",
    "ServiceRegistry",
    "AdapterManager"
]
