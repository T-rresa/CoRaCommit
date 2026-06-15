# Demo RAG Resource

This directory contains a small ApacheCM-derived demo RAG resource for quickstart runs.

It includes 32 sampled documents plus matching SQLite, NumPy, and FAISS files:

- `docs.db`
- `docs.jsonl`
- `embeddings/*.doc_ids.npy`
- `embeddings/*.vecs.npy`
- `faiss/*.index`

Use it by setting:

```bash
RESOURCE_PATH=resource_demo
```

This resource is only for smoke testing and local startup checks. It is not intended for retrieval-quality evaluation or production use.
