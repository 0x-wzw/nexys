"""
Adapter package for Unified Agentic Platform.

Available adapters:
- SwarmWeaver: NecroSwarm workforce coordination
- NeuroWeaver: NeuroSwarm dual-phase Brain+Swarm
- ObliviarchAdapter: Memory compression with 500x reduction
- VoidTetherAdapter: Universal interoperability mesh
- NamespaceAdapter: Workflow orchestration engine
- MemoryEvolutionAdapter: Self-improving memory system
- DeterministicRetrievalAdapter: Predictable path-based retrieval
"""

from .swarmweaver import SwarmWeaver, NecroSwarmConfig, SwarmAgent
from .neuroweaver import NeuroWeaver, NeuroSwarmConfig
from .obliviarch_adapter import ObliviarchAdapter, ObliviarchConfig
from .voidtether_adapter import VoidTetherAdapter, VoidTetherConfig
from .namespace_adapter import NamespaceAdapter, NamespaceConfig
from .memory_evolution_adapter import MemoryEvolutionAdapter, EvolutionConfig
from .deterministic_retrieval_adapter import DeterministicRetrievalAdapter, DeterministicConfig

from .hermes_adapter import HermesAdapter, HermesConfig

__all__ = [
    "SwarmWeaver",
    "NecroSwarmConfig",
    "SwarmAgent",
    "NeuroWeaver",
    "NeuroSwarmConfig",
    "ObliviarchAdapter",
    "ObliviarchConfig",
    "VoidTetherAdapter",
    "VoidTetherConfig",
    "NamespaceAdapter",
    "NamespaceConfig",
    "MemoryEvolutionAdapter",
    "EvolutionConfig",
    "DeterministicRetrievalAdapter",
    "DeterministicConfig",
    "HermesAdapter",
    "HermesConfig"
]
