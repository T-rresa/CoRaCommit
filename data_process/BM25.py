import math
from collections import Counter, defaultdict
from typing import List, Tuple



K1 = 1.2
B = 0.75
TOP_K = 5

class BM25:
    def __init__(self, corpus: List[List[str]]):
        self.k1 = K1
        self.b = B
        self.corpus = corpus
        self.N = len(corpus)

        if self.N == 0:
            raise ValueError("Corpus is empty")

        # Document lengths
        self.doc_len = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_len) / self.N

        # Term frequencies per document
        self.tf = []
        # Document frequency
        self.df = defaultdict(int)

        for doc in corpus:
            freq = Counter(doc)
            self.tf.append(freq)
            for term in freq:
                self.df[term] += 1

        # Inverse document frequency
        self.idf = {
            term: math.log(1.0 + (self.N - df + 0.5) / (df + 0.5))
            for term, df in self.df.items()
        }

    def score(self, query_tokens: List[str], doc_index: int) -> float:
        """
        Compute BM25 score for a single document.
        """
        score = 0.0
        doc_tf = self.tf[doc_index]
        dl = self.doc_len[doc_index]

        for term in query_tokens:
            if term not in doc_tf:
                continue

            tf = doc_tf[term]
            idf = self.idf.get(term, 0.0)

            denom = tf + self.k1 * (1.0 - self.b + self.b * dl / self.avgdl)
            score += idf * (tf * (self.k1 + 1.0)) / denom

        return score

    def retrieve(
        self, query_tokens: List[str], top_k: int = TOP_K
    ) -> List[Tuple[int, float]]:
        """
        Retrieve top-k documents by BM25 score.
        Returns: [(doc_index, score), ...]
        """
        scored = []

        for i in range(self.N):
            s = self.score(query_tokens, i)
            if s > 0.0:
                scored.append((i, s))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
