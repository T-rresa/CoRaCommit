# backend/app/embedding/jina.py

import numpy as np
from sentence_transformers import SentenceTransformer


class JinaEmbedding:
    """
    Jina v2 code embedding for Git diff → dense embedding
    """

    def __init__(self, model_name: str = "jinaai/jina-embeddings-v2-base-code", device: str = None):
        self.model = SentenceTransformer(model_name, device=device,trust_remote_code=True)
        self.model.max_seq_length = 4096

    def encode(self, diff: str) -> np.ndarray:
        """
        Encode one diff string into a normalized embedding vector

        Returns:
            np.ndarray of shape (768,)
        """

        if not diff or not diff.strip():
            return np.zeros(self.model.get_sentence_embedding_dimension(), dtype=np.float32)

        emb = self.model.encode(
            diff,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        return emb.astype(np.float32)
