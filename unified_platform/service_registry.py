"""
Service Registry for Unified Platform

Manages adapter discovery, registration, and lifecycle.
"""

import importlib
import logging
from typing import Dict, List, Optional, Type, Any
from pathlib import Path

from .interfaces import IAgentService, IMemoryService, IWorkflowService

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Central registry for all framework adapters.
    
    Usage:
        registry = ServiceRegistry()
        registry.discover_adapters()
        
        agent_service = registry.get_agent_service("necroswarm")
        memory_service = registry.get_memory_service("obliviarch")
    """
    
    def __init__(self):
        self._agent_adapters: Dict[str, Type[IAgentService]] = {}
        self._memory_adapters: Dict[str, Type[IMemoryService]] = {}
        self._workflow_adapters: Dict[str, Type[IWorkflowService]] = {}
        self._adapter_instances: Dict[str, Any] = {}
        
        # Known adapter mappings
        self._adapter_map = {
            # Agent Services
            "swarmweaver": ("adapters.swarmweaver", "SwarmWeaver"),
            "necroswarm": ("adapters.swarmweaver", "SwarmWeaver"),  # Alias
            "neuroswarm": ("adapters.neuroswarm_adapter", "NeuroSwarmAdapter"),
            
            # Memory Services
            "obliviarch": ("adapters.obliviarch_adapter", "ObliviarchAdapter"),
            "memory_evolution": ("adapters.memory_evolution_adapter", "MemoryEvolutionAdapter"),
            
            # Workflow Services
            "namespace": ("adapters.namespace_adapter", "NamespaceAdapter"),
            "deterministic_retrieval": ("adapters.deterministic_retrieval_adapter", "DeterministicRetrievalAdapter"),
            
            # Integration
            "voidtether": ("adapters.voidtether_adapter", "VoidTetherAdapter"),
        }
        
        # Auto-register built-in adapters
        self._register_builtin_adapters()
    
    def _register_builtin_adapters(self) -> None:
        """Auto-register built-in adapters that are available"""
        # Agent Service Adapters
        try:
            from .adapters.swarmweaver import SwarmWeaver
            self.register_agent_adapter("swarmweaver", SwarmWeaver)
            self.register_agent_adapter("necroswarm", SwarmWeaver)  # Alias
            logger.info("Registered: SwarmWeaver (necroswarm)")
        except ImportError as e:
            logger.debug(f"SwarmWeaver not available: {e}")
        
        try:
            from .adapters.neuroweaver import NeuroWeaver
            self.register_agent_adapter("neuroweaver", NeuroWeaver)
            self.register_agent_adapter("neuroswarm", NeuroWeaver)  # Alias
            logger.info("Registered: NeuroWeaver (neuroswarm)")
        except ImportError as e:
            logger.debug(f"NeuroWeaver not available: {e}")
        
        try:
            from .adapters.voidtether_adapter import VoidTetherAdapter
            self.register_agent_adapter("voidtether", VoidTetherAdapter)
            self.register_workflow_adapter("voidtether", VoidTetherAdapter)
            logger.info("Registered: VoidTetherAdapter (agent + workflow)")
        except ImportError as e:
            logger.debug(f"VoidTetherAdapter not available: {e}")
        
        # Memory Service Adapters
        try:
            from .adapters.obliviarch_adapter import ObliviarchAdapter
            self.register_memory_adapter("obliviarch", ObliviarchAdapter)
            logger.info("Registered: ObliviarchAdapter")
        except ImportError as e:
            logger.debug(f"ObliviarchAdapter not available: {e}")
        
        try:
            from .adapters.memory_evolution_adapter import MemoryEvolutionAdapter
            self.register_memory_adapter("memory_evolution", MemoryEvolutionAdapter)
            logger.info("Registered: MemoryEvolutionAdapter")
        except ImportError as e:
            logger.debug(f"MemoryEvolutionAdapter not available: {e}")
        
        try:
            from .adapters.deterministic_retrieval_adapter import DeterministicRetrievalAdapter
            self.register_memory_adapter("deterministic_retrieval", DeterministicRetrievalAdapter)
            logger.info("Registered: DeterministicRetrievalAdapter")
        except ImportError as e:
            logger.debug(f"DeterministicRetrievalAdapter not available: {e}")
        
        # Workflow Service Adapters
        try:
            from .adapters.namespace_adapter import NamespaceAdapter
            self.register_workflow_adapter("namespace", NamespaceAdapter)
            logger.info("Registered: NamespaceAdapter")
        except ImportError as e:
            logger.debug(f"NamespaceAdapter not available: {e}")
        
        # Hermes agent service
        try:
            from .adapters.hermes_adapter import HermesAdapter
            self.register_agent_adapter("hermes", HermesAdapter)
            logger.info("Registered: HermesAdapter")
        except ImportError as e:
            logger.debug(f"HermesAdapter not available: {e}")
        
        # Composite adapters (implement multiple interfaces)
        # NeuroWeaver also implements IMemoryService
        try:
            from .adapters.neuroweaver import NeuroWeaver
            self.register_memory_adapter("neuroswarm_memory", NeuroWeaver)
            logger.info("Registered: NeuroWeaver as memory adapter")
        except ImportError:
            pass
        
        # VoidTether also implements IWorkflowService
        try:
            from .adapters.voidtether_adapter import VoidTetherAdapter
            self.register_workflow_adapter("voidtether_workflow", VoidTetherAdapter)
            logger.info("Registered: VoidTetherAdapter as workflow adapter")
        except ImportError:
            pass
    
    def register_agent_adapter(
        self, 
        name: str, 
        adapter_class: Type[IAgentService]
    ) -> None:
        """Register an agent service adapter"""
        if not issubclass(adapter_class, IAgentService):
            raise ValueError(f"{adapter_class} must implement IAgentService")
        
        self._agent_adapters[name] = adapter_class
        logger.info(f"Registered agent adapter: {name}")
    
    def register_memory_adapter(
        self, 
        name: str, 
        adapter_class: Type[IMemoryService]
    ) -> None:
        """Register a memory service adapter"""
        if not issubclass(adapter_class, IMemoryService):
            raise ValueError(f"{adapter_class} must implement IMemoryService")
        
        self._memory_adapters[name] = adapter_class
        logger.info(f"Registered memory adapter: {name}")
    
    def register_workflow_adapter(
        self, 
        name: str, 
        adapter_class: Type[IWorkflowService]
    ) -> None:
        """Register a workflow service adapter"""
        if not issubclass(adapter_class, IWorkflowService):
            raise ValueError(f"{adapter_class} must implement IWorkflowService")
        
        self._workflow_adapters[name] = adapter_class
        logger.info(f"Registered workflow adapter: {name}")
    
    def discover_adapters(self) -> None:
        """Auto-discover and load all available adapters"""
        adapters_dir = Path(__file__).parent / "adapters"
        
        if not adapters_dir.exists():
            logger.warning(f"Adapters directory not found: {adapters_dir}")
            return
        
        # Look for adapter modules
        for file_path in adapters_dir.glob("*_adapter.py"):
            module_name = file_path.stem
            full_module = f"unified_platform.adapters.{module_name}"
            
            try:
                module = importlib.import_module(full_module)
                
                # Look for adapter classes
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and attr_name.endswith("Adapter"):
                        self._try_register_adapter(attr_name, attr)
                        
            except ImportError as e:
                logger.warning(f"Could not import {full_module}: {e}")
    
    def _try_register_adapter(self, name: str, adapter_class: Type) -> None:
        """Try to register an adapter based on its implemented protocols"""
        try:
            # Check what protocols it implements
            if issubclass(adapter_class, IAgentService):
                self.register_agent_adapter(name.lower().replace("adapter", ""), adapter_class)
            elif issubclass(adapter_class, IMemoryService):
                self.register_memory_adapter(name.lower().replace("adapter", ""), adapter_class)
            elif issubclass(adapter_class, IWorkflowService):
                self.register_workflow_adapter(name.lower().replace("adapter", ""), adapter_class)
        except Exception as e:
            logger.debug(f"Could not register {name}: {e}")
    
    def get_agent_service(
        self, 
        name: str, 
        config: Optional[Dict] = None,
        create_new: bool = False
    ) -> Optional[IAgentService]:
        """Get or create an agent service adapter"""
        instance_key = f"agent:{name}"
        
        if not create_new and instance_key in self._adapter_instances:
            return self._adapter_instances[instance_key]
        
        if name not in self._agent_adapters:
            logger.error(f"Agent adapter not found: {name}")
            return None
        
        adapter_class = self._agent_adapters[name]
        instance = adapter_class(config or {})
        self._adapter_instances[instance_key] = instance
        
        return instance
    
    def get_memory_service(
        self, 
        name: str, 
        config: Optional[Dict] = None,
        create_new: bool = False
    ) -> Optional[IMemoryService]:
        """Get or create a memory service adapter"""
        instance_key = f"memory:{name}"
        
        if not create_new and instance_key in self._adapter_instances:
            return self._adapter_instances[instance_key]
        
        if name not in self._memory_adapters:
            logger.error(f"Memory adapter not found: {name}")
            return None
        
        adapter_class = self._memory_adapters[name]
        instance = adapter_class(config or {})
        self._adapter_instances[instance_key] = instance
        
        return instance
    
    def get_workflow_service(
        self, 
        name: str, 
        config: Optional[Dict] = None,
        create_new: bool = False
    ) -> Optional[IWorkflowService]:
        """Get or create a workflow service adapter"""
        instance_key = f"workflow:{name}"
        
        if not create_new and instance_key in self._adapter_instances:
            return self._adapter_instances[instance_key]
        
        if name not in self._workflow_adapters:
            logger.error(f"Workflow adapter not found: {name}")
            return None
        
        adapter_class = self._workflow_adapters[name]
        instance = adapter_class(config or {})
        self._adapter_instances[instance_key] = instance
        
        return instance
    
    def list_adapters(self) -> Dict[str, List[str]]:
        """List all registered adapters by category"""
        return {
            "agent": list(self._agent_adapters.keys()),
            "memory": list(self._memory_adapters.keys()),
            "workflow": list(self._workflow_adapters.keys())
        }
    
    def create_composite_agent_service(
        self, 
        adapter_names: List[str],
        config: Optional[Dict] = None
    ) -> "CompositeAgentService":
        """Create a composite service using multiple adapters"""
        from .composite_services import CompositeAgentService
        
        adapters = []
        for name in adapter_names:
            adapter = self.get_agent_service(name, config)
            if adapter:
                adapters.append(adapter)
        
        return CompositeAgentService(adapters)
    
    def create_composite_memory_service(
        self, 
        adapter_names: List[str],
        config: Optional[Dict] = None
    ) -> "CompositeMemoryService":
        """Create a composite memory service using multiple adapters"""
        from .composite_services import CompositeMemoryService
        
        adapters = []
        for name in adapter_names:
            adapter = self.get_memory_service(name, config)
            if adapter:
                adapters.append(adapter)
        
        return CompositeMemoryService(adapters)


# Singleton instance
_registry: Optional[ServiceRegistry] = None


def get_registry() -> ServiceRegistry:
    """Get the global service registry"""
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry
