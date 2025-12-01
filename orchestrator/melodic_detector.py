#!/usr/bin/env python3
"""
Melodic Line Detector
Detects persistent thematic flows across modules using Algorithm 3.1
"""

import ast
from typing import List, Dict, Set, Tuple
from collections import defaultdict
from pathlib import Path
import re
from orchestrator.ee_memory import MelodicLine, MemoryNode, MemoryLevel


class MelodicLineDetector:
    """Detect persistent thematic flows across modules"""
    
    def __init__(self, persistence_threshold: float = 0.7):
        self.persistence_threshold = persistence_threshold
    
    def detect_from_codebase(
        self, 
        codebase_files: Dict[str, str],
        l0_nodes: Dict[str, MemoryNode],
        l1_nodes: Dict[str, MemoryNode],
        l2_nodes: Dict[str, MemoryNode]
    ) -> List[MelodicLine]:
        """
        Algorithm 3.1: Melodic Line Detection
        
        1. Extract call graphs and data flows
        2. Group related modules by thematic similarity
        3. Score persistence (how often patterns appear together)
        4. Return narratives above threshold
        """
        # Build dependency graph
        call_graph = self._build_call_graph(codebase_files, l1_nodes)
        
        # Find thematic clusters
        clusters = self._find_thematic_clusters(call_graph, codebase_files)
        
        # Score persistence and create melodic lines
        melodic_lines = []
        for cluster_id, (modules, patterns, entities) in enumerate(clusters):
            persistence = self._compute_persistence(cluster_id, modules, call_graph, patterns)
            
            if persistence >= self.persistence_threshold:
                melodic_line = MelodicLine(
                    id=f"ml_{cluster_id}",
                    name=self._name_cluster(modules, patterns),
                    description=self._describe_cluster(modules, patterns, entities),
                    persistence_score=persistence,
                    related_modules=modules,
                    related_patterns=patterns
                )
                melodic_lines.append(melodic_line)
        
        return melodic_lines
    
    def _build_call_graph(
        self, 
        files: Dict[str, str], 
        l1_nodes: Dict[str, MemoryNode]
    ) -> Dict[str, Set[str]]:
        """Build call graph from codebase"""
        graph = defaultdict(set)
        
        # Map entity names to their nodes
        entity_map: Dict[str, str] = {}
        for node_id, node in l1_nodes.items():
            if node.level == MemoryLevel.L1_ENTITIES:
                entity_name = node.metadata.get("name", "")
                file_path = node.metadata.get("file", "")
                key = f"{file_path}::{entity_name}"
                entity_map[key] = node_id
        
        # Parse files and extract calls
        for file_path, content in files.items():
            try:
                tree = ast.parse(content, filename=file_path)
                
                # Find function definitions and their calls
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        caller_key = f"{file_path}::{node.name}"
                        
                        # Find calls within this function
                        for child in ast.walk(node):
                            if isinstance(child, ast.Call):
                                if isinstance(child.func, ast.Name):
                                    callee_name = child.func.id
                                    # Check if callee exists in entity_map
                                    for key, eid in entity_map.items():
                                        if key.endswith(f"::{callee_name}"):
                                            graph[caller_key].add(key)
                                            break
                            
                            elif isinstance(child, ast.Attribute):
                                # Handle method calls like obj.method()
                                if isinstance(child.value, ast.Name):
                                    callee_name = f"{child.value.id}.{child.attr}"
                                    for key, eid in entity_map.items():
                                        if callee_name in key:
                                            graph[caller_key].add(key)
                                            break
            except SyntaxError:
                # Not Python or invalid - use regex fallback
                func_pattern = r'def\s+(\w+)\s*\([^)]*\):'
                call_pattern = r'(\w+)\s*\('
                
                functions = {m.group(1) for m in re.finditer(func_pattern, content)}
                calls = {m.group(1) for m in re.finditer(call_pattern, content)}
                
                for func in functions:
                    caller_key = f"{file_path}::{func}"
                    for call in calls:
                        if call in functions and call != func:
                            callee_key = f"{file_path}::{call}"
                            graph[caller_key].add(callee_key)
        
        return dict(graph)
    
    def _find_thematic_clusters(
        self, 
        graph: Dict[str, Set[str]], 
        files: Dict[str, str]
    ) -> List[Tuple[List[str], List[str], List[str]]]:
        """Find clusters of related modules using community detection"""
        # Group by directory (simple heuristic)
        by_directory: Dict[str, Set[str]] = defaultdict(set)
        
        for node_key in graph.keys():
            file_path = node_key.split("::")[0]
            directory = str(Path(file_path).parent)
            by_directory[directory].add(node_key)
        
        # Also group by co-occurrence in call graph
        clusters = []
        processed = set()
        
        for directory, nodes in by_directory.items():
            if len(nodes) >= 2:  # Minimum cluster size
                modules = list(set(node.split("::")[0] for node in nodes))
                patterns = [f"pattern_{directory}"]
                entities = list(nodes)
                
                if directory not in processed:
                    clusters.append((modules, patterns, entities))
                    processed.add(directory)
        
        # Additional clustering: strongly connected components
        scc_clusters = self._find_strongly_connected_components(graph)
        for scc in scc_clusters:
            if len(scc) >= 3:  # Minimum for SCC cluster
                modules = list(set(node.split("::")[0] for node in scc))
                patterns = [f"pattern_scc_{len(clusters)}"]
                entities = list(scc)
                clusters.append((modules, patterns, entities))
        
        return clusters
    
    def _find_strongly_connected_components(
        self, 
        graph: Dict[str, Set[str]]
    ) -> List[Set[str]]:
        """Find strongly connected components using Kosaraju's algorithm"""
        # Build reverse graph
        reverse_graph = defaultdict(set)
        all_nodes = set(graph.keys())
        for node in graph.values():
            all_nodes.update(node)
        
        for node, neighbors in graph.items():
            for neighbor in neighbors:
                reverse_graph[neighbor].add(node)
        
        # DFS for finishing times
        visited = set()
        finish_order = []
        
        def dfs1(node: str):
            visited.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs1(neighbor)
            finish_order.append(node)
        
        for node in all_nodes:
            if node not in visited:
                dfs1(node)
        
        # DFS on reverse graph
        visited = set()
        sccs = []
        
        def dfs2(node: str, component: Set[str]):
            visited.add(node)
            component.add(node)
            for neighbor in reverse_graph.get(node, set()):
                if neighbor not in visited:
                    dfs2(neighbor, component)
        
        for node in reversed(finish_order):
            if node not in visited:
                component = set()
                dfs2(node, component)
                if len(component) > 1:
                    sccs.append(component)
        
        return sccs
    
    def _compute_persistence(
        self, 
        cluster_id: int,
        modules: List[str], 
        graph: Dict[str, Set[str]],
        patterns: List[str]
    ) -> float:
        """
        Compute persistence score (0.0-1.0)
        Higher = more persistent narrative
        """
        if not modules:
            return 0.0
        
        # Count internal connections within cluster
        internal_edges = 0
        total_possible = 0
        
        cluster_nodes = set()
        for module in modules:
            for node_key in graph.keys():
                if node_key.startswith(module):
                    cluster_nodes.add(node_key)
        
        for node in cluster_nodes:
            neighbors = graph.get(node, set())
            for neighbor in neighbors:
                total_possible += 1
                if neighbor in cluster_nodes:
                    internal_edges += 1
        
        # Persistence = internal connectivity
        if total_possible == 0:
            return 0.5  # Default for isolated modules
        
        connectivity = internal_edges / total_possible
        
        # Boost by module count (more modules = more persistent)
        module_boost = min(1.0, len(modules) / 10.0) * 0.2
        
        # Boost by pattern count
        pattern_boost = min(1.0, len(patterns) / 5.0) * 0.1
        
        persistence = connectivity + module_boost + pattern_boost
        return min(1.0, persistence)
    
    def _name_cluster(self, modules: List[str], patterns: List[str]) -> str:
        """Generate name for cluster"""
        if not modules:
            return "Unknown Narrative"
        
        # Use common directory or file prefix
        paths = [Path(m) for m in modules]
        common_parts = []
        
        if len(paths) > 1:
            # Find common directory
            common_parent = Path(modules[0]).parent
            for path in paths[1:]:
                common_parent = self._common_path(common_parent, path.parent)
            
            if str(common_parent) != ".":
                common_parts.append(common_parent.name)
        
        # Use pattern name if available
        if patterns:
            pattern_name = patterns[0].replace("pattern_", "").replace("_", " ").title()
            common_parts.append(pattern_name)
        
        if common_parts:
            return " ".join(common_parts) + " Flow"
        
        # Fallback to first module name
        return Path(modules[0]).stem.title() + " Narrative"
    
    def _common_path(self, path1: Path, path2: Path) -> Path:
        """Find common path between two paths"""
        parts1 = path1.parts
        parts2 = path2.parts
        
        common = []
        for p1, p2 in zip(parts1, parts2):
            if p1 == p2:
                common.append(p1)
            else:
                break
        
        return Path(*common) if common else Path(".")
    
    def _describe_cluster(
        self, 
        modules: List[str], 
        patterns: List[str],
        entities: List[str]
    ) -> str:
        """Generate description for cluster"""
        module_names = [Path(m).stem for m in modules[:3]]
        desc_parts = [
            f"Thematic flow across {len(modules)} modules",
            f"Modules: {', '.join(module_names)}",
            f"Involves {len(entities)} entities"
        ]
        
        if patterns:
            desc_parts.append(f"Patterns: {', '.join(patterns[:2])}")
        
        return ". ".join(desc_parts) + "."

