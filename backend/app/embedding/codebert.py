# backend/app/embedding/codebert.py

import torch
import numpy as np
from transformers import RobertaTokenizer, RobertaModel


class CodeBERTEmbedding:
    """
    CodeBERT encoder for Git diff → dense embedding
    """

    def __init__(self, model_name: str = "microsoft/codebert-base", device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = RobertaTokenizer.from_pretrained(model_name)
        self.model = RobertaModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    @torch.no_grad()
    def encode(self, diff: str) -> np.ndarray:
        """
        Encode one diff string into a normalized embedding vector

        Returns:
            np.ndarray of shape (768,)
        """

        if not diff or not diff.strip():
            # Empty diff → zero vector
            return np.zeros(768, dtype=np.float32)

        inputs = self.tokenizer(
            diff,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding="max_length"
        ).to(self.device)

        outputs = self.model(**inputs)

        # Use CLS token embedding
        cls_embedding = outputs.last_hidden_state[:, 0, :]  # (1, 768)

        # Normalize for cosine similarity
        cls_embedding = torch.nn.functional.normalize(cls_embedding, p=2, dim=1)

        return cls_embedding.cpu().numpy()[0]
