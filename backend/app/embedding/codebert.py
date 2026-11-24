# backend/app/embedding/codebert.py

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel


class CodeBERTEmbedding:
    """
    CodeBERT encoder for Git diff -> dense embedding.

    Important: the FAISS index is built by
    ``fusion_search/embedding/codebert_build_index.py`` with mean pooling over
    token embeddings and L2 normalization.  The query encoder must use the same
    pooling strategy; CLS pooling lives in a different embedding space and
    collapses different diffs onto the same nearest neighbours.
    """

    def __init__(self, model_name: str = "microsoft/codebert-base", device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    @torch.no_grad()
    def encode_batch(self, diffs, batch_size: int = 16) -> np.ndarray:
        """
        Encode a list of diff strings into normalized embedding vectors.

        Returns:
            np.ndarray of shape (len(diffs), 768)
        """
        diffs = [d if isinstance(d, str) else "" for d in diffs]
        if not diffs:
            return np.zeros((0, 768), dtype=np.float32)

        all_vectors = []
        for start in range(0, len(diffs), batch_size):
            batch = diffs[start:start + batch_size]
            inputs = self.tokenizer(
                batch,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            ).to(self.device)

            outputs = self.model(**inputs)
            last_hidden = outputs.last_hidden_state
            attention_mask = inputs["attention_mask"].unsqueeze(-1)
            masked_hidden = last_hidden * attention_mask
            summed = masked_hidden.sum(dim=1)
            lengths = attention_mask.sum(dim=1).clamp(min=1)
            embedding = summed / lengths
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
            all_vectors.append(embedding.cpu().numpy())

        vectors = np.vstack(all_vectors).astype(np.float32)
        # Empty diffs must stay zero vectors (do not let padding tokens leak in)
        for i, d in enumerate(diffs):
            if not d.strip():
                vectors[i] = 0.0
        return vectors

    @torch.no_grad()
    def encode(self, diff: str) -> np.ndarray:
        """
        Encode one diff string into a normalized embedding vector.

        Returns:
            np.ndarray of shape (768,)
        """
        return self.encode_batch([diff], batch_size=1)[0]
