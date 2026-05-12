import os
import numpy as np
from ..core.resources import resource_manager
from ..utils.rouge import calculate_rouge_l
from typing import List, Dict, Any, Optional

class EvaluationService:
    def __init__(self):
        # Ensure resources are initialized
        if not resource_manager.initialized:
            resource_path = os.getenv("RESOURCE_PATH", "resource")
            resource_manager.initialize(resource_path)

    def evaluate(self, generated_message: str, ground_truth: str, model_name: str = "codebert", alpha: float = 0.7, beta: float = 0.3) -> dict:
        """
        Calculate similarity score = alpha * SemanticSim + beta * LexicalSim
        """
        if not generated_message or not ground_truth:
            return {
                "similarity_score": 0.0,
                "semantic_score": 0.0,
                "lexical_score": 0.0
            }

        # 1. Semantic Similarity (Cosine Similarity of Embeddings)
        semantic_score = 0.0
        
        # Check if resource_manager has embedding models initialized
        encoder = resource_manager.get_embedding_model(model_name)
        if encoder:
            try:
                vec_gen = encoder.encode(generated_message)
                vec_gt = encoder.encode(ground_truth)
                
                # Compute Cosine Similarity
                # vec_gen/vec_gt are numpy arrays
                dot_product = np.dot(vec_gen, vec_gt)
                norm_gen = np.linalg.norm(vec_gen)
                norm_gt = np.linalg.norm(vec_gt)
                
                if norm_gen > 0 and norm_gt > 0:
                    semantic_score = float(dot_product / (norm_gen * norm_gt))
            except Exception as e:
                print(f"Error computing semantic similarity: {e}")
                semantic_score = 0.0
        else:
            print(f"Warning: Embedding model {model_name} not available. Skipping semantic score.")

        # 2. Lexical Similarity (ROUGE-L)
        lexical_score = calculate_rouge_l(generated_message, ground_truth)

        # 3. Hybrid Score
        similarity_score = alpha * semantic_score + beta * lexical_score

        return {
            "similarity_score": similarity_score,
            "semantic_score": semantic_score,
            "lexical_score": lexical_score,
            "alpha": alpha,
            "beta": beta
        }

    def evaluate_multi_model(
        self,
        candidates: List[Dict[str, Any]],
        ground_truth: str,
        selected_model: str,
        is_edited: bool,
        alpha: float = 0.7,
        beta: float = 0.3,
        lambda_val: float = 0.7,
        w1: float = 0.6,
        w2: float = 0.4,
        s1: float = 0.9,
        s2: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Evaluate multiple models with user feedback
        
        Args:
            candidates: List of model outputs [{"model": "gpt-4o", "generated_message": "..."}]
            ground_truth: The final accepted/edited message
            selected_model: The model selected by user
            is_edited: Whether user edited the message
            alpha, beta: Weights for sim_score (semantic vs lexical)
            lambda_val: Weight for final score (single vs compare)
            w1, w2: Weights for single_score (sim vs preference)
            s1, s2: User preference scores (high for selected/unedited, low otherwise)
            
        Returns:
            List of evaluated candidates with scores
        """
        
        evaluated_candidates = []
        total_single_score = 0.0
        
        # First pass: Calculate Sim Score and Single Score
        for candidate in candidates:
            model = candidate.get("model")
            generated_msg = candidate.get("generated_message", "")
            
            # 1. Similarity Score
            sim_result = self.evaluate(generated_msg, ground_truth, alpha=alpha, beta=beta)
            sim_score = sim_result["similarity_score"]
            sem_score = sim_result.get("semantic_score", 0.0)
            lex_score = sim_result.get("lexical_score", 0.0)
            
            # 2. User Preference Score
            user_pref = 0.0
            
            # If this is the selected model
            if model == selected_model:
                # If edited, lower score (s2), else higher score (s1)
                user_pref = s1 if not is_edited else s2
            else:
                # Not selected model gets lower base score
                user_pref = 0.3  # Base score for rejected models
            
            # 3. Single Score = w1 * sim + w2 * pref
            single_score = w1 * sim_score + w2 * user_pref
            total_single_score += single_score
        
            candidate_result = {
                "model": model,
                "generated_message": generated_msg,
                "metrics": {
                    "semantic_score": sem_score,
                    "lexical_score": lex_score,
                    "sim_score": sim_score,
                    "user_preference": user_pref,
                    "single_score": single_score,
                    "compare_score": 0.0, # Placeholder
                    "final_score": 0.0    # Placeholder
                }
            }
            evaluated_candidates.append(candidate_result)
            
        # Second pass: Calculate Compare Score and Final Score
        
        num_candidates = len(evaluated_candidates)
        
        if num_candidates <= 1:
            # Single model case: No comparison possible, compare_score falls back to single_score
            # This ensures poor performance is not masked by a perfect relative score.
            for cand in evaluated_candidates:
                single_score = cand["metrics"]["single_score"]
                cand["metrics"]["compare_score"] = single_score
                cand["metrics"]["final_score"] = single_score # final = lambda*s + (1-lambda)*s = s
        else:
            # Multi-model case: Use Relative Max Normalization
            # Best model gets 1.0, others get ratio relative to best.
            max_single_score = 0.0
            for cand in evaluated_candidates:
                if cand["metrics"]["single_score"] > max_single_score:
                    max_single_score = cand["metrics"]["single_score"]
                    
            if max_single_score == 0:
                max_single_score = 1.0 # Avoid division by zero
                
            for cand in evaluated_candidates:
                single_score = cand["metrics"]["single_score"]
                
                # Compare Score = single_score / max(single_scores)
                compare_score = single_score / max_single_score
                
                # Final Score = lambda * single + (1-lambda) * compare
                final_score = lambda_val * single_score + (1 - lambda_val) * compare_score
                
                cand["metrics"]["compare_score"] = compare_score
                cand["metrics"]["final_score"] = final_score
            
        return evaluated_candidates
