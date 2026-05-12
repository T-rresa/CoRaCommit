import os
from typing import List, Dict, Any
import numpy as np
from ..core.resources import resource_manager

class FaissRetriever:
    def __init__(self):
        # Ensure resources are initialized (idempotent)
        if not resource_manager.initialized:
            resource_path = os.getenv("RESOURCE_PATH", "resource")
            resource_manager.initialize(resource_path)
            
    def search_by_vector(self, vector: List[float], model_name: str = "codebert", top_k: int = 1) -> List[Dict[str, Any]]:
        if model_name not in resource_manager.faiss_indices:
            print(f"Index for {model_name} not available. (Check EMBEDDING_MODEL env var)")
            return []
            
        index = resource_manager.faiss_indices[model_name]
        doc_map = resource_manager.doc_id_maps[model_name]
        
        try:
            query_vec = np.array(vector, dtype=np.float32)
            query_vec = np.expand_dims(query_vec, axis=0)
            
            distances, indices = index.search(query_vec, top_k)
            
            results = []
            max_dist = 0
            min_dist = float('inf')
            
            # First pass: collect candidate ids and raw scores for normalization
            temp_candidates = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1: continue
                if idx >= len(doc_map): continue

                dist_val = float(dist)
                max_dist = max(max_dist, dist_val)
                min_dist = min(min_dist, dist_val)
                
                doc_id = str(doc_map[idx])

                temp_candidates.append({
                    "commit_id": doc_id,
                    "raw_score": dist_val
                })

            docs_by_id = resource_manager.get_docs([item["commit_id"] for item in temp_candidates])

            temp_results = []
            for item in temp_candidates:
                doc_id = item["commit_id"]
                doc = docs_by_id.get(doc_id)
                if not doc:
                    continue

                diff_text = doc.get("diff", "")
                # Skip empty diffs - not useful for retrieval or prompts
                if not diff_text or not str(diff_text).strip():
                    continue

                temp_results.append({
                    "commit_id": doc_id,
                    "message": doc.get("message", ""),
                    "diff": diff_text,
                    "raw_score": item["raw_score"]
                })
            
            # Second pass: Normalize scores (Min-Max Normalization)
            denom = max_dist - min_dist if max_dist > min_dist else 1.0
            
            for res in temp_results:
                normalized_score = (res["raw_score"] - min_dist) / denom
                res["similarity_score"] = normalized_score
                results.append(res)
                
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def search(self, diff: str, model_name: str = "codebert", top_k: int = 1) -> List[Dict[str, Any]]:
        encoder = resource_manager.get_embedding_model(model_name)
        if not encoder:
            return []
            
        # Encode query
        try:
            query_vec = encoder.encode(diff)
            return self.search_by_vector(query_vec.tolist(), model_name, top_k)
        except Exception as e:
            print(f"Search error: {e}")
            return []
