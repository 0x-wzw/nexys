"""
Adapter package for Unified Agentic Platform.

Available adapters:
- SwarmWeaver: NecroSwarm workforce coordination
- (More coming: NeuroWeaver, ObliviarchAdapter, VoidTetherAdapter, etc.)
"""

from .swarmweaver import SwarmWeaver, NecroSwarmConfig, SwarmAgent

__all__ = [
    "SwarmWeaver",
    "NecroSwarmConfig",
    "SwarmAgent"
]
