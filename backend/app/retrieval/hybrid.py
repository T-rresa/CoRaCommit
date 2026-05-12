from typing import List, Dict, Any
from .faiss_retriever import FaissRetriever
from .bm25_retriever import BM25Retriever

class HybridRetriever:
    def __init__(self):
        # Retrievers will auto-initialize resources if needed via global ResourceManager
        self.candidate_k = 16
        self.faiss_retriever = FaissRetriever()
        self.bm25_retriever = BM25Retriever()

    def search(self, vector: List[float], query_text: str = None, model_name: str = "codebert", top_k: int = 1) -> List[Dict[str, Any]]:
        # 1. Semantic Search (Candidate Generation)
        # Get top 2*k candidates from FAISS to allow for re-ranking
        candidate_k = self.candidate_k
        faiss_results = self.faiss_retriever.search_by_vector(vector, model_name=model_name, top_k=candidate_k)
        
        if not faiss_results: 
            return []

        # 2. Hybrid Scoring (Re-ranking)
        if query_text:
            candidate_ids = [res["commit_id"] for res in faiss_results]
            bm25_scores = self.bm25_retriever.score(query_text, candidate_ids)
            
            # Normalize BM25 scores (Min-Max)
            if bm25_scores:
                vals = [v for v in bm25_scores.values()]
                if vals:
                    min_score = min(vals)
                    max_score = max(vals)
                    # Only fuse scores when BM25 provides discrimination
                    if max_score > min_score:
                        denom = max_score - min_score
                        
                        # Combine: 0.7 vector + 0.3 BM25
                        for res in faiss_results:
                            cid = res["commit_id"]
                            vec_score = res["similarity_score"]
                            lex_score = (bm25_scores.get(cid, 0.0) - min_score) / denom
                            
                            res["similarity_score"] = 0.7 * vec_score + 0.3 * lex_score
            
            # Re-sort
            faiss_results.sort(key=lambda x: x["similarity_score"], reverse=True)

        return faiss_results[:top_k]
