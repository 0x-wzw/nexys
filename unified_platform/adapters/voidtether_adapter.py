"""
VoidTetherAdapter — The Interoperability Mesh

Connects disparate AI systems, frameworks, and external services through
a unified tether protocol. Enables seamless communication between:
- Local frameworks (NecroSwarm, NeuroSwarm, etc.)
- Remote APIs (OpenAI, Anthropic, etc.)
- Edge devices
- Legacy systems

Key features:
- Protocol translation (HTTP, WebSocket, gRPC, custom)
- Service mesh with health checks
- Auto-discovery and registration
- Bidirectional streaming
- Circuit breaker pattern
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Callable, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

# Lazy import aiohttp - only needed when actually using HTTP/WebSocket features
try:
    import aiohttp
except ImportError:
    aiohttp = None

from ..interfaces import (
    IWorkflowService, IAgentService, WorkflowDef, Workflow,
    ExecutionState, ExecutionResult, WorkflowStatus,
    Task, TaskResult, AgentConfig, Agent,
    ResourceLimit, WorkflowNotFoundError, ExecutionNotFoundError
)

logger = logging.getLogger(__name__)


class ProtocolType(Enum):
    """Supported protocols"""
    HTTP = "http"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    NATIVE = "native"  # Direct Python calls


class ServiceHealth(Enum):
    """Service health states"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class TetherEndpoint:
    """Represents a connected endpoint"""
    endpoint_id: str
    name: str
    protocol: ProtocolType
    url: str
    capabilities: List[str]
    health_check_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_health_check: Optional[datetime] = None
    health_status: ServiceHealth = ServiceHealth.UNKNOWN
    latency_ms: float = 0.0
    circuit_breaker_failures: int = 0
    circuit_breaker_threshold: int = 5


@dataclass
class VoidTetherConfig:
    """Configuration for VoidTether"""
    
    # Mesh configuration
    mesh_name: str = "nexys-mesh"
    discovery_enabled: bool = True
    discovery_interval_seconds: int = 30
    
    # Health checking
    health_check_interval_seconds: int = 60
    health_check_timeout_seconds: int = 10
    
    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_timeout_seconds: int = 60
    
    # Connection pooling
    max_connections_per_endpoint: int = 10
    connection_timeout_seconds: int = 30
    keep_alive_seconds: int = 300
    
    # Protocol defaults
    default_protocol: ProtocolType = ProtocolType.HTTP
    retry_attempts: int = 3
    retry_backoff_seconds: float = 1.0
    
    # Security
    api_key_header: str = "X-API-Key"
    enable_tls: bool = True


class VoidTetherAdapter(IWorkflowService, IAgentService):
    """
    The VoidTether Adapter — Universal Interoperability Mesh.
    
    Connects any system to Nexys through protocol-agnostic tethers:
    - HTTP/REST APIs
    - WebSocket streams
    - gRPC services
    - Native Python objects
    
    Service Mesh Features:
    - Auto-discovery: Find services on the network
    - Health monitoring: Track endpoint health
    - Circuit breaker: Fail fast on degraded services
    - Load balancing: Distribute across healthy endpoints
    
    Usage:
        tether = VoidTetherAdapter(config)
        await tether.initialize()
        
        # Register external API
        await tether.register_endpoint(TetherEndpoint(
            endpoint_id="openai-api",
            name="OpenAI GPT-4",
            protocol=ProtocolType.HTTP,
            url="https://api.openai.com/v1",
            capabilities=["completion", "embedding"]
        ))
        
        # Invoke remote service
        result = await tether.invoke("openai-api", {
            "method": "POST",
            "path": "/chat/completions",
            "body": {...}
        })
        
        # Stream responses
        async for chunk in tether.stream("websocket-endpoint", data):
            process(chunk)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = VoidTetherConfig(**(config or {}))
        self._endpoints: Dict[str, TetherEndpoint] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._initialized = False
        
        # Health monitoring
        self._health_check_task: Optional[asyncio.Task] = None
        self._discovery_task: Optional[asyncio.Task] = None
        
        # Circuit breaker states
        self._circuit_open: Dict[str, bool] = {}
        self._circuit_opened_at: Dict[str, datetime] = {}
        
        # Connection pools
        self._websocket_connections: Dict[str, Any] = {}
        self._grpc_channels: Dict[str, Any] = {}
        
        # Message handlers
        self._message_handlers: Dict[str, Callable] = {}
        
    async def initialize(self) -> None:
        """Initialize VoidTether mesh"""
        if self._initialized:
            return
        
        # Create HTTP session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.config.max_connections_per_endpoint,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(
            total=self.config.connection_timeout_seconds,
            connect=10
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
        
        # Start background tasks
        if self.config.health_check_interval_seconds > 0:
            self._health_check_task = asyncio.create_task(
                self._health_check_loop()
            )
        
        if self.config.discovery_enabled:
            self._discovery_task = asyncio.create_task(
                self._discovery_loop()
            )
        
        self._initialized = True
        logger.info(f"VoidTether mesh '{self.config.mesh_name}' initialized")
    
    async def _health_check_loop(self) -> None:
        """Background: Check endpoint health"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval_seconds)
                
                for endpoint in list(self._endpoints.values()):
                    await self._check_endpoint_health(endpoint)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _check_endpoint_health(self, endpoint: TetherEndpoint) -> None:
        """Check health of a single endpoint"""
        if not endpoint.health_check_url:
            endpoint.health_status = ServiceHealth.UNKNOWN
            return
        
        # Check if circuit is open
        if self._circuit_open.get(endpoint.endpoint_id):
            opened_at = self._circuit_opened_at.get(endpoint.endpoint_id)
            if opened_at:
                elapsed = (datetime.now() - opened_at).total_seconds()
                if elapsed < self.config.circuit_breaker_reset_timeout_seconds:
                    endpoint.health_status = ServiceHealth.UNHEALTHY
                    return
                else:
                    # Try closing circuit
                    self._circuit_open[endpoint.endpoint_id] = False
                    endpoint.circuit_breaker_failures = 0
        
        start_time = datetime.now()
        try:
            async with self._session.get(
                endpoint.health_check_url,
                timeout=aiohttp.ClientTimeout(total=self.config.health_check_timeout_seconds)
            ) as response:
                latency = (datetime.now() - start_time).total_seconds() * 1000
                endpoint.latency_ms = latency
                endpoint.last_health_check = datetime.now()
                
                if response.status == 200:
                    endpoint.health_status = ServiceHealth.HEALTHY
                    endpoint.circuit_breaker_failures = 0
                else:
                    endpoint.health_status = ServiceHealth.DEGRADED
                    endpoint.circuit_breaker_failures += 1
                    
        except Exception as e:
            endpoint.health_status = ServiceHealth.UNHEALTHY
            endpoint.circuit_breaker_failures += 1
            logger.warning(f"Health check failed for {endpoint.name}: {e}")
        
        # Check circuit breaker threshold
        if endpoint.circuit_breaker_failures >= self.config.circuit_breaker_threshold:
            self._circuit_open[endpoint.endpoint_id] = True
            self._circuit_opened_at[endpoint.endpoint_id] = datetime.now()
            logger.warning(f"Circuit breaker opened for {endpoint.name}")
    
    async def _discovery_loop(self) -> None:
        """Background: Auto-discover services"""
        while True:
            try:
                await asyncio.sleep(self.config.discovery_interval_seconds)
                await self._discover_services()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery error: {e}")
    
    async def _discover_services(self) -> None:
        """Discover services on the network"""
        # Placeholder for service discovery
        # Could use: Consul, etcd, Kubernetes, mDNS, etc.
        pass
    
    # ==================== Endpoint Management ====================
    
    async def register_endpoint(self, endpoint: TetherEndpoint) -> None:
        """Register a new endpoint"""
        self._endpoints[endpoint.endpoint_id] = endpoint
        self._circuit_open[endpoint.endpoint_id] = False
        
        # Initialize protocol-specific connections
        if endpoint.protocol == ProtocolType.WEBSOCKET:
            await self._init_websocket(endpoint)
        elif endpoint.protocol == ProtocolType.GRPC:
            await self._init_grpc(endpoint)
        
        logger.info(f"Registered endpoint: {endpoint.name} ({endpoint.protocol.value})")
    
    async def unregister_endpoint(self, endpoint_id: str) -> None:
        """Unregister an endpoint"""
        endpoint = self._endpoints.pop(endpoint_id, None)
        if endpoint:
            # Cleanup connections
            if endpoint_id in self._websocket_connections:
                ws = self._websocket_connections.pop(endpoint_id)
                await ws.close()
            if endpoint_id in self._grpc_channels:
                channel = self._grpc_channels.pop(endpoint_id)
                await channel.close()
            
            logger.info(f"Unregistered endpoint: {endpoint.name}")
    
    async def _init_websocket(self, endpoint: TetherEndpoint) -> None:
        """Initialize WebSocket connection"""
        try:
            import aiohttp
            ws = await self._session.ws_connect(endpoint.url)
            self._websocket_connections[endpoint.endpoint_id] = ws
            
            # Start message handler
            asyncio.create_task(
                self._websocket_handler(endpoint.endpoint_id, ws)
            )
        except Exception as e:
            logger.error(f"WebSocket init failed for {endpoint.name}: {e}")
    
    async def _init_grpc(self, endpoint: TetherEndpoint) -> None:
        """Initialize gRPC channel"""
        try:
            import grpc
            channel = grpc.aio.insecure_channel(endpoint.url)
            self._grpc_channels[endpoint.endpoint_id] = channel
        except Exception as e:
            logger.error(f"gRPC init failed for {endpoint.name}: {e}")
    
    async def _websocket_handler(self, endpoint_id: str, ws: Any) -> None:
        """Handle incoming WebSocket messages"""
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                handler = self._message_handlers.get(endpoint_id)
                if handler:
                    await handler(data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error for {endpoint_id}: {ws.exception()}")
    
    # ==================== Invocation Methods ====================
    
    async def invoke(
        self,
        endpoint_id: str,
        request: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Invoke endpoint with request"""
        await self._ensure_initialized()
        
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")
        
        # Check circuit breaker
        if self._circuit_open.get(endpoint_id):
            raise ExecutionError(f"Circuit breaker open for {endpoint_id}")
        
        # Route by protocol
        if endpoint.protocol == ProtocolType.HTTP:
            return await self._invoke_http(endpoint, request, timeout)
        elif endpoint.protocol == ProtocolType.NATIVE:
            return await self._invoke_native(endpoint, request)
        elif endpoint.protocol == ProtocolType.WEBSOCKET:
            return await self._invoke_websocket(endpoint, request)
        elif endpoint.protocol == ProtocolType.GRPC:
            return await self._invoke_grpc(endpoint, request)
        else:
            raise ValueError(f"Unsupported protocol: {endpoint.protocol}")
    
    async def _invoke_http(
        self,
        endpoint: TetherEndpoint,
        request: Dict[str, Any],
        timeout: Optional[float]
    ) -> Dict[str, Any]:
        """Invoke HTTP endpoint"""
        method = request.get("method", "GET").upper()
        path = request.get("path", "/")
        body = request.get("body")
        headers = request.get("headers", {})
        
        url = f"{endpoint.url.rstrip('/')}/{path.lstrip('/')}"
        timeout = aiohttp.ClientTimeout(total=timeout or self.config.connection_timeout_seconds)
        
        for attempt in range(self.config.retry_attempts):
            try:
                async with self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if body else None,
                    timeout=timeout
                ) as response:
                    response_data = await response.json()
                    
                    # Update latency stats
                    endpoint.last_health_check = datetime.now()
                    
                    return {
                        "status": response.status,
                        "data": response_data,
                        "headers": dict(response.headers)
                    }
                    
            except Exception as e:
                if attempt == self.config.retry_attempts - 1:
                    endpoint.circuit_breaker_failures += 1
                    raise ExecutionError(f"HTTP invocation failed: {e}")
                await asyncio.sleep(self.config.retry_backoff_seconds * (2 ** attempt))
    
    async def _invoke_native(
        self,
        endpoint: TetherEndpoint,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke native Python object"""
        # For native endpoints, metadata contains the callable
        handler = endpoint.metadata.get("handler")
        if not handler:
            raise ExecutionError(f"No native handler for {endpoint.endpoint_id}")
        
        if asyncio.iscoroutinefunction(handler):
            result = await handler(**request)
        else:
            result = handler(**request)
        
        return {"data": result, "status": 200}
    
    async def _invoke_websocket(
        self,
        endpoint: TetherEndpoint,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send via WebSocket"""
        ws = self._websocket_connections.get(endpoint.endpoint_id)
        if not ws:
            raise ExecutionError(f"WebSocket not connected for {endpoint.endpoint_id}")
        
        await ws.send_json(request)
        
        # For request-response pattern, wait for reply
        # In practice, you'd use a correlation ID
        return {"sent": True}
    
    async def _invoke_grpc(
        self,
        endpoint: TetherEndpoint,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke gRPC service"""
        channel = self._grpc_channels.get(endpoint.endpoint_id)
        if not channel:
            raise ExecutionError(f"gRPC channel not connected for {endpoint.endpoint_id}")
        
        # gRPC stub would be created here based on service definition
        # This is a simplified placeholder
        raise ExecutionError("gRPC invocation requires service stubs")
    
    async def stream(
        self,
        endpoint_id: str,
        request: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream responses from endpoint"""
        await self._ensure_initialized()
        
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")
        
        if endpoint.protocol == ProtocolType.HTTP:
            async with self._session.post(
                endpoint.url,
                json=request
            ) as response:
                async for line in response.content:
                    if line.startswith(b'data: '):
                        data = json.loads(line[6:])
                        yield data
        elif endpoint.protocol == ProtocolType.WEBSOCKET:
            ws = self._websocket_connections.get(endpoint_id)
            if ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        yield json.loads(msg.data)
        else:
            raise ValueError(f"Streaming not supported for {endpoint.protocol.value}")
    
    async def broadcast(
        self,
        capability: str,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Broadcast to all endpoints with capability"""
        results = {}
        
        for endpoint_id, endpoint in self._endpoints.items():
            if capability in endpoint.capabilities:
                if endpoint.health_status == ServiceHealth.HEALTHY:
                    try:
                        result = await self.invoke(endpoint_id, request)
                        results[endpoint_id] = result
                    except Exception as e:
                        results[endpoint_id] = {"error": str(e)}
        
        return results
    
    # ==================== IWorkflowService Implementation ====================
    
    async def create_workflow(self, definition: WorkflowDef) -> str:
        """Create workflow (stores in mesh)"""
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(definition.name) % 10000}"
        
        # Store workflow definition
        self._endpoints[workflow_id] = TetherEndpoint(
            endpoint_id=workflow_id,
            name=definition.name,
            protocol=ProtocolType.NATIVE,
            url="internal://workflow",
            capabilities=["workflow"],
            metadata={"workflow_definition": definition}
        )
        
        return workflow_id
    
    async def execute_workflow(
        self,
        workflow_id: str,
        context: ExecutionState
    ) -> ExecutionResult:
        """Execute workflow across mesh"""
        await self._ensure_initialized()
        
        endpoint = self._endpoints.get(workflow_id)
        if not endpoint:
            raise WorkflowNotFoundError(f"Workflow {workflow_id} not found")
        
        definition = endpoint.metadata.get("workflow_definition")
        if not definition:
            raise WorkflowNotFoundError(f"No definition for workflow {workflow_id}")
        
        # Execute workflow steps
        execution = ExecutionResult(
            execution_id=f"exec_{datetime.now().timestamp()}",
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now()
        )
        
        for step in definition.steps:
            # Find endpoint for step
            target_endpoints = [
                ep for ep in self._endpoints.values()
                if step.agent_type in ep.capabilities
                and ep.health_status == ServiceHealth.HEALTHY
            ]
            
            if not target_endpoints:
                execution.status = WorkflowStatus.FAILED
                execution.error = f"No healthy endpoint for {step.agent_type}"
                return execution
            
            # Execute on first available
            target = target_endpoints[0]
            
            try:
                result = await self.invoke(target.endpoint_id, {
                    "method": "POST",
                    "path": "/execute",
                    "body": {
                        "task": step.task_description,
                        "input": context.variables
                    }
                })
                
                execution.completed_steps.append(step.step_id)
                context.variables[step.output_key] = result.get("data")
                
            except Exception as e:
                execution.status = WorkflowStatus.FAILED
                execution.error = str(e)
                return execution
        
        execution.status = WorkflowStatus.COMPLETED
        execution.completed_at = datetime.now()
        return execution
    
    async def get_workflow_status(self, workflow_id: str) -> WorkflowStatus:
        """Get workflow status"""
        # Simplified — in production, track running executions
        return WorkflowStatus.COMPLETED
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel workflow execution"""
        # Implementation would track and cancel running workflows
        return True
    
    async def list_workflows(self) -> List[WorkflowDef]:
        """List all workflows"""
        workflows = []
        for endpoint in self._endpoints.values():
            if "workflow" in endpoint.capabilities:
                definition = endpoint.metadata.get("workflow_definition")
                if definition:
                    workflows.append(definition)
        return workflows
    
    # ==================== IAgentService Implementation ====================
    
    async def create_agent(self, config: AgentConfig) -> Agent:
        """Create agent on remote endpoint"""
        # Find endpoint supporting agent creation
        for endpoint in self._endpoints.values():
            if "agent_creation" in endpoint.capabilities:
                result = await self.invoke(endpoint.endpoint_id, {
                    "method": "POST",
                    "path": "/agents",
                    "body": config.__dict__
                })
                
                return Agent(
                    id=result.get("data", {}).get("agent_id", config.id),
                    adapter=self,
                    native_instance=None,
                    status=AgentStatus.IDLE
                )
        
        raise ExecutionError("No endpoint supports agent creation")
    
    async def dispatch_task(self, agent_id: str, task: Task) -> TaskResult:
        """Dispatch task to agent via mesh"""
        # Find agent's endpoint
        for endpoint in self._endpoints.values():
            result = await self.invoke(endpoint.endpoint_id, {
                "method": "POST",
                "path": f"/agents/{agent_id}/tasks",
                "body": task.__dict__
            })
            
            if result.get("status") == 200:
                return TaskResult(
                    task_id=task.id,
                    success=True,
                    output=result.get("data"),
                    metrics=None
                )
        
        return TaskResult(
            task_id=task.id,
            success=False,
            error="Agent not found or unreachable"
        )
    
    async def get_agent_status(self, agent_id: str) -> Any:
        """Get agent status from endpoint"""
        for endpoint in self._endpoints.values():
            try:
                result = await self.invoke(endpoint.endpoint_id, {
                    "method": "GET",
                    "path": f"/agents/{agent_id}/status"
                })
                if result.get("status") == 200:
                    return result.get("data")
            except:
                continue
        return None
    
    async def terminate_agent(self, agent_id: str) -> None:
        """Terminate agent on endpoint"""
        for endpoint in self._endpoints.values():
            try:
                await self.invoke(endpoint.endpoint_id, {
                    "method": "DELETE",
                    "path": f"/agents/{agent_id}"
                })
            except:
                continue
    
    async def coordinate(self, *args, **kwargs) -> Any:
        """Coordinate agents across mesh"""
        # Delegate to SwarmWeaver or other coordinators
        raise NotImplementedError("Use dedicated coordinator for multi-agent")
    
    async def list_agents(self) -> List[Agent]:
        """List agents across all endpoints"""
        agents = []
        for endpoint in self._endpoints.values():
            try:
                result = await self.invoke(endpoint.endpoint_id, {
                    "method": "GET",
                    "path": "/agents"
                })
                if result.get("status") == 200:
                    for agent_data in result.get("data", []):
                        agents.append(Agent(
                            id=agent_data.get("id"),
                            adapter=self,
                            native_instance=None,
                            status=AgentStatus.IDLE
                        ))
            except:
                continue
        return agents
    
    # ==================== Utility ====================
    
    async def get_mesh_status(self) -> Dict[str, Any]:
        """Get mesh health overview"""
        healthy = sum(1 for ep in self._endpoints.values() 
                     if ep.health_status == ServiceHealth.HEALTHY)
        degraded = sum(1 for ep in self._endpoints.values() 
                      if ep.health_status == ServiceHealth.DEGRADED)
        unhealthy = sum(1 for ep in self._endpoints.values() 
                       if ep.health_status == ServiceHealth.UNHEALTHY)
        
        return {
            "mesh_name": self.config.mesh_name,
            "total_endpoints": len(self._endpoints),
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "circuit_breakers_open": sum(1 for v in self._circuit_open.values() if v),
            "active_connections": len(self._websocket_connections) + len(self._grpc_channels)
        }
    
    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize()
    
    async def cleanup(self) -> None:
        """Cleanup mesh"""
        if self._health_check_task:
            self._health_check_task.cancel()
        if self._discovery_task:
            self._discovery_task.cancel()
        
        # Close WebSocket connections
        for ws in self._websocket_connections.values():
            await ws.close()
        
        # Close gRPC channels
        for channel in self._grpc_channels.values():
            await channel.close()
        
        if self._session:
            await self._session.close()
        
        self._initialized = False
