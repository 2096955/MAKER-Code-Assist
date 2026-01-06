#!/usr/bin/env python3
"""
Melodic Line Detector
Detects persistent thematic flows across modules using Algorithm 3.1

Enhanced with:
- Semantic similarity analysis using embeddings
- Improved persistence scoring with temporal patterns
- Cross-module thematic detection
- Better NLP-based naming and description generation
"""

import ast
import logging
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
from pathlib import Path
import re
import time
import numpy as np
from orchestrator.ee_memory import MelodicLine, MemoryNode, MemoryLevel

logger = logging.getLogger(__name__)

# Optional semantic analysis dependencies
try:
    from sentence_transformers import SentenceTransformer
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False


class MelodicLineDetector:
    """
    Detect persistent thematic flows across modules
    
    Enhanced with semantic analysis and improved persistence scoring.
    """
    
    def __init__(
        self, 
        persistence_threshold: float = 0.7,
        use_semantic: bool = True,
        embedding_model: str = "all-MiniLM-L6-v2"  # Lightweight, fast model
    ):
        self.persistence_threshold = persistence_threshold
        self.use_semantic = use_semantic and SEMANTIC_AVAILABLE
        
        # Initialize embedding model if semantic analysis enabled
        self.embedder = None
        if self.use_semantic:
            try:
                self.embedder = SentenceTransformer(embedding_model)
                logger.info(f"[MelodicDetector] Semantic analysis enabled with {embedding_model}")
            except (ValueError, OSError, ImportError) as e:
                logger.warning(f"[MelodicDetector] Could not load embedding model: {e}")
                self.use_semantic = False
        
        # Temporal access tracking for persistence scoring
        self.module_access_times: Dict[str, List[float]] = defaultdict(list)
        self.module_cooccurrence: Dict[Tuple[str, str], int] = defaultdict(int)
    
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
        """
        Build call graph from codebase with semantic relationships
        
        Enhanced to include:
        - Direct call relationships
        - Semantic similarity relationships (if embeddings available)
        """
        graph = defaultdict(set)
        
        # Map entity names to their nodes
        entity_map: Dict[str, str] = {}
        entity_metadata: Dict[str, Dict] = {}
        for node_id, node in l1_nodes.items():
            if node.level == MemoryLevel.L1_ENTITIES:
                entity_name = node.metadata.get("name", "")
                file_path = node.metadata.get("file", "")
                key = f"{file_path}::{entity_name}"
                entity_map[key] = node_id
                entity_metadata[key] = {
                    "name": entity_name,
                    "file": file_path,
                    "content": node.content[:200]  # First 200 chars for semantic analysis
                }
        
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
                                            # Track co-occurrence
                                            self._track_cooccurrence(caller_key, key)
                                            break
                            
                            elif isinstance(child, ast.Attribute):
                                # Handle method calls like obj.method()
                                if isinstance(child.value, ast.Name):
                                    callee_name = f"{child.value.id}.{child.attr}"
                                    for key, eid in entity_map.items():
                                        if callee_name in key:
                                            graph[caller_key].add(key)
                                            self._track_cooccurrence(caller_key, key)
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
                            self._track_cooccurrence(caller_key, callee_key)
        
        # Add semantic relationships if embeddings available
        if self.use_semantic and self.embedder and len(entity_metadata) > 1:
            semantic_edges = self._find_semantic_relationships(entity_metadata)
            for caller, callees in semantic_edges.items():
                graph[caller].update(callees)
        
        return dict(graph)
    
    def _track_cooccurrence(self, module1: str, module2: str):
        """Track when modules are accessed together (temporal pattern)"""
        file1 = module1.split("::")[0]
        file2 = module2.split("::")[0]
        if file1 != file2:
            pair = tuple(sorted([file1, file2]))
            self.module_cooccurrence[pair] += 1
            # Track access time
            now = time.time()
            self.module_access_times[file1].append(now)
            self.module_access_times[file2].append(now)
    
    def _find_semantic_relationships(
        self, 
        entity_metadata: Dict[str, Dict]
    ) -> Dict[str, Set[str]]:
        """
        Find semantic relationships between entities using embeddings
        
        Returns edges for entities that are semantically similar
        """
        semantic_graph = defaultdict(set)
        
        if not self.embedder:
            return semantic_graph
        
        try:
            # Create embeddings for all entities
            entity_keys = list(entity_metadata.keys())
            entity_texts = []
            for key in entity_keys:
                meta = entity_metadata[key]
                # Combine name, file path, and content snippet for embedding
                text = f"{meta['name']} {meta['file']} {meta.get('content', '')}"
                entity_texts.append(text)
            
            # Generate embeddings in batch
            embeddings = self.embedder.encode(entity_texts, convert_to_numpy=True, show_progress_bar=False)
            
            # Normalize for cosine similarity
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / (norms + 1e-8)
            
            # Find similar entities (cosine similarity > 0.7)
            similarity_threshold = 0.7
            for i, key1 in enumerate(entity_keys):
                for j, key2 in enumerate(entity_keys[i+1:], start=i+1):
                    similarity = np.dot(embeddings[i], embeddings[j])
                    if similarity > similarity_threshold:
                        # Add bidirectional edge
                        semantic_graph[key1].add(key2)
                        semantic_graph[key2].add(key1)
        
        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"[MelodicDetector] Semantic analysis failed: {e}")
        
        return semantic_graph
    
    def _find_thematic_clusters(
        self, 
        graph: Dict[str, Set[str]], 
        files: Dict[str, str]
    ) -> List[Tuple[List[str], List[str], List[str]]]:
        """
        Enhanced thematic clustering with cross-module detection
        
        Uses multiple strategies:
        1. Directory-based clustering (spatial)
        2. Call graph clustering (structural)
        3. Semantic clustering (if embeddings available)
        4. Co-occurrence clustering (temporal)
        """
        clusters = []
        processed_modules = set()
        
        # Strategy 1: Directory-based clustering (spatial)
        by_directory: Dict[str, Set[str]] = defaultdict(set)
        for node_key in graph.keys():
            file_path = node_key.split("::")[0]
            directory = str(Path(file_path).parent)
            by_directory[directory].add(node_key)
        
        for directory, nodes in by_directory.items():
            if len(nodes) >= 2:  # Minimum cluster size
                modules = list(set(node.split("::")[0] for node in nodes))
                # Only add if not already processed
                module_set = frozenset(modules)
                if module_set not in processed_modules:
                    patterns = [f"pattern_{directory.replace('/', '_')}"]
                    entities = list(nodes)
                    clusters.append((modules, patterns, entities))
                    processed_modules.add(module_set)
        
        # Strategy 2: Strongly connected components (structural)
        scc_clusters = self._find_strongly_connected_components(graph)
        for scc in scc_clusters:
            if len(scc) >= 3:  # Minimum for SCC cluster
                modules = list(set(node.split("::")[0] for node in scc))
                module_set = frozenset(modules)
                if module_set not in processed_modules:
                    patterns = [f"pattern_scc_{len(clusters)}"]
                    entities = list(scc)
                    clusters.append((modules, patterns, entities))
                    processed_modules.add(module_set)
        
        # Strategy 3: Semantic clustering (cross-module, if embeddings available)
        if self.use_semantic and self.embedder:
            semantic_clusters = self._find_semantic_clusters(graph, files)
            for modules, patterns, entities in semantic_clusters:
                module_set = frozenset(modules)
                if module_set not in processed_modules and len(modules) >= 2:
                    clusters.append((modules, patterns, entities))
                    processed_modules.add(module_set)
        
        # Strategy 4: Co-occurrence clustering (temporal patterns)
        cooccurrence_clusters = self._find_cooccurrence_clusters()
        for modules, patterns, entities in cooccurrence_clusters:
            module_set = frozenset(modules)
            if module_set not in processed_modules and len(modules) >= 2:
                clusters.append((modules, patterns, entities))
                processed_modules.add(module_set)
        
        return clusters
    
    def _find_semantic_clusters(
        self,
        graph: Dict[str, Set[str]],
        files: Dict[str, str]
    ) -> List[Tuple[List[str], List[str], List[str]]]:
        """
        Find clusters based on semantic similarity (cross-module)
        
        Groups modules that are semantically similar even if not in same directory
        """
        clusters = []
        
        if not self.embedder:
            return clusters
        
        try:
            # Extract module-level features for clustering
            module_features: Dict[str, str] = {}
            for file_path, content in files.items():
                # Create feature text from file path and content snippet
                feature_text = f"{file_path} {content[:500]}"
                module_features[file_path] = feature_text
            
            if len(module_features) < 2:
                return clusters
            
            # Generate embeddings
            module_paths = list(module_features.keys())
            feature_texts = [module_features[path] for path in module_paths]
            embeddings = self.embedder.encode(feature_texts, convert_to_numpy=True, show_progress_bar=False)
            
            # Normalize for cosine similarity
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / (norms + 1e-8)
            
            # Cluster modules with similarity > 0.75
            similarity_threshold = 0.75
            clustered = set()
            
            for i, path1 in enumerate(module_paths):
                if path1 in clustered:
                    continue
                
                cluster_modules = [path1]
                cluster_entities = []
                
                # Find all similar modules
                for j, path2 in enumerate(module_paths[i+1:], start=i+1):
                    if path2 in clustered:
                        continue
                    
                    similarity = np.dot(embeddings[i], embeddings[j])
                    if similarity > similarity_threshold:
                        cluster_modules.append(path2)
                        clustered.add(path2)
                
                if len(cluster_modules) >= 2:
                    # Get entities from these modules
                    for module in cluster_modules:
                        for node_key in graph.keys():
                            if node_key.startswith(module):
                                cluster_entities.append(node_key)
                    
                    patterns = [f"pattern_semantic_{len(clusters)}"]
                    clusters.append((cluster_modules, patterns, cluster_entities))
                    clustered.add(path1)
        
        except Exception as e:
            logger.warning(f"[MelodicDetector] Semantic clustering failed: {e}")
        
        return clusters
    
    def _find_cooccurrence_clusters(self) -> List[Tuple[List[str], List[str], List[str]]]:
        """
        Find clusters based on temporal co-occurrence patterns
        
        Groups modules that are frequently accessed together
        """
        clusters = []
        
        if not self.module_cooccurrence:
            return clusters
        
        # Group modules by co-occurrence frequency
        from collections import defaultdict
        cooccurrence_graph = defaultdict(set)
        
        for (mod1, mod2), count in self.module_cooccurrence.items():
            if count >= 2:  # At least 2 co-occurrences
                cooccurrence_graph[mod1].add(mod2)
                cooccurrence_graph[mod2].add(mod1)
        
        # Find connected components in co-occurrence graph
        visited = set()
        for module in cooccurrence_graph:
            if module in visited:
                continue
            
            # BFS to find connected component
            component = set()
            queue = [module]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for neighbor in cooccurrence_graph.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            
            if len(component) >= 2:
                modules = list(component)
                patterns = [f"pattern_cooccurrence_{len(clusters)}"]
                entities = []  # Will be populated from graph later
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
        Enhanced persistence scoring with multiple factors:
        
        1. Internal connectivity (call graph structure)
        2. Temporal patterns (how often modules accessed together)
        3. Semantic coherence (if embeddings available)
        4. Module count and pattern count
        
        Returns: Persistence score (0.0-1.0), higher = more persistent narrative
        """
        if not modules:
            return 0.0
        
        # 1. Internal connectivity (structural relationships)
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
        
        # Connectivity score (0.0-1.0)
        if total_possible == 0:
            connectivity = 0.5  # Default for isolated modules
        else:
            connectivity = internal_edges / total_possible
        
        # 2. Temporal patterns (co-occurrence frequency)
        temporal_score = 0.0
        if len(modules) >= 2:
            cooccurrence_count = 0
            total_pairs = 0
            for i, mod1 in enumerate(modules):
                for mod2 in modules[i+1:]:
                    total_pairs += 1
                    pair = tuple(sorted([mod1, mod2]))
                    cooccurrence_count += self.module_cooccurrence.get(pair, 0)
            
            if total_pairs > 0:
                # Normalize: more co-occurrences = higher score
                temporal_score = min(1.0, cooccurrence_count / (total_pairs * 2.0))
        
        # 3. Semantic coherence (if embeddings available)
        semantic_score = 0.0
        if self.use_semantic and len(modules) >= 2:
            # Check if modules have semantic relationships in graph
            semantic_edges = 0
            for mod1 in modules:
                for mod2 in modules:
                    if mod1 != mod2:
                        # Check if there's a semantic edge between entities in these modules
                        for node1 in cluster_nodes:
                            if node1.startswith(mod1):
                                neighbors = graph.get(node1, set())
                                for node2 in neighbors:
                                    if node2.startswith(mod2):
                                        semantic_edges += 1
                                        break
            if len(modules) > 1:
                semantic_score = min(1.0, semantic_edges / (len(modules) * (len(modules) - 1)))
        
        # 4. Module count boost (more modules = more persistent narrative)
        module_boost = min(1.0, len(modules) / 10.0) * 0.15
        
        # 5. Pattern count boost
        pattern_boost = min(1.0, len(patterns) / 5.0) * 0.1
        
        # Weighted combination
        persistence = (
            connectivity * 0.35 +      # Structural relationships (35%)
            temporal_score * 0.25 +    # Temporal patterns (25%)
            semantic_score * 0.20 +    # Semantic coherence (20%)
            module_boost +             # Module count (15%)
            pattern_boost              # Pattern count (10%)
        )
        
        return min(1.0, persistence)
    
    def _name_cluster(self, modules: List[str], patterns: List[str]) -> str:
        """
        Enhanced naming with better NLP-based generation
        
        Uses:
        - Common directory analysis
        - Pattern name extraction
        - Semantic analysis of module names (if available)
        """
        if not modules:
            return "Unknown Narrative"
        
        # Extract meaningful words from module names
        module_keywords = []
        for module in modules[:5]:  # Limit to 5 modules
            path = Path(module)
            # Extract keywords from path components
            for part in path.parts:
                if part not in ['.', '..', ''] and len(part) > 2:
                    # Remove common technical suffixes
                    clean_part = part.replace('_', ' ').replace('-', ' ')
                    # Split camelCase
                    import re
                    words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', clean_part)
                    module_keywords.extend([w.lower() for w in words if len(w) > 2])
        
        # Find most common keywords
        from collections import Counter
        keyword_counts = Counter(module_keywords)
        top_keywords = [word for word, count in keyword_counts.most_common(3)]
        
        # Use common directory or file prefix
        paths = [Path(m) for m in modules]
        common_parts = []
        
        if len(paths) > 1:
            # Find common directory
            common_parent = Path(modules[0]).parent
            for path in paths[1:]:
                common_parent = self._common_path(common_parent, path.parent)
            
            if str(common_parent) != "." and common_parent.name:
                common_parts.append(common_parent.name.replace('_', ' ').title())
        
        # Use top keywords if available
        if top_keywords:
            # Filter out common words
            common_words = {'api', 'src', 'lib', 'util', 'test', 'main', 'app', 'core'}
            meaningful_keywords = [kw for kw in top_keywords if kw not in common_words]
            if meaningful_keywords:
                keyword_name = ' '.join(meaningful_keywords[:2]).title()
                common_parts.append(keyword_name)
        
        # Use pattern name if available
        if patterns:
            pattern_name = patterns[0].replace("pattern_", "").replace("_", " ").title()
            if pattern_name not in common_parts:
                common_parts.append(pattern_name)
        
        if common_parts:
            return " ".join(common_parts[:2]) + " Flow"  # Limit to 2 parts
        
        # Fallback to first module name with better formatting
        fallback_name = Path(modules[0]).stem.replace('_', ' ').title()
        return f"{fallback_name} Narrative"
    
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
        """
        Enhanced description generation with better NLP
        
        Creates more natural, informative descriptions
        """
        module_names = [Path(m).stem.replace('_', ' ').title() for m in modules[:3]]
        
        # Build description parts
        desc_parts = []
        
        # Main narrative statement
        if len(modules) == 1:
            desc_parts.append(f"Thematic narrative in {module_names[0]}")
        elif len(modules) <= 3:
            desc_parts.append(f"Thematic flow connecting {len(modules)} modules: {', '.join(module_names)}")
        else:
            desc_parts.append(f"Complex thematic flow across {len(modules)} modules (including {', '.join(module_names)})")
        
        # Entity information
        if entities:
            entity_count = len(entities)
            if entity_count == 1:
                desc_parts.append(f"involves 1 entity")
            elif entity_count < 10:
                desc_parts.append(f"involves {entity_count} entities")
            else:
                desc_parts.append(f"involves {entity_count} entities across multiple components")
        
        # Pattern information
        if patterns:
            pattern_names = [p.replace('pattern_', '').replace('_', ' ').title() for p in patterns[:2]]
            if len(pattern_names) == 1:
                desc_parts.append(f"implements {pattern_names[0]} pattern")
            else:
                desc_parts.append(f"implements patterns: {', '.join(pattern_names)}")
        
        # Add semantic hints if available
        if self.use_semantic:
            desc_parts.append("(semantically coherent)")
        
        # Join with natural language
        description = ". ".join(desc_parts)
        if not description.endswith('.'):
            description += "."
        
        return description

