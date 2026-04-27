"""
Tests for SwarmWeaver adapter.

Run: pytest tests/test_swarmweaver.py -v
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/platform-consolidation')

from unified_platform.interfaces import (
    AgentConfig, Task, TaskPriority, ResourceLimit,
    CoordinationStrategy, AgentStatus
)
from unified_platform.adapters.swarmweaver import (
    SwarmWeaver, NecroSwarmConfig, SwarmAgent
)


class TestNecroSwarmConfig:
    """Test configuration class"""
    
    def test_default_config(self):
        config = NecroSwarmConfig()
        assert config.council_size == 10
        assert config.consensus_threshold == 0.7
        assert config.enable_token_economics is True
        
    def test_custom_config(self):
        config = NecroSwarmConfig(
            council_size=5,
            consensus_threshold=0.8,
            enable_token_economics=False
        )
        assert config.council_size == 5
        assert config.consensus_threshold == 0.8
        assert config.enable_token_economics is False
        
    def test_to_necroswarm_dict(self):
        config = NecroSwarmConfig()
        result = config.to_necroswarm_dict()
        
        assert result["council"]["size"] == 10
        assert result["council"]["consensus_threshold"] == 0.7
        assert result["token_economics"] is True


class TestSwarmWeaver:
    """Test SwarmWeaver adapter"""
    
    @pytest.fixture
    def weaver(self):
        return SwarmWeaver({
            "council_size": 5,
            "redis_url": "redis://test:6379"
        })
    
    @pytest.fixture
    def mock_necroswarm(self):
        """Create mock NecroSwarm"""
        mock = Mock()
        mock.initialize = AsyncMock()
        mock.spawn_agent = AsyncMock(return_value=Mock(
            status='idle',
            id='test-agent-1'
        ))
        mock.terminate_agent = AsyncMock()
        mock.execute_task = AsyncMock(return_value={
            "status": "completed",
            "output": "Task completed successfully",
            "tokens_used": 100,
            "latency_ms": 50.0,
            "cost": 0.001,
            "cache_hit": False
        })
        mock.council_deliberate = AsyncMock(return_value=Mock(
            consensus_reached=True,
            decision="Proceed with Plan A",
            votes={"agent1": "Plan A", "agent2": "Plan A"},
            confidence=0.95,
            dissenters=[]
        ))
        mock.get_agent_status = AsyncMock(return_value={"status": "idle"})
        mock.enable_acs = AsyncMock()
        mock.enable_acp = AsyncMock()
        mock.rebalance_resources = AsyncMock()
        mock.shutdown = AsyncMock()
        return mock
    
    @pytest.mark.asyncio
    async def test_initialization(self, weaver, mock_necroswarm):
        """Test SwarmWeaver initialization"""
        with patch('necroswarm.SwarmController', return_value=mock_necroswarm):
            await weaver.initialize()
            
            assert weaver._initialized is True
            assert weaver._necroswarm is not None
            mock_necroswarm.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_agent(self, weaver, mock_necroswarm):
        """Test agent creation"""
        with patch('necroswarm.SwarmController', return_value=mock_necroswarm):
            await weaver.initialize()
            
            config = AgentConfig(
                id="test-agent-001",
                name="Test Agent",
                capabilities=["reasoning", "coding"],
                resources=ResourceLimit(token_limit=50000, memory_mb=256),
                metadata={"team": "alpha"}
            )
            
            agent = await weaver.create_agent(config)
            
            assert agent.id == "test-agent-001"
            assert agent.adapter == weaver
            mock_necroswarm.spawn_agent.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dispatch_task(self, weaver, mock_necroswarm):
        """Test task dispatch"""
        with patch('necroswarm.SwarmController', return_value=mock_necroswarm):
            await weaver.initialize()
            
            # Create agent first
            config = AgentConfig(
                id="test-agent-001",
                name="Test Agent",
                capabilities=["reasoning"],
                resources=ResourceLimit(),
                metadata={}
            )
            await weaver.create_agent(config)
            
            # Dispatch task
            task = Task(
                id="task-001",
                objective="Analyze data",
                context={"data": [1, 2, 3]},
                constraints={"max_time": 60},
                priority=TaskPriority.NORMAL
            )
            
            result = await weaver.dispatch_task("test-agent-001", task)
            
            assert result.success is True
            assert result.task_id == "task-001"
            assert result.output == "Task completed successfully"
            assert result.metrics.tokens_used == 100
    
    @pytest.mark.asyncio
    async def test_coordinate(self, weaver, mock_necroswarm):
        """Test multi-agent coordination"""
        with patch('necroswarm.SwarmController', return_value=mock_necroswarm):
            await weaver.initialize()
            
            # Create two agents
            for i in range(2):
                config = AgentConfig(
                    id=f"agent-{i}",
                    name=f"Agent {i}",
                    capabilities=["reasoning"],
                    resources=ResourceLimit(),
                    metadata={}
                )
                await weaver.create_agent(config)
            
            # Coordinate
            result = await weaver.coordinate(
                agent_ids=["agent-0", "agent-1"],
                strategy=CoordinationStrategy.CONSENSUS,
                objective="Select best option"
            )
            
            assert result.consensus is True
            assert result.decision == "Proceed with Plan A"
            assert result.confidence == 0.95
            assert len(result.votes) == 2
    
    @pytest.mark.asyncio
    async def test_list_agents(self, weaver, mock_necroswarm):
        """Test listing agents"""
        with patch('necroswarm.SwarmController', return_value=mock_necroswarm):
            await weaver.initialize()
            
            # Create agents
            for i in range(3):
                config = AgentConfig(
                    id=f"agent-{i}",
                    name=f"Agent {i}",
                    capabilities=["reasoning"],
                    resources=ResourceLimit(),
                    metadata={}
                )
                await weaver.create_agent(config)
            
            agents = await weaver.list_agents()
            
            assert len(agents) == 3
            assert all(a.adapter == weaver for a in agents)
    
    @pytest.mark.asyncio
    async def test_terminate_agent(self, weaver, mock_necroswarm):
        """Test agent termination"""
        with patch('necroswarm.SwarmController', return_value=mock_necroswarm):
            await weaver.initialize()
            
            # Create agent
            config = AgentConfig(
                id="test-agent-001",
                name="Test Agent",
                capabilities=["reasoning"],
                resources=ResourceLimit(),
                metadata={}
            )
            await weaver.create_agent(config)
            
            # Terminate
            await weaver.terminate_agent("test-agent-001")
            
            assert "test-agent-001" not in weaver._agents
            mock_necroswarm.terminate_agent.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup(self, weaver, mock_necroswarm):
        """Test cleanup"""
        with patch('necroswarm.SwarmController', return_value=mock_necroswarm):
            await weaver.initialize()
            
            # Create agent
            config = AgentConfig(
                id="test-agent-001",
                name="Test Agent",
                capabilities=["reasoning"],
                resources=ResourceLimit(),
                metadata={}
            )
            await weaver.create_agent(config)
            
            # Cleanup
            await weaver.cleanup()
            
            assert weaver._initialized is False
            mock_necroswarm.shutdown.assert_called_once()
    
    def test_get_swarm_stats(self, weaver):
        """Test statistics"""
        stats = weaver.get_swarm_stats()
        
        assert "agents_total" in stats
        assert "tasks_total" in stats
        assert "success_rate" in stats
        assert "council_size" in stats
    
    def test_map_capabilities(self, weaver):
        """Test capability mapping"""
        caps = weaver._map_capabilities(["reasoning", "coding", "creative"])
        
        assert "analytical" in caps  # reasoning
        assert "technical" in caps    # coding
        assert "creative" in caps   # creative
    
    def test_map_strategy(self, weaver):
        """Test strategy mapping"""
        assert weaver._map_strategy(CoordinationStrategy.CONSENSUS) == "consensus_voting"
        assert weaver._map_strategy(CoordinationStrategy.HIERARCHICAL) == "hierarchical_delegation"
        assert weaver._map_strategy(CoordinationStrategy.MARKET) == "token_weighted_voting"


class TestSwarmAgent:
    """Test SwarmAgent wrapper"""
    
    def test_status_mapping(self):
        mock_native = Mock()
        mock_native.status = 'busy'
        
        agent = SwarmAgent("test-1", mock_native, None)
        
        assert agent.status == AgentStatus.BUSY
    
    @pytest.mark.asyncio
    async def test_execute(self):
        mock_adapter = AsyncMock()
        mock_adapter._execute_on_agent = AsyncMock(return_value=Mock(
            success=True,
            output="result"
        ))
        
        mock_native = Mock()
        agent = SwarmAgent("test-1", mock_native, mock_adapter)
        
        task = Task(
            id="t-1",
            objective="Do thing",
            context={},
            constraints={}
        )
        
        result = await agent.execute(task)
        
        assert result.success is True
        mock_adapter._execute_on_agent.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
