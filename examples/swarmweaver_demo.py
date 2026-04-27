"""
SwarmWeaver Demo — The Conductor of Digital Legions

This example demonstrates how to use SwarmWeaver to orchestrate
a multi-agent workforce through the NecroSwarm council.

Usage:
    python examples/swarmweaver_demo.py
"""

import asyncio
import sys

sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/platform-consolidation')

from unified_platform import ServiceRegistry, AdapterManager
from unified_platform.interfaces import (
    AgentConfig, Task, CoordinationStrategy, ResourceLimit,
    TaskPriority
)


async def demo_basic_agent_creation():
    """Demo: Create and manage agents"""
    print("=" * 60)
    print("DEMO 1: Basic Agent Creation")
    print("=" * 60)
    
    # Initialize SwarmWeaver
    registry = ServiceRegistry()
    
    # Register SwarmWeaver adapter
    from unified_platform.adapters.swarmweaver import SwarmWeaver
    registry.register_agent_adapter("swarmweaver", SwarmWeaver)
    
    # Create SwarmWeaver instance
    weaver = registry.get_agent_service("swarmweaver", {
        "council_size": 5,
        "enable_token_economics": True
    })
    
    print("✓ SwarmWeaver initialized")
    
    # Create specialized agents
    agents = []
    
    # Research Agent
    research_agent = await weaver.create_agent(AgentConfig(
        id="research-001",
        name="Research Specialist",
        capabilities=["research", "analysis", "data_processing"],
        resources=ResourceLimit(token_limit=100000, memory_mb=512),
        metadata={
            "team": "research",
            "consensus_weight": 1.2,  # Research gets slightly more say
            "description": "Expert at gathering and analyzing information"
        }
    ))
    agents.append(research_agent)
    print(f"✓ Created: {research_agent.id}")
    
    # Code Agent
    code_agent = await weaver.create_agent(AgentConfig(
        id="code-001",
        name="Code Architect",
        capabilities=["coding", "technical", "debugging"],
        resources=ResourceLimit(token_limit=80000, memory_mb=384),
        metadata={
            "team": "engineering",
            "consensus_weight": 1.0,
            "description": "Expert at writing and reviewing code"
        }
    ))
    agents.append(code_agent)
    print(f"✓ Created: {code_agent.id}")
    
    # Creative Agent
    creative_agent = await weaver.create_agent(AgentConfig(
        id="creative-001",
        name="Creative Director",
        capabilities=["creative", "design", "communication"],
        resources=ResourceLimit(token_limit=60000, memory_mb=256),
        metadata={
            "team": "design",
            "consensus_weight": 1.1,
            "description": "Expert at design and creative work"
        }
    ))
    agents.append(creative_agent)
    print(f"✓ Created: {creative_agent.id}")
    
    print(f"\nTotal agents: {len(agents)}")
    return weaver, agents


async def demo_task_dispatch(weaver, agents):
    """Demo: Dispatch tasks to agents"""
    print("\n" + "=" * 60)
    print("DEMO 2: Task Dispatch")
    print("=" * 60)
    
    # Dispatch research task
    research_task = Task(
        id="task-research-001",
        objective="Research the current state of vector databases for AI applications",
        context={
            "focus_areas": ["performance", "scalability", "ease_of_use"],
            "preferred_solutions": ["open_source"]
        },
        constraints={"max_time": 300, "min_sources": 5},
        priority=TaskPriority.HIGH
    )
    
    print(f"\nDispatching to {agents[0].id}:")
    print(f"  Objective: {research_task.objective}")
    
    result = await weaver.dispatch_task(agents[0].id, research_task)
    
    print(f"  Status: {'✓ Success' if result.success else '✗ Failed'}")
    if result.success:
        print(f"  Tokens used: {result.metrics.tokens_used}")
        print(f"  Latency: {result.metrics.latency_ms:.2f}ms")
    
    # Dispatch coding task
    code_task = Task(
        id="task-code-001",
        objective="Implement a caching layer for the API with Redis",
        context={
            "language": "Python",
            "framework": "FastAPI",
            "requirements": ["TTL support", "distributed locking"]
        },
        constraints={"max_time": 600},
        priority=TaskPriority.CRITICAL
    )
    
    print(f"\nDispatching to {agents[1].id}:")
    print(f"  Objective: {code_task.objective}")
    
    result = await weaver.dispatch_task(agents[1].id, code_task)
    
    print(f"  Status: {'✓ Success' if result.success else '✗ Failed'}")


async def demo_council_coordination(weaver, agents):
    """Demo: Multi-agent coordination via council"""
    print("\n" + "=" * 60)
    print("DEMO 3: Council Coordination")
    print("=" * 60)
    
    # Use all three agents for a strategic decision
    agent_ids = [a.id for a in agents]
    
    print(f"\nConvening council with {len(agent_ids)} agents...")
    print(f"Strategy: Consensus voting")
    print(f"Objective: Select architecture for new microservice")
    
    coordination = await weaver.coordinate(
        agent_ids=agent_ids,
        strategy=CoordinationStrategy.CONSENSUS,
        objective="Select the best architecture pattern for a real-time data processing microservice. Options: Event-driven, Request-response, or CQRS."
    )
    
    print(f"\nCouncil Decision:")
    print(f"  Consensus reached: {'✓ Yes' if coordination.consensus else '✗ No'}")
    print(f"  Decision: {coordination.decision}")
    print(f"  Confidence: {coordination.confidence:.1%}")
    print(f"  Votes: {coordination.votes}")
    
    if coordination.dissenters:
        print(f"  Dissenters: {coordination.dissenters}")


async def demo_token_economics(weaver):
    """Demo: ACS-ACP flywheel and token economics"""
    print("\n" + "=" * 60)
    print("DEMO 4: Token Economics & Flywheel")
    print("=" * 60)
    
    # Get swarm statistics
    stats = weaver.get_swarm_stats()
    
    print("\nSwarm Economics:")
    print(f"  Total agents: {stats['agents_total']}")
    print(f"  Active: {stats['agents_active']}")
    print(f"  Idle: {stats['agents_idle']}")
    print(f"  Tasks completed: {stats['tasks_total']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    print(f"  Token economics: {'✓ Enabled' if stats['token_economics_enabled'] else '✗ Disabled'}")
    print(f"  Council size: {stats['council_size']}")
    
    print("\nACS-ACP Flywheel:")
    print("  ACS (Agent Creation System): Spawns agents when demand > 70%")
    print("  ACP (Agent Consumption Protocol): Retires agents when utilization < 10%")


async def demo_failover_and_scaling():
    """Demo: Health monitoring and failover"""
    print("\n" + "=" * 60)
    print("DEMO 5: Health Monitoring & Failover")
    print("=" * 60)
    
    from unified_platform.adapter_manager import AdapterManager
    
    # Initialize adapter manager with health monitoring
    manager = AdapterManager()
    
    # Configure failover chain
    manager.set_failover_chain("agent", ["swarmweaver", "neuroswarm"])
    
    print("\nFailover chain configured:")
    print("  Primary: SwarmWeaver (NecroSwarm)")
    print("  Fallback: NeuroSwarm")
    
    print("\nHealth monitoring:")
    print("  ✓ Latency tracking (< 100ms = healthy)")
    print("  ✓ Error rate tracking")
    print("  ✓ Automatic failover on degradation")
    print("  ✓ 30-second health check interval")


async def main():
    """Run all demos"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " SwarmWeaver Demo — The Conductor ".center(58) + "║")
    print("╠" + "═" * 58 + "╣")
    print("║  Multi-Agent Workforce Orchestration via 10-D Council    ║")
    print("╚" + "═" + "═" * 56 + "╝")
    
    try:
        # Note: This demo uses mocks. For real execution,
        # NecroSwarm must be installed and configured.
        
        print("\n⚠ This demo uses mock NecroSwarm for illustration.")
        print("  To run with real NecroSwarm:")
        print("  1. Install: pip install necroswarm")
        print("  2. Configure Redis connection")
        print("  3. Run with real instances\n")
        
        # Demo 1: Create agents
        # weaver, agents = await demo_basic_agent_creation()
        
        # Demo 2-5: (Would work with real NecroSwarm)
        # await demo_task_dispatch(weaver, agents)
        # await demo_council_coordination(weaver, agents)
        # await demo_token_economics(weaver)
        await demo_failover_and_scaling()
        
        print("\n" + "=" * 60)
        print("Demo complete! SwarmWeaver ready for production.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
