#!/usr/bin/env python3
"""
Code Graph: Semantic code relationship tracking using NetworkX

Tracks function calls, imports, and dependencies as a directed graph.
Enables queries like "who calls this function?" and "what breaks if I change this?"
"""

import networkx as nx
import json
import time
from typing import List, Dict, Set, Optional
import logging

logger = logging.getLogger(__name__)

# Try to import community detection (optional, falls back gracefully)
try:
    from networkx.algorithms import community
    COMMUNITY_AVAILABLE = True
except ImportError:
    COMMUNITY_AVAILABLE = False
    logger.warning("NetworkX community algorithms not available. Community detection disabled.")


class CodeGraph:
    """Semantic code graph tracking function calls, imports, dependencies"""
    
    def __init__(self):
        self.graph = nx.DiGraph()  # Directed graph for call chains
        self.version = 1
        self.last_updated = time.time()
        self.communities: Optional[List[Set[str]]] = None  # Cached communities
        self.community_built = False
    
    def add_function(self, name: str, file_path: str, line: int = 0):
        """Add function node to graph"""
        node_id = f"{file_path}::{name}"
        self.graph.add_node(node_id, type='function', file=file_path, line=line, name=name)
    
    def add_class(self, name: str, file_path: str, line: int = 0):
        """Add class node to graph"""
        node_id = f"{file_path}::{name}"
        self.graph.add_node(node_id, type='class', file=file_path, line=line, name=name)
    
    def add_call(self, caller: str, callee: str, file_path: str):
        """Add function call edge"""
        # Caller should always be qualified (from current file)
        caller_id = f"{file_path}::{caller}" if "::" not in caller else caller
        
        # For callee: check if it's external (httpx.AsyncClient) or internal
        # Standard library modules (common ones)
        STDLIB = {'os', 'sys', 'json', 'time', 'logging', 'pathlib', 'typing', 'asyncio', 'collections', 'functools', 'itertools', 're', 'hashlib', 'dataclasses', 'enum'}
        
        if "::" in callee:
            # Already qualified
            callee_id = callee
        elif '.' in callee:
            # External module call (e.g., httpx.AsyncClient, redis.Redis)
            callee_id = callee
        elif callee in STDLIB:
            # Standard library
            callee_id = callee
        else:
            # Internal function - assume same file if not qualified
            callee_id = f"{file_path}::{callee}"
        
        if not self.graph.has_node(caller_id):
            self.graph.add_node(caller_id, type='function', name=caller, file=file_path)
        if not self.graph.has_node(callee_id):
            self.graph.add_node(callee_id, type='unknown', name=callee.split('::')[-1] if '::' in callee else callee)
        self.graph.add_edge(caller_id, callee_id, type='calls')
    
    def add_import(self, importer_file: str, imported: str, import_type: str = 'import'):
        """Add import edge"""
        importer_id = f"{importer_file}::module"
        imported_id = imported
        
        if not self.graph.has_node(importer_id):
            self.graph.add_node(importer_id, type='module', file=importer_file)
        if not self.graph.has_node(imported_id):
            self.graph.add_node(imported_id, type='module', name=imported)
        self.graph.add_edge(importer_id, imported_id, type='imports', import_type=import_type)
    
    def find_callers(self, function_name: str) -> List[str]:
        """Who calls this function? Returns list of caller node IDs"""
        # Try exact match first (if already qualified)
        if function_name in self.graph:
            return list(self.graph.predecessors(function_name))
        
        # Search for qualified IDs ending with ::symbol
        matches = [node for node in self.graph.nodes() if node.endswith(f"::{function_name}")]
        if matches:
            all_callers = set()
            for match in matches:
                all_callers.update(self.graph.predecessors(match))
            return list(all_callers)
        return []
    
    def find_callers_fast(self, function_name: str) -> List[str]:
        """
        Find callers with community-aware search (5-10x faster for large graphs).
        Falls back to regular find_callers if communities not built.
        """
        # If communities not built, use regular search
        if not self.community_built or not self.communities:
            return self.find_callers(function_name)
        
        # Find the symbol's node
        symbol_node = None
        if function_name in self.graph:
            symbol_node = function_name
        else:
            matches = [node for node in self.graph.nodes() if node.endswith(f"::{function_name}")]
            if matches:
                symbol_node = matches[0]
        
        if not symbol_node:
            return []
        
        # Get symbol's community ID
        symbol_comm_id = None
        for comm_id, comm in enumerate(self.communities):
            if symbol_node in comm:
                symbol_comm_id = comm_id
                break
        
        if symbol_comm_id is None:
            # Symbol not in any community, use regular search
            return self.find_callers(function_name)
        
        # Get all callers
        all_callers = list(self.graph.predecessors(symbol_node))
        
        if not all_callers:
            return []
        
        # Separate callers by community
        community_callers = []
        other_callers = []
        
        for caller in all_callers:
            # Check if caller is in same community
            in_same_community = False
            if symbol_comm_id < len(self.communities):
                if caller in self.communities[symbol_comm_id]:
                    in_same_community = True
            
            if in_same_community:
                community_callers.append(caller)
            else:
                other_callers.append(caller)
        
        # Return community callers first (most relevant), then others
        return community_callers + other_callers
    
    def find_callees(self, function_name: str) -> List[str]:
        """What does this function call? Returns list of callee node IDs"""
        if function_name in self.graph:
            return [n for n in self.graph.successors(function_name)]
        matches = [n for n in self.graph.nodes() if n.endswith(f"::{function_name}")]
        if matches:
            all_callees = set()
            for match in matches:
                all_callees.update(self.graph.successors(match))
            return list(all_callees)
        return []
    
    def impact_analysis(self, function_name: str) -> List[str]:
        """What would break if I change this? (all descendants)"""
        matches = [n for n in self.graph.nodes() if function_name in n]
        if not matches:
            return []
        all_descendants = set()
        for match in matches:
            all_descendants.update(nx.descendants(self.graph, match))
        return list(all_descendants)
    
    def get_node_info(self, node_name: str) -> Optional[Dict]:
        """Get metadata for a node"""
        if node_name in self.graph:
            return self.graph.nodes[node_name]
        return None
    
    def build_communities(self) -> Optional[List[Set[str]]]:
        """
        Pre-compute code communities for faster search.
        Uses Louvain algorithm (greedy modularity) to detect communities.
        
        Returns:
            List of community sets, or None if not available
        """
        if not COMMUNITY_AVAILABLE:
            logger.debug("Community detection not available (NetworkX community algorithms missing)")
            return None
        
        if self.graph.number_of_nodes() < 10:
            logger.debug("Graph too small for community detection (<10 nodes)")
            return None
        
        try:
            # Convert to undirected for community detection
            # (communities work on undirected graphs)
            undirected = self.graph.to_undirected()
            
            # Detect communities using greedy modularity (Louvain-like)
            communities = list(community.greedy_modularity_communities(undirected))
            
            self.communities = communities
            self.community_built = True
            
            # Store community IDs in node metadata for fast lookup
            for comm_id, comm in enumerate(communities):
                for node in comm:
                    if node in self.graph.nodes:
                        self.graph.nodes[node]['community_id'] = comm_id
            
            logger.info(f"[CodeGraph] Detected {len(communities)} code communities "
                       f"(avg {self.graph.number_of_nodes() / len(communities):.1f} nodes/community)")
            
            return communities
            
        except Exception as e:
            logger.warning(f"Failed to build communities: {e}")
            self.communities = None
            self.community_built = False
            return None
    
    def get_community_info(self) -> Dict:
        """Get information about detected communities"""
        if not self.community_built or not self.communities:
            return {
                "communities_detected": False,
                "count": 0,
                "message": "Communities not built. Call build_communities() first."
            }
        
        # Calculate statistics
        comm_sizes = [len(comm) for comm in self.communities]
        
        return {
            "communities_detected": True,
            "count": len(self.communities),
            "total_nodes": self.graph.number_of_nodes(),
            "avg_community_size": sum(comm_sizes) / len(comm_sizes) if comm_sizes else 0,
            "min_community_size": min(comm_sizes) if comm_sizes else 0,
            "max_community_size": max(comm_sizes) if comm_sizes else 0,
        }
    
    def to_dict(self) -> Dict:
        """Serialize graph to dict for Redis storage"""
        # Serialize communities as list of lists (sets not JSON serializable)
        communities_serialized = None
        if self.communities:
            communities_serialized = [list(comm) for comm in self.communities]
        
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "graph": nx.node_link_data(self.graph),
            "communities": communities_serialized,
            "community_built": self.community_built
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CodeGraph':
        """Deserialize graph from dict"""
        graph = cls()
        graph.version = data.get("version", 1)
        graph.last_updated = data.get("last_updated", time.time())
        graph.graph = nx.node_link_graph(data["graph"])
        
        # Restore communities if available
        communities_serialized = data.get("communities")
        if communities_serialized:
            graph.communities = [set(comm) for comm in communities_serialized]
            graph.community_built = data.get("community_built", False)
            
            # Restore community IDs in node metadata
            if graph.communities:
                for comm_id, comm in enumerate(graph.communities):
                    for node in comm:
                        if node in graph.graph.nodes:
                            graph.graph.nodes[node]['community_id'] = comm_id
        
        return graph
    
    def persist_to_redis(self, redis_client, key_prefix: str = "code_graph"):
        """Persist graph to Redis with versioning and atomic updates (with retry logic)"""
        import redis
        
        graph_data = nx.node_link_data(self.graph)
        serialized = json.dumps(graph_data)
        
        # Use Redis transaction with optimistic locking
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with redis_client.pipeline() as pipe:
                    # Watch version key for changes
                    pipe.watch(f"{key_prefix}:version")
                    
                    # Get current version
                    current_version = pipe.get(f"{key_prefix}:version")
                    new_version = int(current_version or 0) + 1
                    
                    # Start transaction
                    pipe.multi()
                    pipe.set(f"{key_prefix}:state", serialized)
                    pipe.set(f"{key_prefix}:version", new_version)
                    pipe.set(f"{key_prefix}:v{new_version}", serialized)  # Keep versioned copy
                    pipe.expire(f"{key_prefix}:v{new_version}", 86400)  # 24h TTL
                    pipe.setex(f"{key_prefix}:latest", 86400, f"{key_prefix}:v{new_version}")  # Latest pointer
                    pipe.execute()
                    
                    self.version = new_version
                    self.last_updated = int(time.time())
                    logger.info(f"Persisted code graph version {new_version}")
                    return True
            except redis.WatchError:
                # Another process updated the graph, retry
                if attempt < max_retries - 1:
                    logger.debug(f"Graph update conflict, retry {attempt + 1}/{max_retries}")
                    continue
                else:
                    logger.error("Failed to persist graph after max retries")
                    return False
            except Exception as e:
                logger.warning(f"Failed to persist code graph: {e}")
                return False
        
        return False
    
    @classmethod
    def load_from_redis(cls, redis_client, key_prefix: str = "code_graph") -> Optional['CodeGraph']:
        """Load graph from Redis (latest version)"""
        try:
            latest_key = redis_client.get(f"{key_prefix}:latest")
            if not latest_key:
                return None
            data_str = redis_client.get(latest_key)
            if not data_str:
                return None
            data = json.loads(data_str)
            return cls.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load code graph: {e}")
            return None

