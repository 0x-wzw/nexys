"""
DeterministicRetrievalAdapter — Predictable, Path-Based Retrieval

Wraps the OpenClaw deterministic retrieval framework to provide:
- Exact path-based file and memory lookup
- Optional semantic fallback for hybrid mode
- Glob/wildcard pattern matching
- Structured path resolution
- Confidence scoring for retrieval results

Modes:
- DETERMINISTIC: Exact path lookup only (fastest, most reliable)
- SEMANTIC: Semantic similarity search (when available)
- HYBRID: Path lookup with semantic fallback

Key principle: Retrieval should be predictable. Same input → same output.
"""

import asyncio
import logging
import glob
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from enum import Enum

from ..interfaces import (
    IMemoryService, MemoryEntry, Metadata, SearchResult,
    CompressionCriteria, CompressionReport, EvolutionReport,
    MemoryNotFoundError
)

logger = logging.getLogger(__name__)


class RetrievalMode(Enum):
    """Supported retrieval modes"""
    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class RetrievalResult:
    """Result container for retrieval operations"""
    path: str
    content: Any
    exists: bool
    mode: str
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DeterministicConfig:
    """Configuration for DeterministicRetrievalAdapter"""
    
    # Base paths
    memory_base_path: str = "~/.openclaw/workspace/memory"
    workspace_base_path: str = "~/.openclaw/workspace"
    
    # Retrieval mode
    default_mode: RetrievalMode = RetrievalMode.DETERMINISTIC
    semantic_fallback: bool = True
    
    # Path resolution
    resolve_relative_to_memory: bool = True
    resolve_relative_to_workspace: bool = True
    
    # Glob/wildcard
    enable_glob: bool = True
    max_glob_results: int = 100
    
    # Caching
    enable_cache: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 1000
    
    # Performance
    max_file_size_mb: float = 10.0
    skip_binary_files: bool = True
    
    # Confidence scoring
    exact_match_confidence: float = 1.0
    glob_match_confidence: float = 0.95
    semantic_match_confidence: float = 0.85
    
    # Native engine
    retrieval_path: Optional[str] = None


class DeterministicRetrievalAdapter(IMemoryService):
    """
    The DeterministicRetrievalAdapter — Predictable Path-Based Retrieval.
    
    Core principle: Same input always produces same output.
    
    Features:
    - Exact path resolution: "memory/2026-05-10.md" → exact file
    - Glob matching: "memory/*.md" → all markdown files
    - Hybrid mode: Try deterministic first, fall back to semantic
    - Confidence scoring: How certain is this result?
    - Path normalization: Handle relative/absolute paths consistently
    
    Usage:
        adapter = DeterministicRetrievalAdapter(config)
        await adapter.initialize()
        
        # Deterministic retrieval
        entry = await adapter.retrieve("memory/2026-05-10.md")
        
        # Glob search
        results = await adapter.search("memory/2026-*.md")
        
        # Hybrid: try exact, then semantic
        adapter.set_mode(RetrievalMode.HYBRID)
        entry = await adapter.retrieve("latest session notes")
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = DeterministicConfig(**(config or {}))
        self._initialized = False
        self._mode = self.config.default_mode
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._native_engine: Optional[Any] = None
        self._memory_base = Path(self.config.memory_base_path).expanduser().resolve()
        self._workspace_base = Path(self.config.workspace_base_path).expanduser().resolve()
    
    async def initialize(self) -> None:
        """Initialize deterministic retrieval engine"""
        if self._initialized:
            return
        
        # Ensure base paths exist
        self._memory_base.mkdir(parents=True, exist_ok=True)
        self._workspace_base.mkdir(parents=True, exist_ok=True)
        
        # Try to load native engine
        try:
            import sys
            if self.config.retrieval_path:
                sys.path.insert(0, self.config.retrieval_path)
            
            from deterministic_retrieval import DeterministicRetrieval
            self._native_engine = DeterministicRetrieval(
                memory_base_path=str(self._memory_base)
            )
            logger.info("Native deterministic retrieval engine loaded")
        except ImportError:
            self._native_engine = None
            logger.info("Using built-in deterministic retrieval")
        
        self._initialized = True
        logger.info(f"DeterministicRetrievalAdapter initialized (mode: {self._mode.value})")
    
    def set_mode(self, mode: RetrievalMode) -> None:
        """Set retrieval mode"""
        self._mode = mode
        logger.info(f"Retrieval mode set to: {mode.value}")
    
    # ==================== Path Resolution ====================
    
    def _resolve_path(self, key: str) -> Path:
        """Resolve a key to an absolute path"""
        path = Path(key)
        
        # Already absolute
        if path.is_absolute():
            return path
        
        # Try memory base first
        memory_path = self._memory_base / path
        if memory_path.exists() and self.config.resolve_relative_to_memory:
            return memory_path
        
        # Try workspace base
        workspace_path = self._workspace_base / path
        if workspace_path.exists() and self.config.resolve_relative_to_workspace:
            return workspace_path
        
        # Default to memory base (may not exist yet)
        return memory_path
    
    def _is_glob_pattern(self, key: str) -> bool:
        """Check if key contains glob patterns"""
        return any(c in key for c in "*?[]")
    
    def _read_file(self, path: Path) -> Optional[str]:
        """Read file contents safely"""
        try:
            # Check file size
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                logger.warning(f"File too large: {path} ({size_mb:.1f} MB)")
                return None
            
            # Skip binary check
            if self.config.skip_binary_files:
                try:
                    with open(path, 'rb') as f:
                        chunk = f.read(1024)
                        if b'\x00' in chunk:
                            return f"[Binary file: {path.name}]"
                except Exception:
                    pass
            
            # Read text
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
                
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
            return None
    
    def _get_cache_key(self, key: str, mode: str) -> str:
        """Generate cache key"""
        return f"{mode}:{key}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get from cache if valid"""
        if not self.config.enable_cache:
            return None
        
        cached = self._cache.get(cache_key)
        if not cached:
            return None
        
        # Check TTL
        age = (datetime.now() - cached["timestamp"]).total_seconds()
        if age > self.config.cache_ttl_seconds:
            del self._cache[cache_key]
            return None
        
        return cached["data"]
    
    def _set_in_cache(self, cache_key: str, data: Any) -> None:
        """Store in cache with TTL"""
        if not self.config.enable_cache:
            return
        
        # Evict oldest if cache is full
        if len(self._cache) >= self.config.max_cache_size:
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest]
        
        self._cache[cache_key] = {
            "data": data,
            "timestamp": datetime.now()
        }
    
    # ==================== Core IMemoryService ====================
    
    async def store(self, key: str, data: Any, metadata: Metadata) -> None:
        """Store data at deterministic path"""
        await self._ensure_initialized()
        
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write data
        content = json.dumps(data, indent=2, default=str) if not isinstance(data, str) else data
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Invalidate cache
        cache_key = self._get_cache_key(key, self._mode.value)
        if cache_key in self._cache:
            del self._cache[cache_key]
        
        # Store in native engine if available
        if self._native_engine:
            try:
                self._native_engine.store(str(path), data)
            except Exception as e:
                logger.warning(f"Native store failed: {e}")
        
        logger.debug(f"Stored at: {path}")
    
    async def retrieve(self, key: str) -> Optional[MemoryEntry]:
        """Retrieve with deterministic path resolution"""
        await self._ensure_initialized()
        
        cache_key = self._get_cache_key(key, self._mode.value)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        result = None
        
        # Mode: DETERMINISTIC or HYBRID
        if self._mode in (RetrievalMode.DETERMINISTIC, RetrievalMode.HYBRID):
            result = await self._deterministic_retrieve(key)
        
        # Mode: SEMANTIC or HYBRID (fallback)
        if not result and self._mode in (RetrievalMode.SEMANTIC, RetrievalMode.HYBRID):
            result = await self._semantic_retrieve(key)
        
        if result:
            self._set_in_cache(cache_key, result)
        
        return result
    
    async def _deterministic_retrieve(self, key: str) -> Optional[MemoryEntry]:
        """Exact path-based retrieval"""
        path = self._resolve_path(key)
        
        if path.exists():
            content = self._read_file(path)
            if content is not None:
                # Try to parse as JSON
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = content
                
                entry = MemoryEntry(
                    key=key,
                    data=data,
                    metadata=Metadata(
                        source=str(path),
                        timestamp=datetime.fromtimestamp(path.stat().st_mtime),
                        tags=["deterministic", "file"],
                        importance=1.0
                    ),
                    compressed=False
                )
                return entry
        
        return None
    
    async def _semantic_retrieve(self, key: str) -> Optional[MemoryEntry]:
        """Semantic fallback retrieval"""
        # Simplified: search for files with similar names
        query_lower = key.lower().replace(" ", "_").replace("-", "_")
        
        for ext in [".md", ".txt", ".json", ".py"]:
            pattern = f"**/*{query_lower}*{ext}"
            
            for base in [self._memory_base, self._workspace_base]:
                matches = list(base.glob(pattern))
                if matches:
                    best_match = matches[0]
                    content = self._read_file(best_match)
                    if content is not None:
                        try:
                            data = json.loads(content)
                        except json.JSONDecodeError:
                            data = content
                        
                        return MemoryEntry(
                            key=str(best_match.relative_to(base)),
                            data=data,
                            metadata=Metadata(
                                source=str(best_match),
                                timestamp=datetime.fromtimestamp(best_match.stat().st_mtime),
                                tags=["semantic", "fallback"],
                                importance=self.config.semantic_match_confidence
                            ),
                            compressed=False
                        )
        
        return None
    
    async def search(self, query: str, limit: int = 10, min_score: float = 0.7) -> List[SearchResult]:
        """Search with glob pattern support"""
        await self._ensure_initialized()
        
        results = []
        
        # Check for glob patterns
        if self._is_glob_pattern(query) and self.config.enable_glob:
            for base in [self._memory_base, self._workspace_base]:
                try:
                    matches = list(base.glob(query))
                    for match in matches[:self.config.max_glob_results]:
                        if match.is_file():
                            content = self._read_file(match)
                            if content is not None:
                                try:
                                    data = json.loads(content)
                                except json.JSONDecodeError:
                                    data = content
                                
                                results.append(SearchResult(
                                    key=str(match.relative_to(base)),
                                    data=data,
                                    score=self.config.glob_match_confidence,
                                    metadata=Metadata(
                                        source=str(match),
                                        timestamp=datetime.fromtimestamp(match.stat().st_mtime),
                                        tags=["glob", "pattern_match"],
                                        importance=1.0
                                    )
                                ))
                except Exception as e:
                    logger.warning(f"Glob search failed: {e}")
        
        else:
            # Non-glob: search by filename/content similarity
            query_lower = query.lower()
            
            for base in [self._memory_base, self._workspace_base]:
                for path in base.rglob("*"):
                    if not path.is_file():
                        continue
                    
                    # Check filename match
                    score = 0.0
                    if query_lower in path.name.lower():
                        score = self.config.exact_match_confidence
                    
                    if score >= min_score:
                        content = self._read_file(path)
                        if content is not None:
                            try:
                                data = json.loads(content)
                            except json.JSONDecodeError:
                                data = content
                            
                            results.append(SearchResult(
                                key=str(path.relative_to(base)),
                                data=data,
                                score=score,
                                metadata=Metadata(
                                    source=str(path),
                                    timestamp=datetime.fromtimestamp(path.stat().st_mtime),
                                    tags=["filename_match"],
                                    importance=1.0
                                )
                            ))
        
        # Sort and limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    async def delete(self, key: str) -> bool:
        """Delete file at deterministic path"""
        path = self._resolve_path(key)
        
        if path.exists():
            path.unlink()
            
            # Invalidate cache
            for mode in ["deterministic", "semantic", "hybrid"]:
                cache_key = self._get_cache_key(key, mode)
                if cache_key in self._cache:
                    del self._cache[cache_key]
            
            return True
        
        return False
    
    async def compress(self, criteria: CompressionCriteria) -> CompressionReport:
        """Compress old files"""
        await self._ensure_initialized()
        
        compressed_count = 0
        bytes_before = 0
        bytes_after = 0
        
        for base in [self._memory_base, self._workspace_base]:
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                
                age_days = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).days
                
                if age_days > criteria.older_than_days:
                    content = self._read_file(path)
                    if content:
                        bytes_before += len(content.encode('utf-8'))
                        # Simple compression: remove whitespace
                        compressed = content.replace("  ", " ").replace("\n\n", "\n")
                        bytes_after += len(compressed.encode('utf-8'))
                        
                        with open(path, 'w') as f:
                            f.write(compressed)
                        
                        compressed_count += 1
        
        return CompressionReport(
            entries_compressed=compressed_count,
            bytes_before=bytes_before,
            bytes_after=bytes_after,
            compression_ratio=bytes_before / max(bytes_after, 1)
        )
    
    async def evolve(self) -> EvolutionReport:
        """Evolve by reorganizing files based on access patterns"""
        await self._ensure_initialized()
        
        # Simple evolution: identify and report stale files
        stale_files = []
        
        for base in [self._memory_base, self._workspace_base]:
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                
                age_days = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).days
                
                if age_days > 365:  # Older than 1 year
                    stale_files.append(str(path))
        
        return EvolutionReport(
            new_relationships=0,
            consolidated_entries=len(stale_files),
            schema_changes=[f"stale_files:{len(stale_files)}"]
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics"""
        file_count = 0
        total_size = 0
        
        for base in [self._memory_base, self._workspace_base]:
            for path in base.rglob("*"):
                if path.is_file():
                    file_count += 1
                    total_size += path.stat().st_size
        
        return {
            "mode": self._mode.value,
            "file_count": file_count,
            "total_size_bytes": total_size,
            "cache_entries": len(self._cache),
            "memory_base": str(self._memory_base),
            "workspace_base": str(self._workspace_base),
            "native_engine_available": self._native_engine is not None,
            "glob_enabled": self.config.enable_glob,
            "cache_enabled": self.config.enable_cache
        }
    
    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize()
    
    async def cleanup(self) -> None:
        """Cleanup"""
        self._cache.clear()
        self._initialized = False
        logger.info("DeterministicRetrievalAdapter cleaned up")
    
    # ==================== Extended API ====================
    
    async def list_directory(self, path: str = "") -> List[str]:
        """List files in a directory"""
        await self._ensure_initialized()
        
        base_path = self._resolve_path(path)
        
        if not base_path.exists() or not base_path.is_dir():
            return []
        
        return [
            str(p.relative_to(base_path))
            for p in base_path.iterdir()
        ]
    
    async def exists(self, key: str) -> bool:
        """Check if path exists"""
        await self._ensure_initialized()
        return self._resolve_path(key).exists()
    
    async def get_file_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get file metadata"""
        await self._ensure_initialized()
        
        path = self._resolve_path(key)
        
        if not path.exists():
            return None
        
        stat = path.stat()
        return {
            "path": str(path),
            "size_bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "is_file": path.is_file(),
            "is_directory": path.is_dir()
        }
