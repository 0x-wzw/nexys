"""
Adapter Manager

Handles adapter lifecycle, health monitoring, and failover.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from .interfaces import IAgentService, IMemoryService, IWorkflowService

logger = logging.getLogger(__name__)


class AdapterStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


@dataclass
class AdapterHealth:
    """Health status of an adapter"""
    name: str
    status: AdapterStatus
    last_check: datetime
    latency_ms: float
    error_count: int
    success_count: int
    error_message: Optional[str] = None


class AdapterManager:
    """
    Manages adapter instances with health monitoring and failover.
    
    Usage:
        manager = AdapterManager()
        await manager.initialize_adapters(["necroswarm", "obliviarch"])
        
        # Health check
        health = await manager.check_health()
        
        # Get best available adapter
        adapter = manager.get_best_adapter("agent")
    """
    
    def __init__(self, registry=None):
        from .service_registry import get_registry
        self.registry = registry or get_registry()
        
        self._adapters: Dict[str, Any] = {}
        self._health: Dict[str, AdapterHealth] = {}
        self._health_check_interval = 30  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable] = []
        
        # Failover configuration
        self._primary_adapters: Dict[str, str] = {}
        self._failover_chain: Dict[str, List[str]] = {}
    
    async def initialize_adapters(
        self, 
        agent_adapters: Optional[List[str]] = None,
        memory_adapters: Optional[List[str]] = None,
        workflow_adapters: Optional[List[str]] = None,
        configs: Optional[Dict[str, Dict]] = None
    ) -> None:
        """Initialize specified adapters"""
        configs = configs or {}
        
        # Initialize agent adapters
        if agent_adapters:
            for name in agent_adapters:
                adapter = self.registry.get_agent_service(
                    name, 
                    configs.get(name),
                    create_new=True
                )
                if adapter:
                    self._adapters[f"agent:{name}"] = adapter
                    self._health[f"agent:{name}"] = AdapterHealth(
                        name=name,
                        status=AdapterStatus.HEALTHY,
                        last_check=datetime.now(),
                        latency_ms=0,
                        error_count=0,
                        success_count=0
                    )
                    logger.info(f"Initialized agent adapter: {name}")
        
        # Initialize memory adapters
        if memory_adapters:
            for name in memory_adapters:
                adapter = self.registry.get_memory_service(
                    name,
                    configs.get(name),
                    create_new=True
                )
                if adapter:
                    self._adapters[f"memory:{name}"] = adapter
                    self._health[f"memory:{name}"] = AdapterHealth(
                        name=name,
                        status=AdapterStatus.HEALTHY,
                        last_check=datetime.now(),
                        latency_ms=0,
                        error_count=0,
                        success_count=0
                    )
                    logger.info(f"Initialized memory adapter: {name}")
        
        # Initialize workflow adapters
        if workflow_adapters:
            for name in workflow_adapters:
                adapter = self.registry.get_workflow_service(
                    name,
                    configs.get(name),
                    create_new=True
                )
                if adapter:
                    self._adapters[f"workflow:{name}"] = adapter
                    self._health[f"workflow:{name}"] = AdapterHealth(
                        name=name,
                        status=AdapterStatus.HEALTHY,
                        last_check=datetime.now(),
                        latency_ms=0,
                        error_count=0,
                        success_count=0
                    )
                    logger.info(f"Initialized workflow adapter: {name}")
    
    async def start_health_monitoring(self) -> None:
        """Start periodic health checks"""
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(
                self._health_check_loop()
            )
            logger.info("Started health monitoring")
    
    async def stop_health_monitoring(self) -> None:
        """Stop health monitoring"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Stopped health monitoring")
    
    async def _health_check_loop(self) -> None:
        """Background task for health checks"""
        while True:
            try:
                await self.check_health()
                await asyncio.sleep(self._health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(self._health_check_interval)
    
    async def check_health(self) -> Dict[str, AdapterHealth]:
        """Check health of all adapters"""
        for key, adapter in self._adapters.items():
            start = datetime.now()
            
            try:
                # Adapter-specific health check
                if key.startswith("agent:"):
                    await self._check_agent_health(adapter)
                elif key.startswith("memory:"):
                    await self._check_memory_health(adapter)
                elif key.startswith("workflow:"):
                    await self._check_workflow_health(adapter)
                
                latency = (datetime.now() - start).total_seconds() * 1000
                
                # Update health status
                health = self._health[key]
                health.latency_ms = latency
                health.last_check = datetime.now()
                health.success_count += 1
                
                # Determine status based on latency and errors
                if latency < 100:  # < 100ms
                    if health.error_count > 5:
                        health.status = AdapterStatus.DEGRADED
                    else:
                        health.status = AdapterStatus.HEALTHY
                elif latency < 500:  # < 500ms
                    health.status = AdapterStatus.DEGRADED
                else:
                    health.status = AdapterStatus.UNHEALTHY
                
                health.error_message = None
                
            except Exception as e:
                health = self._health[key]
                health.error_count += 1
                health.status = AdapterStatus.UNHEALTHY
                health.error_message = str(e)
                health.last_check = datetime.now()
                
                logger.warning(f"Health check failed for {key}: {e}")
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self._health)
            except Exception as e:
                logger.error(f"Health callback error: {e}")
        
        return self._health
    
    async def _check_agent_health(self, adapter: IAgentService) -> None:
        """Health check for agent adapters"""
        # Try to list agents (lightweight operation)
        await adapter.list_agents()
    
    async def _check_memory_health(self, adapter: IMemoryService) -> None:
        """Health check for memory adapters"""
        # Try to get stats (lightweight operation)
        await adapter.get_stats()
    
    async def _check_workflow_health(self, adapter: IWorkflowService) -> None:
        """Health check for workflow adapters"""
        # Try to list workflows (lightweight operation)
        await adapter.list_workflows()
    
    def get_best_adapter(
        self, 
        category: str,
        exclude: Optional[List[str]] = None
    ) -> Optional[Any]:
        """Get the best available adapter based on health"""
        exclude = exclude or []
        
        # Get all adapters in category
        candidates = [
            (key, self._health[key]) 
            for key in self._adapters.keys() 
            if key.startswith(f"{category}:") and key not in exclude
        ]
        
        if not candidates:
            return None
        
        # Sort by health status and latency
        def health_score(item):
            key, health = item
            status_score = {
                AdapterStatus.HEALTHY: 3,
                AdapterStatus.DEGRADED: 2,
                AdapterStatus.UNHEALTHY: 1,
                AdapterStatus.OFFLINE: 0
            }.get(health.status, 0)
            
            # Higher score = better, lower latency = better
            return (status_score, -health.latency_ms)
        
        candidates.sort(key=health_score, reverse=True)
        
        best_key, best_health = candidates[0]
        
        if best_health.status == AdapterStatus.OFFLINE:
            return None
        
        return self._adapters[best_key]
    
    def get_adapter_health(self, key: str) -> Optional[AdapterHealth]:
        """Get health status of a specific adapter"""
        return self._health.get(key)
    
    def get_all_health(self) -> Dict[str, AdapterHealth]:
        """Get health status of all adapters"""
        return self._health.copy()
    
    def on_health_change(self, callback: Callable) -> None:
        """Register a callback for health status changes"""
        self._callbacks.append(callback)
    
    def set_failover_chain(
        self, 
        category: str, 
        chain: List[str]
    ) -> None:
        """Set failover priority for a category"""
        if chain:
            self._primary_adapters[category] = chain[0]
            self._failover_chain[category] = chain
    
    async def execute_with_failover(
        self,
        category: str,
        operation: Callable,
        max_retries: int = 3
    ) -> Any:
        """Execute an operation with automatic failover"""
        chain = self._failover_chain.get(category, [])
        
        if not chain:
            # No failover configured, use best available
            adapter = self.get_best_adapter(category)
            if not adapter:
                raise RuntimeError(f"No available adapters for {category}")
            return await operation(adapter)
        
        # Try each adapter in the chain
        last_error = None
        for adapter_name in chain:
            adapter_key = f"{category}:{adapter_name}"
            adapter = self._adapters.get(adapter_key)
            
            if not adapter:
                continue
            
            health = self._health.get(adapter_key)
            if health and health.status == AdapterStatus.OFFLINE:
                continue
            
            try:
                result = await operation(adapter)
                
                # Mark as successful
                if health:
                    health.success_count += 1
                
                return result
                
            except Exception as e:
                last_error = e
                
                # Mark as failed
                if health:
                    health.error_count += 1
                
                logger.warning(
                    f"Operation failed on {adapter_name}: {e}. "
                    f"Trying next in chain..."
                )
        
        # All adapters failed
        raise RuntimeError(
            f"All adapters in failover chain failed. "
            f"Last error: {last_error}"
        )
    
    async def shutdown(self) -> None:
        """Gracefully shutdown all adapters"""
        await self.stop_health_monitoring()
        
        # Cleanup adapters
        for key, adapter in self._adapters.items():
            try:
                # Call cleanup if available
                if hasattr(adapter, 'cleanup'):
                    await adapter.cleanup()
                elif hasattr(adapter, 'close'):
                    await adapter.close()
                    
                logger.info(f"Shutdown adapter: {key}")
            except Exception as e:
                logger.error(f"Error shutting down {key}: {e}")
        
        self._adapters.clear()
        self._health.clear()
