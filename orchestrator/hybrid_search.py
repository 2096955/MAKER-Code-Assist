#!/usr/bin/env python3
"""
Hybrid Search: Combines semantic (RAG) + keyword (grep) search with re-ranking.

Implements open-docs pattern for multi-level retrieval:
1. Semantic search (RAG embeddings)
2. Keyword search (grep-based MCP)
3. Re-rank and merge results
"""

import logging
from typing import List, Dict, Optional, Set
from pathlib import Path
import re

logger = logging.getLogger(__name__)


class HybridSearch:
    """Combines semantic and keyword search for better retrieval"""
    
    def __init__(self, rag_service=None, mcp_client=None):
        """
        Initialize hybrid search.
        
        Args:
            rag_service: RAG service for semantic search
            mcp_client: MCP client for keyword search (find_references)
        """
        self.rag = rag_service
        self.mcp = mcp_client
    
    def keyword_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Keyword-based search using grep/find_references.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of results with file paths and line numbers
        """
        if not self.mcp:
            return []
        
        results = []
        
        # Extract keywords from query
        keywords = self._extract_keywords(query)
        
        for keyword in keywords[:5]:  # Limit to top 5 keywords
            try:
                # Use MCP find_references for keyword search
                refs_result = self.mcp.find_references(keyword)
                
                # Parse results (format: "[DEF] file.py:42 (definition)" or "[REF] file.py:100 (reference)")
                for line in refs_result.split('\n'):
                    if not line.strip() or line.startswith(' No'):
                        continue
                    
                    # Parse: "[DEF] orchestrator/orchestrator.py:123 (definition)"
                    match = re.match(r'[[DEF][REF]]\s+([^:]+):(\d+)\s+\((\w+)\)', line)
                    if match:
                        file_path, line_num, ref_type = match.groups()
                        results.append({
                            'file_path': file_path,
                            'line_number': int(line_num),
                            'ref_type': ref_type,
                            'keyword': keyword,
                            'score': 0.8 if ref_type == 'definition' else 0.6,  # Definitions score higher
                            'source': 'keyword'
                        })
            except (ValueError, AttributeError, TypeError) as e:
                logger.warning(f"Keyword search failed for '{keyword}': {e}")
                continue
        
        # Deduplicate by file_path + line_number
        seen = set()
        unique_results = []
        for result in results:
            key = (result['file_path'], result['line_number'])
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        # Sort by score and return top_k
        unique_results.sort(key=lambda x: x['score'], reverse=True)
        return unique_results[:top_k]
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract meaningful keywords from query.
        
        Args:
            query: Search query
            
        Returns:
            List of keywords (function names, class names, variables)
        """
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'how', 'what', 'where', 'when', 'why', 'does', 
                     'is', 'are', 'was', 'were', 'do', 'does', 'did', 'can', 'could', 
                     'should', 'would', 'will', 'this', 'that', 'these', 'those'}
        
        # Extract potential identifiers (camelCase, snake_case, UPPER_CASE)
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', query)
        
        # Filter out stop words and short words
        keywords = [w for w in words if w.lower() not in stop_words and len(w) > 2]
        
        # Prioritize capitalized words (likely class/function names)
        keywords.sort(key=lambda x: (x[0].isupper(), len(x)), reverse=True)
        
        return keywords[:10]  # Return top 10 keywords
    
    def merge_and_rerank(self, semantic_results: List[Dict], keyword_results: List[Dict], 
                         top_k: int = 5) -> List[Dict]:
        """
        Merge and re-rank results from semantic and keyword search.
        
        Args:
            semantic_results: Results from RAG semantic search
            keyword_results: Results from keyword search
            top_k: Number of final results to return
            
        Returns:
            Merged and re-ranked results
        """
        # Create a combined result set
        combined = {}
        
        # Add semantic results (weight: 0.6)
        for result in semantic_results:
            file_path = result.get('metadata', {}).get('file_path', '')
            if not file_path:
                continue
            
            key = file_path
            if key not in combined:
                combined[key] = {
                    'file_path': file_path,
                    'text': result.get('text', ''),
                    'semantic_score': result.get('score', 0.0) * 0.6,  # Weight semantic results
                    'keyword_score': 0.0,
                    'confidence': result.get('confidence', result.get('score', 0.0)),
                    'metadata': result.get('metadata', {}),
                    'sources': ['semantic']
                }
            else:
                # Boost if found in both
                combined[key]['semantic_score'] = max(
                    combined[key]['semantic_score'],
                    result.get('score', 0.0) * 0.6
                )
                combined[key]['sources'].append('semantic')
        
        # Add keyword results (weight: 0.4)
        for result in keyword_results:
            file_path = result.get('file_path', '')
            if not file_path:
                continue
            
            key = file_path
            keyword_score = result.get('score', 0.0) * 0.4  # Weight keyword results
            
            if key not in combined:
                combined[key] = {
                    'file_path': file_path,
                    'text': f"Found at line {result.get('line_number', '?')}",
                    'semantic_score': 0.0,
                    'keyword_score': keyword_score,
                    'confidence': keyword_score,
                    'metadata': {
                        'line_number': result.get('line_number'),
                        'ref_type': result.get('ref_type'),
                        'keyword': result.get('keyword')
                    },
                    'sources': ['keyword']
                }
            else:
                # Boost if found in both searches
                combined[key]['keyword_score'] = max(
                    combined[key]['keyword_score'],
                    keyword_score
                )
                combined[key]['sources'].append('keyword')
                # Update metadata with line number if available
                if result.get('line_number'):
                    combined[key]['metadata']['line_number'] = result.get('line_number')
        
        # Calculate final scores (semantic + keyword, with boost for both)
        final_results = []
        for file_path, result in combined.items():
            final_score = result['semantic_score'] + result['keyword_score']
            
            # Boost if found in both searches (hybrid bonus)
            if len(result['sources']) > 1:
                final_score *= 1.2  # 20% boost for hybrid matches
            
            result['final_score'] = final_score
            final_results.append(result)
        
        # Sort by final score and return top_k
        final_results.sort(key=lambda x: x['final_score'], reverse=True)
        return final_results[:top_k]
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Perform hybrid search combining semantic and keyword search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            Merged and re-ranked results
        """
        semantic_results = []
        keyword_results = []
        
        # 1. Semantic search (RAG)
        if self.rag:
            try:
                semantic_results = self.rag.search(query, top_k=top_k * 2)  # Get more for re-ranking
            except (ValueError, AttributeError, TypeError) as e:
                logger.warning(f"Semantic search failed: {e}")
        
        # 2. Keyword search (grep-based)
        if self.mcp:
            try:
                keyword_results = self.keyword_search(query, top_k=top_k * 2)  # Get more for re-ranking
            except Exception as e:
                logger.warning(f"Keyword search failed: {e}")
        
        # 3. Merge and re-rank
        return self.merge_and_rerank(semantic_results, keyword_results, top_k)


