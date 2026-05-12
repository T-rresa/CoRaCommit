import os
import re
from typing import List, Dict
from ..core.resources import resource_manager

class BM25Retriever:
    def __init__(self):
        # Ensure resources are initialized
        if not resource_manager.initialized:
            resource_path = os.getenv("RESOURCE_PATH", "resource")
            resource_manager.initialize(resource_path)
            
        # No in-memory BM25 needed - using SQLite FTS5 directly

    def _build_fts_query(self, query: str) -> str:
        # Extract alphanumeric tokens for FTS5 MATCH, avoiding diff symbols
        tokens = re.findall(r"[A-Za-z0-9_]+", query or "")
        if not tokens:
            return ""

        seen = set()
        safe_tokens = []
        for token in tokens:
            normalized = token.strip("_").lower()
            if len(normalized) < 2:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            safe_tokens.append(f'"{normalized}"')
            if len(safe_tokens) >= 64:
                break

        return " OR ".join(safe_tokens)

    def score(self, query: str, candidate_ids: List[str]) -> Dict[str, float]:
        """
        Calculate BM25 scores for candidate_ids using SQLite FTS5.
        
        Args:
            query: The search query string
            candidate_ids: List of document IDs to score
            
        Returns:
            Dict[doc_id, score]
        """
        if not resource_manager.db_conn:
            return {}
            
        fts_query = self._build_fts_query(query)

        # If query is empty after sanitization, return 0 scores
        if not fts_query:
            return {cid: 0.0 for cid in candidate_ids}

        scores = {}
        
        try:
            # Query FTS5 for candidates and get BM25 scores
            placeholders = ','.join(['?'] * len(candidate_ids))
            
            # SQL: 
            # SELECT id, bm25(docs_fts) as score 
            # FROM docs_fts 
            # WHERE docs_fts MATCH ? AND id IN (?,?,...)
            
            sql = f'''
                SELECT id, bm25(docs_fts) as score
                FROM docs_fts
                WHERE docs_fts MATCH ? AND id IN ({placeholders})
            '''
            
            # Arguments: [fts_query, id1, id2, ...]
            args = [fts_query] + candidate_ids
            
            cursor = resource_manager.db_conn.cursor()
            cursor.execute(sql, args)
            
            for row in cursor.fetchall():
                doc_id = str(row[0])
                # SQLite bm25() returns negative scores, negate to get positive values
                
                raw_score = row[1]
                scores[doc_id] = -1.0 * raw_score 
                
            # Fill missing candidates with 0.0
            for cid in candidate_ids:
                if cid not in scores:
                    scores[cid] = 0.0
                    
        except Exception as e:
            print(f"BM25 FTS5 Error: {e}")
            # Fallback to 0.0
            for cid in candidate_ids:
                scores[cid] = 0.0
                
        return scores
