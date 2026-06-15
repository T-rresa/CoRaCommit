# FusionSearch Embedding Export

[English](README.md) | 中文

本目录保留原 FusionSearch 实验中与全量 diff embedding 构建和后端 RAG 资源导出相关的部分。


## 环境

```bash
conda env create -f environment.yml
conda activate coracommit_env
```

快速检查依赖：

```bash
python -c "import torch, transformers, faiss, sentence_transformers; print('ok')"
```

## 构建 Dense 索引

在本目录下运行命令。

构建 CodeBERT embeddings：

```bash
python main.py build-index codebert
```

默认配置：

* 输入：`data/raw/apachecm/full.jsonl`
* 输出：`artifacts/indexes/codebert_diff_index.pkl`
* 模型：`microsoft/codebert-base`

构建 Jina embeddings：

```bash
python main.py build-index jina
```

默认配置：

* 输入：`data/raw/apachecm/full.jsonl`
* 输出：`artifacts/indexes/jina_diff_index.pkl`
* 模型：`jinaai/jina-embeddings-v2-base-code`

## 导出后端资源

使用下面命令把已有 dense pkl 索引转换成后端格式：

```bash
python main.py export-backend --output-dir artifacts/backend_resource
```

默认输入：

* `artifacts/indexes/codebert_diff_index.pkl`
* `artifacts/indexes/jina_diff_index.pkl`

输出结构：

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

导出器默认跳过空 diff、NaN/Inf 向量和零向量。可以添加 `--fail-on-invalid`，让脚本在遇到无效行时直接失败。

默认情况下，后端返回的 `commit_id` 是源数据顺序 id（`0`、`1`、`2`、...）。

只导出一个模型：

```bash
python main.py export-backend --models jina
```

导出到仓库根目录的后端资源目录：

```bash
python main.py export-backend --output-dir ../resource
```

## 验证导出资源

使用后端 `ResourceManager` 做 smoke test，确认导出的目录可以被加载，并能从每个 FAISS 索引中检索出一条结果：

```bash
python verify_backend_resources.py --resource-dir artifacts/backend_resource --models codebert jina
```
