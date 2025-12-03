#!/usr/bin/env python3
"""
Expositional Engineering Hierarchical Memory Network
Implements 4-level hierarchy: L₀ (raw) → L₁ (entities) → L₂ (patterns) → L₃ (melodic lines)

Based on EE Memory approach with:
- Compression ratios: β = [0.3, 0.2, 0.15] (L₀→L₁, L₁→L₂, L₂→L₃)
- Preservation thresholds: γ = [0.85, 0.75, 0.70]
- Target: 86% context compression
"""

import json
import time
import hashlib
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import ast
import re
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class CallExtractor(ast.NodeVisitor):
    """Extract function calls and imports from AST for code graph"""
    def __init__(self, file_path: str, code_graph):
        self.file_path = file_path
        self.graph = code_graph
        self.current_function = None
        self.imports = {}  # Map imported names to modules
        
    def visit_Import(self, node):
        """Track imports: import httpx"""
        for alias in node.names:
            module_name = alias.name
            imported_name = alias.asname or alias.name.split('.')[0]
            self.imports[imported_name] = module_name
            self.graph.add_import(self.file_path, module_name, 'import')
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Track imports: from httpx import AsyncClient"""
        module_name = node.module or ''
        for alias in node.names:
            imported_name = alias.asname or alias.name
            self.imports[imported_name] = module_name
            self.graph.add_import(self.file_path, module_name, 'from_import')
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        """Track function definition and enter scope"""
        old_function = self.current_function
        func_id = f"{self.file_path}::{node.name}"
        self.current_function = func_id
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_ClassDef(self, node):
        """Track class definition"""
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """Extract function calls: func() or obj.method()"""
        if not self.current_function:
            return
        
        # Get caller name (already qualified from visit_FunctionDef)
        caller_name = self.current_function.split('::')[-1]  # Just the function name
        
        # Handle direct calls: func()
        if isinstance(node.func, ast.Name):
            callee = node.func.id
            # Check if it's an imported function
            if callee in self.imports:
                callee = self.imports[callee]
            # Pass qualified caller ID (current_function is already qualified)
            self.graph.add_call(caller_name, callee, self.file_path)
        
        # Handle method calls: obj.method()
        elif isinstance(node.func, ast.Attribute):
            # Extract method name
            method_name = node.func.attr
            # Try to resolve object name
            if isinstance(node.func.value, ast.Name):
                obj_name = node.func.value.id
                # Check if it's an imported class/module
                if obj_name in self.imports:
                    callee = f"{self.imports[obj_name]}.{method_name}"
                else:
                    callee = f"{obj_name}.{method_name}"
            else:
                callee = method_name
            # Pass qualified caller ID
            self.graph.add_call(caller_name, callee, self.file_path)
        
        self.generic_visit(node)


class MemoryLevel(Enum):
    """Four levels of hierarchical memory"""
    L0_RAW = 0          # Raw code files, messages
    L1_ENTITIES = 1     # Functions, classes, variables
    L2_PATTERNS = 2     # Design patterns, architectural principles
    L3_MELODIC = 3      # Business narratives, thematic flows


@dataclass
class MelodicLine:
    """Thematic narrative flow (e.g., payment processing chain)"""
    id: str
    name: str
    description: str
    persistence_score: float  # 0.0-1.0, from Algorithm 3.1
    related_modules: List[str]
    related_patterns: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "persistence_score": self.persistence_score,
            "related_modules": self.related_modules,
            "related_patterns": self.related_patterns,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MelodicLine':
        """Deserialize from dict"""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            persistence_score=data["persistence_score"],
            related_modules=data["related_modules"],
            related_patterns=data.get("related_patterns", []),
            created_at=data.get("created_at", time.time()),
            last_accessed=data.get("last_accessed", time.time()),
            access_count=data.get("access_count", 0)
        )


@dataclass
class MemoryNode:
    """Single node in HMN"""
    level: MemoryLevel
    content: str
    metadata: Dict[str, Any]
    node_id: str
    parent_ids: List[str] = field(default_factory=list)
    child_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            "level": self.level.value,
            "content": self.content[:1000],  # Truncate for storage
            "metadata": self.metadata,
            "node_id": self.node_id,
            "parent_ids": self.parent_ids,
            "child_ids": self.child_ids,
            "created_at": self.created_at,
            "access_count": self.access_count
        }


class HierarchicalMemoryNetwork:
    """
    EE Memory: 4-level hierarchical compression
    Compression ratios: β = [0.3, 0.2, 0.15] (L₀→L₁, L₁→L₂, L₂→L₃)
    Preservation thresholds: γ = [0.85, 0.75, 0.70]
    """
    
    def __init__(self, 
                 codebase_path: str,
                 compression_ratios: List[float] = [0.3, 0.2, 0.15],
                 preservation_thresholds: List[float] = [0.85, 0.75, 0.70],
                 redis_client=None):
        self.codebase_path = Path(codebase_path).resolve()
        self.compression_ratios = compression_ratios
        self.preservation_thresholds = preservation_thresholds
        self.redis_client = redis_client
        
        # Level storage
        self.l0_nodes: Dict[str, MemoryNode] = {}  # Raw files
        self.l1_nodes: Dict[str, MemoryNode] = {}  # Entities
        self.l2_nodes: Dict[str, MemoryNode] = {}  # Patterns
        self.l3_melodic_lines: Dict[str, MelodicLine] = {}
        
        # Indexes for fast lookup
        self.file_to_l0: Dict[str, str] = {}
        self.entity_to_l1: Dict[str, str] = {}
        self.pattern_to_l2: Dict[str, str] = {}
        
        # Statistics
        self.stats = {
            "l0_count": 0,
            "l1_count": 0,
            "l2_count": 0,
            "l3_count": 0,
            "total_compression_ratio": 0.0
        }
        
        # LRU cache for file access tracking
        self._lru_cache: OrderedDict[str, float] = OrderedDict()
        
        # Code graph for semantic relationships
        try:
            from orchestrator.code_graph import CodeGraph
            self.code_graph: Optional[CodeGraph] = CodeGraph()
        except ImportError:
            logger.warning("CodeGraph not available, graph features disabled")
            self.code_graph: Optional[CodeGraph] = None
    
    def _update_lru_cache(self, node_id: str):
        """Update LRU cache for node access tracking"""
        self._lru_cache[node_id] = time.time()
        # Evict oldest if cache too large (keep last 1000)
        if len(self._lru_cache) > 1000:
            self._lru_cache.popitem(last=False)
    
    def add_code_file(self, file_path: str, content: str) -> str:
        """Add raw code file to L₀ with LRU caching"""
        node_id = f"l0_{hashlib.md5(file_path.encode()).hexdigest()[:12]}"

        # Check if already exists
        if node_id in self.l0_nodes:
            self.l0_nodes[node_id].access_count += 1
            self._update_lru_cache(node_id)
            return node_id

        node = MemoryNode(
            level=MemoryLevel.L0_RAW,
            content=content,
            metadata={"file_path": file_path, "size": len(content), "lines": content.count('\n')},
            node_id=node_id
        )
        self.l0_nodes[node_id] = node
        self.file_to_l0[file_path] = node_id
        self._update_lru_cache(node_id)
        self.stats["l0_count"] += 1
        return node_id
    
    def extract_entities(self, l0_node_id: str) -> List[str]:
        """Extract L₁ entities (functions, classes) from L₀ code and populate code graph"""
        if l0_node_id not in self.l0_nodes:
            return []
        
        node = self.l0_nodes[l0_node_id]
        file_path = node.metadata.get("file_path", "")
        content = node.content
        
        # Try to parse as Python AST
        entities = []
        try:
            tree = ast.parse(content, filename=file_path)
            
            # Extract entities and populate code graph
            if self.code_graph:
                # Use CallExtractor visitor to extract calls and imports
                extractor = CallExtractor(file_path, self.code_graph)
                extractor.visit(tree)
            
            for item in ast.walk(tree):
                if isinstance(item, ast.FunctionDef):
                    entity_id = f"l1_func_{item.name}_{l0_node_id}"
                    entity_node = MemoryNode(
                        level=MemoryLevel.L1_ENTITIES,
                        content=ast.get_source_segment(content, item) or "",
                        metadata={
                            "type": "function",
                            "name": item.name,
                            "file": file_path,
                            "line": item.lineno
                        },
                        node_id=entity_id,
                        parent_ids=[l0_node_id]
                    )
                    self.l1_nodes[entity_id] = entity_node
                    node.child_ids.append(entity_id)
                    entities.append(entity_id)
                    self.entity_to_l1[f"{file_path}::{item.name}"] = entity_id
                    
                    # Add to code graph
                    if self.code_graph:
                        self.code_graph.add_function(item.name, file_path, item.lineno)
                    
                elif isinstance(item, ast.ClassDef):
                    entity_id = f"l1_class_{item.name}_{l0_node_id}"
                    entity_node = MemoryNode(
                        level=MemoryLevel.L1_ENTITIES,
                        content=ast.get_source_segment(content, item) or "",
                        metadata={
                            "type": "class",
                            "name": item.name,
                            "file": file_path,
                            "line": item.lineno
                        },
                        node_id=entity_id,
                        parent_ids=[l0_node_id]
                    )
                    self.l1_nodes[entity_id] = entity_node
                    node.child_ids.append(entity_id)
                    entities.append(entity_id)
                    self.entity_to_l1[f"{file_path}::{item.name}"] = entity_id
                    
                    # Add to code graph
                    if self.code_graph:
                        self.code_graph.add_class(item.name, file_path, item.lineno)
        except SyntaxError as e:
            # Not Python or invalid syntax - use regex fallback
            logger.warning(f"AST parse error for {file_path}: {e}. Using regex fallback.")
            # Extract function-like patterns
            func_pattern = r'def\s+(\w+)\s*\([^)]*\):'
            for match in re.finditer(func_pattern, content):
                entity_id = f"l1_func_{match.group(1)}_{l0_node_id}"
                if entity_id not in self.l1_nodes:
                    entity_node = MemoryNode(
                        level=MemoryLevel.L1_ENTITIES,
                        content=match.group(0),
                        metadata={
                            "type": "function",
                            "name": match.group(1),
                            "file": file_path
                        },
                        node_id=entity_id,
                        parent_ids=[l0_node_id]
                    )
                    self.l1_nodes[entity_id] = entity_node
                    node.child_ids.append(entity_id)
                    entities.append(entity_id)
        except Exception as e:
            logger.warning(f"Error extracting entities from {file_path}: {e}")
        
        # Build communities and persist code graph after extraction
        if self.code_graph:
            # Build communities for faster queries (if graph is large enough)
            if self.code_graph.graph.number_of_nodes() >= 10:
                try:
                    self.code_graph.build_communities()
                except Exception as e:
                    logger.debug(f"Community detection failed (non-critical): {e}")
            
            # Persist to Redis
            if self.redis_client:
                try:
                    self.code_graph.persist_to_redis(self.redis_client)
                except Exception as e:
                    logger.warning(f"Failed to persist code graph: {e}")
        
        self.stats["l1_count"] = len(self.l1_nodes)
        return entities
    
    def detect_patterns(self, l1_node_ids: List[str]) -> List[str]:
        """Detect L₂ patterns (design patterns, architecture) from L₁ entities"""
        patterns = []
        
        # Group entities by file/module
        by_file: Dict[str, List[str]] = {}
        for entity_id in l1_node_ids:
            if entity_id in self.l1_nodes:
                node = self.l1_nodes[entity_id]
                file_path = node.metadata.get("file", "unknown")
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(entity_id)
        
        # Detect common patterns
        for file_path, entity_ids in by_file.items():
            if len(entity_ids) >= 3:  # Minimum for pattern
                pattern_id = f"l2_pattern_{hashlib.md5(file_path.encode()).hexdigest()[:12]}"
                
                # Extract pattern description
                pattern_desc = self._describe_pattern(file_path, entity_ids)
                
                pattern_node = MemoryNode(
                    level=MemoryLevel.L2_PATTERNS,
                    content=pattern_desc,
                    metadata={
                        "type": "module_pattern",
                        "file": file_path,
                        "entity_count": len(entity_ids)
                    },
                    node_id=pattern_id,
                    parent_ids=entity_ids
                )
                
                self.l2_nodes[pattern_id] = pattern_node
                for entity_id in entity_ids:
                    if entity_id in self.l1_nodes:
                        self.l1_nodes[entity_id].child_ids.append(pattern_id)
                patterns.append(pattern_id)
                self.pattern_to_l2[file_path] = pattern_id
        
        self.stats["l2_count"] = len(self.l2_nodes)
        return patterns
    
    def _describe_pattern(self, file_path: str, entity_ids: List[str]) -> str:
        """Generate description of pattern from entities"""
        entity_names = []
        for eid in entity_ids[:5]:  # Limit to 5
            if eid in self.l1_nodes:
                entity_names.append(self.l1_nodes[eid].metadata.get("name", ""))
        
        return f"Module pattern in {file_path}: {', '.join(entity_names)}"
    
    def detect_melodic_lines(self, persistence_threshold: float = 0.7) -> List[MelodicLine]:
        """
        Algorithm 3.1: Detect melodic lines (thematic flows)
        Returns narratives that persist across multiple modules
        """
        melodic_lines = []
        
        # Group patterns by similarity/co-occurrence
        pattern_groups = self._group_patterns_by_cooccurrence()
        
        for group_id, (patterns, modules, persistence) in enumerate(pattern_groups):
            if persistence >= persistence_threshold:
                melodic_line = MelodicLine(
                    id=f"ml_{group_id}",
                    name=self._name_melodic_line(patterns, modules),
                    description=self._describe_melodic_line(patterns, modules),
                    persistence_score=persistence,
                    related_modules=modules,
                    related_patterns=patterns
                )
                self.l3_melodic_lines[melodic_line.id] = melodic_line
                melodic_lines.append(melodic_line)
        
        self.stats["l3_count"] = len(self.l3_melodic_lines)
        return melodic_lines
    
    def _group_patterns_by_cooccurrence(self) -> List[Tuple[List[str], List[str], float]]:
        """Group patterns that appear together (co-occurrence analysis)"""
        groups = []
        
        # Simple heuristic: patterns in same directory are related
        by_directory: Dict[str, List[str]] = {}
        for pattern_id, pattern_node in self.l2_nodes.items():
            file_path = pattern_node.metadata.get("file", "")
            directory = str(Path(file_path).parent)
            if directory not in by_directory:
                by_directory[directory] = []
            by_directory[directory].append(pattern_id)
        
        # Create groups with persistence scores
        for directory, pattern_ids in by_directory.items():
            if len(pattern_ids) >= 2:  # At least 2 patterns
                modules = [self.l2_nodes[pid].metadata.get("file", "") for pid in pattern_ids]
                # Persistence = number of patterns / total files in directory
                persistence = min(1.0, len(pattern_ids) / max(1, len(set(modules))))
                groups.append((pattern_ids, modules, persistence))
        
        return groups
    
    def _name_melodic_line(self, patterns: List[str], modules: List[str]) -> str:
        """Generate name for melodic line"""
        if not modules:
            return "Unknown Narrative"
        
        # Use directory or file name as base
        first_module = modules[0]
        base_name = Path(first_module).stem
        directory = Path(first_module).parent.name
        
        if directory and directory != ".":
            return f"{directory.title()} Flow"
        return f"{base_name.title()} Narrative"
    
    def _describe_melodic_line(self, patterns: List[str], modules: List[str]) -> str:
        """Generate description for melodic line"""
        pattern_descs = []
        for pid in patterns[:3]:  # Limit to 3
            if pid in self.l2_nodes:
                pattern_descs.append(self.l2_nodes[pid].content[:100])
        
        return f"Thematic flow across {len(modules)} modules: {'; '.join(pattern_descs)}"
    
    def query_with_context(self, task_description: str, top_k: int = 5) -> Dict[str, Any]:
        """
        PageIndex-style hierarchical navigation
        Returns code context with narrative awareness
        """
        # 1. L₃: Find relevant melodic lines
        relevant_narratives = self._find_relevant_melodic_lines(task_description, top_k)
        
        # 2. L₂: Get patterns from narratives
        relevant_patterns = self._get_patterns_from_narratives(relevant_narratives)
        
        # 3. L₁: Get entities from patterns
        relevant_entities = self._get_entities_from_patterns(relevant_patterns)
        
        # 4. L₀: Retrieve actual code
        code_context = self._get_code_from_entities(relevant_entities)
        
        # Update access counts
        for ml in relevant_narratives:
            ml.last_accessed = time.time()
            ml.access_count += 1
        
        # Compute compression ratio
        original_size = sum(len(node.content) for node in self.l0_nodes.values())
        compressed_size = len(code_context)
        compression_ratio = 1.0 - (compressed_size / max(1, original_size))
        
        return {
            "code": code_context,
            "narratives": [ml.name for ml in relevant_narratives],
            "narrative_details": [ml.to_dict() for ml in relevant_narratives],
            "patterns": relevant_patterns,
            "entities": relevant_entities,
            "compression_ratio": compression_ratio,
            "original_size": original_size,
            "compressed_size": compressed_size
        }
    
    def _find_relevant_melodic_lines(self, task_description: str, top_k: int) -> List[MelodicLine]:
        """Find melodic lines relevant to task (simple keyword matching)"""
        task_lower = task_description.lower()
        scored = []
        
        for ml in self.l3_melodic_lines.values():
            score = 0.0
            # Check name
            if any(word in ml.name.lower() for word in task_lower.split()):
                score += 0.5
            # Check description
            if any(word in ml.description.lower() for word in task_lower.split()):
                score += 0.3
            # Boost by persistence
            score += ml.persistence_score * 0.2
            
            scored.append((score, ml))
        
        # Sort by score and return top_k
        scored.sort(reverse=True, key=lambda x: x[0])
        return [ml for score, ml in scored[:top_k] if score > 0.1]
    
    def _get_patterns_from_narratives(self, narratives: List[MelodicLine]) -> List[str]:
        """Get L₂ patterns from melodic lines"""
        patterns = set()
        for ml in narratives:
            patterns.update(ml.related_patterns)
        return list(patterns)
    
    def _get_entities_from_patterns(self, pattern_ids: List[str]) -> List[str]:
        """Get L₁ entities from L₂ patterns"""
        entities = set()
        for pid in pattern_ids:
            if pid in self.l2_nodes:
                entities.update(self.l2_nodes[pid].parent_ids)
        return list(entities)
    
    def _get_code_from_entities(self, entity_ids: List[str]) -> str:
        """Get L₀ code from L₁ entities"""
        code_snippets = []
        seen_files = set()
        
        for eid in entity_ids[:20]:  # Limit to 20 entities
            if eid in self.l1_nodes:
                entity = self.l1_nodes[eid]
                file_path = entity.metadata.get("file", "")
                
                # Get full file if not seen
                if file_path and file_path not in seen_files:
                    if file_path in self.file_to_l0:
                        l0_id = self.file_to_l0[file_path]
                        if l0_id in self.l0_nodes:
                            code_snippets.append(f"# {file_path}\n{self.l0_nodes[l0_id].content[:2000]}")
                            seen_files.add(file_path)
                    else:
                        # Fallback: use entity content
                        code_snippets.append(f"# {file_path}::{entity.metadata.get('name', '')}\n{entity.content[:500]}")
        
        return "\n\n".join(code_snippets)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get HMN statistics"""
        return {
            **self.stats,
            "compression_ratios": self.compression_ratios,
            "preservation_thresholds": self.preservation_thresholds
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize HMN to dict (for persistence)"""
        return {
            "codebase_path": str(self.codebase_path),
            "compression_ratios": self.compression_ratios,
            "preservation_thresholds": self.preservation_thresholds,
            "melodic_lines": [ml.to_dict() for ml in self.l3_melodic_lines.values()],
            "stats": self.stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HierarchicalMemoryNetwork':
        """Deserialize HMN from dict"""
        hmn = cls(
            codebase_path=data["codebase_path"],
            compression_ratios=data.get("compression_ratios", [0.3, 0.2, 0.15]),
            preservation_thresholds=data.get("preservation_thresholds", [0.85, 0.75, 0.70])
        )
        
        # Restore melodic lines
        for ml_data in data.get("melodic_lines", []):
            ml = MelodicLine.from_dict(ml_data)
            hmn.l3_melodic_lines[ml.id] = ml
        
        hmn.stats = data.get("stats", hmn.stats)
        return hmn

