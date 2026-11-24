# -*- coding: utf-8 -*-
"""Smoke test for CodeBERT query/index embedding consistency.

The FAISS index is built with mean pooling (fusion_search/embedding/
codebert_build_index.py).  This script verifies that the query encoder
(backend/app/embedding/codebert.py) uses the same space:

  * top-1 for a corpus document should be itself (score ~= 1.0);
  * after excluding self, different queries should pick different exemplars;
  * the script fails if all queries still collapse to one hub document.

Run from the repository root:

    conda run -n coracommit_env python backend/scripts/check_retrieval_consistency.py \
        --samples 10 --output experiment/outputs/retrieval_smoke.jsonl
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource-path", default=str(REPO_ROOT / "resource"))
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument(
        "--sample-file",
        default=str(REPO_ROOT / "experiment" / "inputs" / "sample_commit.jsonl"),
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "experiment" / "outputs" / "retrieval_smoke.jsonl"),
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default="codebert")
    args = parser.parse_args()

    os.environ["RESOURCE_PATH"] = args.resource_path
    os.environ["EMBEDDING_MODEL"] = args.model
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    from app.core.resources import resource_manager
    from app.embedding.codebert import CodeBERTEmbedding

    resource_manager.initialize(args.resource_path)
    encoder = CodeBERTEmbedding()

    model = args.model
    if model not in resource_manager.faiss_indices:
        raise SystemExit(f"FAISS index for {model} not found in {args.resource_path}")
    index = resource_manager.faiss_indices[model]
    doc_map = resource_manager.doc_id_maps[model]

    rows = []
    with open(args.sample_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("diff", "").strip():
                rows.append(row)
            if len(rows) >= args.samples:
                break

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    picked_ids = []
    top1_self = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for row in rows:
            qid = str(row.get("_id"))
            vec = encoder.encode(row["diff"])
            dists, idxs = index.search(np.expand_dims(vec.astype(np.float32), axis=0), args.top_k)
            matches = [
                {"commit_id": str(doc_map[idx]), "score": float(dist)}
                for dist, idx in zip(dists[0], idxs[0])
                if idx != -1
            ]
            filtered = [m for m in matches if m["commit_id"] != qid]
            picked = filtered[0] if filtered else None
            if matches and matches[0]["commit_id"] == qid:
                top1_self += 1
            if picked:
                picked_ids.append(picked["commit_id"])
            record = {
                "query_id": qid,
                "top_k": matches,
                "self_is_top1": bool(matches and matches[0]["commit_id"] == qid),
                "picked_after_self_exclusion": picked,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                f"query {qid}: top1={matches[0]['commit_id'] if matches else None} "
                f"picked={picked['commit_id'] if picked else None}"
            )

    unique_picked = len(set(picked_ids))
    print(f"\nqueries={len(rows)} top1_self={top1_self} unique_picked={unique_picked}")
    print(f"written {output_path}")

    if top1_self < max(1, len(rows) - 1):
        raise SystemExit("FAIL: query embedding does not retrieve its own document as top-1")
    if unique_picked <= 1:
        raise SystemExit("FAIL: all queries still collapse to one exemplar (pooling mismatch?)")
    print("OK: query/index embeddings are consistent")


if __name__ == "__main__":
    main()