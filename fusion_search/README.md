# FusionSearch Embedding Export

English | [中文](README.zh-CN.md)

This directory keeps the parts of the original FusionSearch experiment that are needed to build full diff embeddings and export them into the backend RAG resource format.

## Environment

```bash
conda env create -f environment.yml
conda activate coracommit_env
```

Quick import check:

```bash
python -c "import torch, transformers, faiss, sentence_transformers; print('ok')"
```

## Build Dense Indexes

Run commands from this directory.

Build CodeBERT embeddings:

```bash
python main.py build-index codebert
```

Defaults:

* input: `data/raw/apachecm/full.jsonl`
* output: `artifacts/indexes/codebert_diff_index.pkl`
* model: `microsoft/codebert-base`

Build Jina embeddings:

```bash
python main.py build-index jina
```

Defaults:

* input: `data/raw/apachecm/full.jsonl`
* output: `artifacts/indexes/jina_diff_index.pkl`
* model: `jinaai/jina-embeddings-v2-base-code`

## Export Backend Resources

Convert existing dense pkl indexes into the backend format:

```bash
python main.py export-backend --output-dir artifacts/backend_resource
```

Default inputs:

* `artifacts/indexes/codebert_diff_index.pkl`
* `artifacts/indexes/jina_diff_index.pkl`

Output layout:

```text
artifacts/backend_resource/
  docs.db
  docs.jsonl
  embeddings/
    codebert.doc_ids.npy
    codebert.vecs.npy
    jina.doc_ids.npy
    jina.vecs.npy
  faiss/
    codebert.index
    jina.index
```

The exporter skips empty diffs, NaN/Inf vectors, and zero vectors by default. Add `--fail-on-invalid` to fail instead of skipping invalid rows.

By default, backend `commit_id` values are source row ids (`0`, `1`, `2`, ...).

Export only one model:

```bash
python main.py export-backend --models jina
```

Export to the repository-level backend resource directory:

```bash
python main.py export-backend --output-dir ../resource
```

## Verify Exported Resources

Smoke test that the backend `ResourceManager` can load the exported directory and retrieve one item from each FAISS index:

```bash
python verify_backend_resources.py --resource-dir artifacts/backend_resource --models codebert jina
```
