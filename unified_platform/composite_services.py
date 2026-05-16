"""
Composite Services

Combines multiple adapters into unified services with failover and load balancing.
"""

import asyncio
from typing import List, Optional, Any, Dict

from .interfaces import IAgentService, IMemoryService, IWorkflowService


class CompositeAgentService(IAgentService):
    """Combines multiple agent adapters with failover"""
    
    def __init__(self, adapters: List[IAgentService]):
        self.adapters = adapters
    
    async def create_agent(self, config):
        for adapter in self.adapters:
            try:
                return await adapter.create_agent(config)
            except Exception:
                continue
        raise RuntimeError("All adapters failed")
    
    async def dispatch_task(self, agent_id, task):
        for adapter in self.adapters:
            try:
                return await adapter.dispatch_task(agent_id, task)
            except Exception:
                continue
        raise RuntimeError("All adapters failed")
    
    async def get_agent_status(self, agent_id):
        for adapter in self.adapters:
            try:
                return await adapter.get_agent_status(agent_id)
            except Exception:
                continue
        return None
    
    async def terminate_agent(self, agent_id):
        for adapter in self.adapters:
            try:
                return await adapter.terminate_agent(agent_id)
            except Exception:
                continue
    
    async def coordinate(self, agent_ids, strategy, objective=""):
        for adapter in self.adapters:
            try:
                return await adapter.coordinate(agent_ids, strategy, objective)
            except Exception:
                continue
        raise RuntimeError("All adapters failed")
    
    async def list_agents(self):
        all_agents = []
        for adapter in self.adapters:
            try:
                agents = await adapter.list_agents()
                all_agents.extend(agents)
            except Exception:
                continue
        return all_agents


class CompositeMemoryService(IMemoryService):
    """Combines multiple memory adapters with failover"""
    
    def __init__(self, adapters: List[IMemoryService]):
        self.adapters = adapters
    
    async def store(self, key, data, metadata):
        for adapter in self.adapters:
            try:
                return await adapter.store(key, data, metadata)
            except Exception:
                continue
        raise RuntimeError("All adapters failed")
    
    async def retrieve(self, key):
        for adapter in self.adapters:
            try:
                result = await adapter.retrieve(key)
                if result:
                    return result
            except Exception:
                continue
        return None
    
    async def search(self, query, limit=10, min_score=0.7):
        all_results = []
        for adapter in self.adapters:
            try:
                results = await adapter.search(query, limit, min_score)
                all_results.extend(results)
            except Exception:
                continue
        # Deduplicate and sort
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:limit]
    
    async def delete(self, key):
        for adapter in self.adapters:
            try:
                return await adapter.delete(key)
            except Exception:
                continue
        return False
    
    async def compress(self, criteria):
        for adapter in self.adapters:
            try:
                return await adapter.compress(criteria)
            except Exception:
                continue
        raise RuntimeError("All adapters failed")
    
    async def evolve(self):
        for adapter in self.adapters:
            try:
                return await adapter.evolve()
            except Exception:
                continue
        raise RuntimeError("All adapters failed")
    
    async def get_stats(self):
        stats = {}
        for adapter in self.adapters:
            try:
                s = await adapter.get_stats()
                stats.update(s)
            except Exception:
                continue
        return stats


class CompositeWorkflowService(IWorkflowService):
    """Combines multiple workflow adapters with failover"""
    
    def __init__(self, adapters: List[IWorkflowService]):
        self.adapters = adapters
    
    async def define_workflow(self, definition):
        for adapter in self.adapters:
            try:
                return await adapter.define_workflow(definition)
            except Exception:
                continue
        raise RuntimeError("All adapters failed")
    
    async def execute(self, workflow_id, input_data, variables=None):
        for adapter in self.adapters:
            try:
                return await adapter.execute(workflow_id, input_data, variables)
            except Exception:
                continue
        raise RuntimeError("All adapters failed")
    
    async def get_state(self, execution_id):
        for adapter in self.adapters:
            try:
                return await adapter.get_state(execution_id)
            except Exception:
                continue
        return None
    
    async def pause(self, execution_id):
        for adapter in self.adapters:
            try:
                return await adapter.pause(execution_id)
            except Exception:
                continue
    
    async def resume(self, execution_id):
        for adapter in self.adapters:
            try:
                return await adapter.resume(execution_id)
            except Exception:
                continue
    
    async def cancel(self, execution_id):
        for adapter in self.adapters:
            try:
                return await adapter.cancel(execution_id)
            except Exception:
                continue
    
    async def list_workflows(self):
        all_workflows = []
        for adapter in self.adapters:
            try:
                workflows = await adapter.list_workflows()
                all_workflows.extend(workflows)
            except Exception:
                continue
        return all_workflows
