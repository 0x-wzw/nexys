"""
MemoryEvolutionAdapter — Self-Improving Memory System

Wraps the OpenClaw memory evolution framework to provide:
- Access pattern tracking with decay scoring
- Automatic relationship inference between memories
- Memory rewriting and versioning
- Self-improving memory structures

Key features:
- Tracks access patterns to identify important memories
- Automatically infers relationships between memories
- Rewrites memories for clarity and consolidation
- Decay scoring for memory importance
"""

import asyncio
import logging
import time
import hashlib
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict

from ..interfaces import (
    IMemoryService, MemoryEntry, Metadata, SearchResult,
    CompressionCriteria, CompressionReport, EvolutionReport,
    MemoryNotFoundError
)

logger = logging.getLogger(__name__)


@dataclass
class EvolutionConfig:
    """Configuration for MemoryEvolutionAdapter"""
    
    # Access tracking
    track_access_patterns: bool = True
    access_window_size: int = 1000
    access_threshold_for_important: int = 5
    
    # Decay scoring
    enable_decay_scoring: bool = True
    decay_halflife_hours: float = 168.0  # 1 week
    importance_boost_per_access: float = 0.1
    max_importance: float = 10.0
    
    # Relationship inference
    enable_relationship_inference: bool = True
    relationship_min_cooccurrence: int = 3
    relationship_decay_hours: float = 24.0
    
    # Memory rewriting
    enable_memory_rewriting: bool = True
    rewrite_interval_hours: float = 24.0
    rewrite_min_access_count: int = 10
    
    # Storage
    storage_backend: str = "local"  # local, redis, file
    persist_path: Optional[str] = None
    
    # Evolution
    auto_evolve: bool = True
    evolve_interval_minutes: int = 60
    min_memories_for_evolution: int = 50


@dataclass
class TrackedMemory:
    """Memory entry with evolution tracking"""
    entry: MemoryEntry
    access_count: int = 0
    last_accessed: float = 0.0
    created_at: float = 0.0
    relationships: Set[str] = field(default_factory=set)
    versions: List[str] = field(default_factory=list)
    decay_score: float = 1.0
    importance_score: float = 1.0
    rewrite_count: int = 0


class AccessPatternTracker:
    """Tracks memory access patterns for evolution insights"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.access_log: List[Dict] = []
        self.memory_access_counts: Dict[str, int] = defaultdict(int)
        self.access_sequences: List[List[str]] = []
        self._lock = asyncio.Lock()
    
    async def record_access(self, memory_id: str, operation: str = "read", context: Optional[str] = None):
        """Record a memory access event"""
        entry = {
            "memory_id": memory_id,
            "operation": operation,
            "timestamp": time.time(),
            "context": context
        }
        
        async with self._lock:
            self.access_log.append(entry)
            self.memory_access_counts[memory_id] += 1
            
            # Keep log size manageable
            if len(self.access_log) > self.window_size:
                removed = self.access_log.pop(0)
                self.memory_access_counts[removed["memory_id"]] -= 1
    
    async def record_sequence(self, memory_ids: List[str]):
        """Record a sequence of related memory accesses"""
        if len(memory_ids) > 1:
            async with self._lock:
                self.access_sequences.append(memory_ids)
                if len(self.access_sequences) > self.window_size:
                    self.access_sequences.pop(0)
    
    async def get_frequently_accessed(self, threshold: int = 5) -> List[Tuple[str, int]]:
        """Get memories accessed more than threshold times"""
        return [(mid, count) for mid, count in self.memory_access_counts.items() if count >= threshold]
    
    async def get_access_patterns(self, memory_id: str) -> Dict:
        """Get access patterns for a specific memory"""
        accesses = [e for e in self.access_log if e["memory_id"] == memory_id]
        
        if not accesses:
            return {"total_accesses": 0, "operations": {}, "contexts": []}
        
        operations = defaultdict(int)
        contexts = []
        for a in accesses:
            operations[a["operation"]] += 1
            if a["context"]:
                contexts.append(a["context"])
        
        return {
            "total_accesses": len(accesses),
            "operations": dict(operations),
            "contexts": list(set(contexts))[:10]  # Top 10 unique contexts
        }
    
    async def get_coaccess_patterns(self, memory_id: str) -> Dict[str, int]:
        """Get memories frequently accessed together with this one"""
        coaccess = defaultdict(int)
        
        for sequence in self.access_sequences:
            if memory_id in sequence:
                for other_id in sequence:
                    if other_id != memory_id:
                        coaccess[other_id] += 1
        
        return dict(coaccess)


class MemoryEvolutionAdapter(IMemoryService):
    """
    The MemoryEvolutionAdapter — Self-Improving Memory System.
    
    Wraps the OpenClaw memory evolution framework to provide
    intelligent memory management:
    
    1. ACCESS TRACKING: Every read/write is logged to understand
       which memories are important.
    
    2. DECAY SCORING: Memories lose importance over time but gain
       it when accessed. Frequently accessed memories persist.
    
    3. RELATIONSHIP INFERENCE: Automatically discovers connections
       between memories based on access patterns.
    
    4. MEMORY REWRITING: Consolidates and rewrites memories for
       clarity, creating versioned history.
    
    Usage:
        adapter = MemoryEvolutionAdapter(config)
        await adapter.initialize()
        
        # Store with tracking
        await adapter.store("key", data, metadata)
        
        # Retrieve with access logging
        entry = await adapter.retrieve("key")
        
        # Search with importance scoring
        results = await adapter.search("query")
        
        # Trigger evolution
        report = await adapter.evolve()
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = EvolutionConfig(**(config or {}))
        self._initialized = False
        self._memories: Dict[str, TrackedMemory] = {}
        self._tracker = AccessPatternTracker(self.config.access_window_size)
        self._evolution_task: Optional[asyncio.Task] = None
        self._rewrite_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Initialize memory evolution system"""
        if self._initialized:
            return
        
        # Try to import native memory evolution if available
        try:
            import sys
            evolution_path = self.config.evolution_path if hasattr(self.config, 'evolution_path') else None
            if evolution_path:
                sys.path.insert(0, evolution_path)
            
            from evolution_agent import EvolutionEngine
            self._native_engine = EvolutionEngine()
            self._native_engine.initialize()
            logger.info("Native memory evolution engine loaded")
        except ImportError:
            self._native_engine = None
            logger.info("Using built-in memory evolution (native engine not installed)")
        
        # Start background tasks
        if self.config.auto_evolve:
            self._evolution_task = asyncio.create_task(
                self._evolution_loop()
            )
        
        if self.config.enable_memory_rewriting:
            self._rewrite_task = asyncio.create_task(
                self._rewrite_loop()
            )
        
        self._initialized = True
        logger.info("MemoryEvolutionAdapter initialized")
    
    async def _evolution_loop(self) -> None:
        """Background: Periodic memory evolution"""
        while True:
            try:
                await asyncio.sleep(self.config.evolve_interval_minutes * 60)
                
                if len(self._memories) >= self.config.min_memories_for_evolution:
                    report = await self.evolve()
                    logger.info(f"Auto-evolution: {report.new_relationships} new relationships")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Evolution error: {e}")
    
    async def _rewrite_loop(self) -> None:
        """Background: Periodic memory rewriting"""
        while True:
            try:
                await asyncio.sleep(self.config.rewrite_interval_hours * 3600)
                await self._rewrite_important_memories()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rewrite error: {e}")
    
    # ==================== Core IMemoryService ====================
    
    async def store(self, key: str, data: Any, metadata: Metadata) -> None:
        """Store memory with tracking"""
        await self._ensure_initialized()
        
        # Create entry
        entry = MemoryEntry(
            key=key,
            data=data,
            metadata=metadata
        )
        
        # Wrap in tracked memory
        now = time.time()
        tracked = TrackedMemory(
            entry=entry,
            created_at=now,
            last_accessed=now,
            importance_score=metadata.importance
        )
        
        self._memories[key] = tracked
        
        # Record access
        if self.config.track_access_patterns:
            await self._tracker.record_access(key, "write")
        
        # Store in native engine if available
        if self._native_engine:
            self._native_engine.store_memory(key, data, {
                "importance": metadata.importance,
                "tags": metadata.tags,
                "timestamp": metadata.timestamp.isoformat() if isinstance(metadata.timestamp, datetime) else metadata.timestamp
            })
        
        logger.debug(f"Stored memory: {key}")
    
    async def retrieve(self, key: str) -> Optional[MemoryEntry]:
        """Retrieve memory with access tracking"""
        await self._ensure_initialized()
        
        tracked = self._memories.get(key)
        if not tracked:
            return None
        
        # Update access stats
        tracked.access_count += 1
        tracked.last_accessed = time.time()
        tracked.importance_score = min(
            tracked.importance_score + self.config.importance_boost_per_access,
            self.config.max_importance
        )
        
        # Record access pattern
        if self.config.track_access_patterns:
            await self._tracker.record_access(key, "read")
        
        # Update decay score
        if self.config.enable_decay_scoring:
            tracked.decay_score = self._compute_decay_score(tracked)
        
        return tracked.entry
    
    async def search(self, query: str, limit: int = 10, min_score: float = 0.7) -> List[SearchResult]:
        """Search with importance-weighted scoring"""
        await self._ensure_initialized()
        
        results = []
        query_lower = query.lower()
        
        for key, tracked in self._memories.items():
            # Compute base similarity
            data_str = str(tracked.entry.data).lower()
            score = self._compute_text_similarity(query_lower, data_str)
            
            # Boost by importance and decay
            if self.config.enable_decay_scoring:
                importance_boost = tracked.importance_score / self.config.max_importance
                decay_penalty = tracked.decay_score
                score = score * (0.5 + 0.5 * importance_boost) * decay_penalty
            
            if score >= min_score:
                results.append(SearchResult(
                    key=key,
                    data=tracked.entry.data,
                    score=score,
                    metadata=tracked.entry.metadata
                ))
        
        # Sort by score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    async def delete(self, key: str) -> bool:
        """Delete memory"""
        if key in self._memories:
            del self._memories[key]
            if self.config.track_access_patterns:
                await self._tracker.record_access(key, "delete")
            return True
        return False
    
    async def compress(self, criteria: CompressionCriteria) -> CompressionReport:
        """Compress low-importance memories"""
        await self._ensure_initialized()
        
        bytes_before = self._estimate_storage_size()
        compressed_count = 0
        
        for key, tracked in list(self._memories.items()):
            # Check if memory should be compressed
            age_days = (time.time() - tracked.created_at) / 86400
            
            if age_days > criteria.older_than_days:
                if tracked.access_count < criteria.min_access_count:
                    # Compress by removing detailed metadata
                    tracked.entry.metadata.tags = ["compressed"]
                    tracked.entry.compressed = True
                    tracked.entry.compression_ratio = 2.0  # Simplified
                    compressed_count += 1
        
        bytes_after = self._estimate_storage_size()
        
        return CompressionReport(
            entries_compressed=compressed_count,
            bytes_before=bytes_before,
            bytes_after=bytes_after,
            compression_ratio=bytes_before / max(bytes_after, 1)
        )
    
    async def evolve(self) -> EvolutionReport:
        """Evolve memory structures based on access patterns"""
        await self._ensure_initialized()
        
        new_relationships = 0
        consolidated = 0
        schema_changes = []
        
        # 1. Infer relationships from co-access patterns
        if self.config.enable_relationship_inference:
            for key, tracked in self._memories.items():
                coaccess = await self._tracker.get_coaccess_patterns(key)
                
                for other_key, count in coaccess.items():
                    if count >= self.config.relationship_min_cooccurrence:
                        if other_key not in tracked.relationships:
                            tracked.relationships.add(other_key)
                            new_relationships += 1
                            
                            # Also add reciprocal
                            if other_key in self._memories:
                                self._memories[other_key].relationships.add(key)
        
        # 2. Adjust importance scores based on decay
        if self.config.enable_decay_scoring:
            for tracked in self._memories.values():
                old_importance = tracked.importance_score
                tracked.importance_score = self._compute_decay_score(tracked)
                if abs(tracked.importance_score - old_importance) > 0.5:
                    schema_changes.append(f"importance_adjustment:{tracked.entry.key}")
        
        # 3. Identify and tag clusters
        clusters = self._identify_clusters()
        if clusters:
            schema_changes.append(f"clusters_identified:{len(clusters)}")
        
        # 4. Native engine evolution if available
        if self._native_engine:
            try:
                self._native_engine.evolve_memories()
                schema_changes.append("native_engine_evolution")
            except Exception as e:
                logger.warning(f"Native evolution failed: {e}")
        
        return EvolutionReport(
            new_relationships=new_relationships,
            consolidated_entries=consolidated,
            schema_changes=schema_changes
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory evolution statistics"""
        total_memories = len(self._memories)
        total_accesses = sum(m.access_count for m in self._memories.values())
        avg_importance = sum(m.importance_score for m in self._memories.values()) / max(total_memories, 1)
        
        # Count relationships
        total_relationships = sum(len(m.relationships) for m in self._memories.values())
        
        # Access pattern stats
        frequently_accessed = await self._tracker.get_frequently_accessed(
            self.config.access_threshold_for_important
        )
        
        return {
            "total_memories": total_memories,
            "total_accesses": total_accesses,
            "avg_importance": avg_importance,
            "total_relationships": total_relationships,
            "frequently_accessed_count": len(frequently_accessed),
            "access_log_size": len(self._tracker.access_log),
            "sequence_count": len(self._tracker.access_sequences),
            "native_engine_available": self._native_engine is not None,
            "evolution_enabled": self.config.auto_evolve,
            "decay_scoring_enabled": self.config.enable_decay_scoring
        }
    
    # ==================== Helper Methods ====================
    
    def _compute_decay_score(self, tracked: TrackedMemory) -> float:
        """Compute decay score based on time since last access"""
        hours_since_access = (time.time() - tracked.last_accessed) / 3600
        halflife = self.config.decay_halflife_hours
        
        # Exponential decay
        decay = 0.5 ** (hours_since_access / halflife)
        
        # Boost by access frequency
        access_boost = min(tracked.access_count * 0.05, 1.0)
        
        return min(decay + access_boost, 1.0)
    
    def _compute_text_similarity(self, query: str, text: str) -> float:
        """Simple text similarity score"""
        query_terms = query.split()
        if not query_terms:
            return 0.0
        
        matches = sum(1 for term in query_terms if term in text)
        return matches / len(query_terms)
    
    def _identify_clusters(self) -> List[Set[str]]:
        """Identify memory clusters based on relationships"""
        visited = set()
        clusters = []
        
        for key in self._memories:
            if key in visited:
                continue
            
            # BFS to find cluster
            cluster = set()
            queue = [key]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster.add(current)
                
                if current in self._memories:
                    queue.extend(self._memories[current].relationships)
            
            if len(cluster) > 1:
                clusters.append(cluster)
        
        return clusters
    
    async def _rewrite_important_memories(self) -> None:
        """Rewrite frequently accessed memories for clarity"""
        frequently_accessed = await self._tracker.get_frequently_accessed(
            self.config.rewrite_min_access_count
        )
        
        for key, count in frequently_accessed:
            tracked = self._memories.get(key)
            if tracked and tracked.rewrite_count < 3:  # Limit rewrites
                # Simple rewrite: consolidate metadata
                tracked.entry.metadata.tags.append(f"rewritten_v{tracked.rewrite_count + 1}")
                tracked.rewrite_count += 1
                tracked.versions.append(tracked.entry.data)
                
                logger.info(f"Rewrote memory {key} (accessed {count} times)")
    
    def _estimate_storage_size(self) -> int:
        """Estimate total storage size in bytes"""
        import json
        total = 0
        for tracked in self._memories.values():
            total += len(json.dumps(tracked.entry.data))
            total += len(json.dumps(tracked.entry.metadata.__dict__))
        return total
    
    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize()
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self._evolution_task:
            self._evolution_task.cancel()
            try:
                await self._evolution_task
            except asyncio.CancelledError:
                pass
        
        if self._rewrite_task:
            self._rewrite_task.cancel()
            try:
                await self._rewrite_task
            except asyncio.CancelledError:
                pass
        
        self._initialized = False
        logger.info("MemoryEvolutionAdapter cleaned up")
