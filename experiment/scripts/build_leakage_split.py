# -*- coding: utf-8 -*-
"""Build the repository-disjoint leakage test set and pool-only FAISS index.

Steps:
  1. Hold out 22 repos (seed 42) from the 945 samples.
  2. Write the 497 test queries and the repo-disjoint split.
  3. Cache doc metadata (date/repo/files) from resource/docs.jsonl.
  4. Build a pool-only CodeBERT FAISS index from non-heldout repos.

Run from the repository root:
  conda run -n coracommit_env python experiment/scripts/build_leakage_split.py
"""

import argparse
import json
import os
import random
import sqlite3
from collections import Counter
from pathlib import Path

import faiss
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLES = REPO_ROOT / "experiment" / "inputs" / "sample_commit.jsonl"
DEFAULT_RESOURCE = REPO_ROOT / "resource"
DEFAULT_OUT = REPO_ROOT / "experiment" / "outputs" / "leakage"


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES))
    parser.add_argument("--resource", default=str(DEFAULT_RESOURCE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repos", type=int, default=22)
    parser.add_argument("--rebuild-meta", action="store_true")
    parser.add_argument("--rebuild-index", action="store_true")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    resource = Path(args.resource)

    samples = list(read_jsonl(args.samples))
    counts = Counter(s["repo"] for s in samples)
    repos = sorted(counts)
    holdout = sorted(random.Random(args.seed).sample(repos, args.repos))
    holdout_set = set(holdout)
    test = [s for s in samples if s["repo"] in holdout_set]
    print(f"samples={len(samples)} repos={len(repos)} holdout={len(holdout)} test={len(test)}")

    split = {
        "seed": args.seed,
        "n_holdout_repos": len(holdout),
        "holdout_repos": holdout,
        "test_count": len(test),
        "test_ids": [s["_id"] for s in test],
        "repo_counts": dict(counts),
    }
    with open(out / "split_repo_disjoint_22.json", "w", encoding="utf-8") as f:
        json.dump(split, f, ensure_ascii=False, indent=2)
    with open(out / "leakage_test_497.jsonl", "w", encoding="utf-8") as f:
        for s in test:
            f.write(json.dumps({
                "id": s.get("_id"),
                "owner": s.get("owner", ""),
                "repo": s.get("repo", ""),
                "commit_sha": s.get("commit_sha", ""),
                "date": s.get("date", ""),
                "message": s.get("message", ""),
                "files": s.get("files", []),
                "diff": s.get("diff", ""),
            }, ensure_ascii=False) + "\n")
    print("wrote split and test queries")

    # 1. Cache doc metadata from docs.jsonl (date/repo/files).
    meta_path = out / "doc_meta.jsonl"
    meta = {}
    if meta_path.exists() and not args.rebuild_meta:
        for d in read_jsonl(meta_path):
            meta[str(d["id"])] = d
        print(f"loaded cached doc_meta {len(meta)}")
    else:
        docs_jsonl = resource / "docs.jsonl"
        print("scanning docs.jsonl for date/repo/files...", flush=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            for i, d in enumerate(read_jsonl(docs_jsonl), start=1):
                did = str(d.get("_id"))
                rec = {
                    "id": did,
                    "date": d.get("date", ""),
                    "repo": d.get("repo", ""),
                    "files": d.get("files", []),
                }
                meta[did] = rec
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if i % 50000 == 0:
                    print(f"  scanned {i}", flush=True)
        print(f"cached doc_meta {len(meta)}")

    # 2. Build pool-only index.
    ids_path = resource / "embeddings" / "codebert.doc_ids.npy"
    vecs_path = resource / "embeddings" / "codebert.vecs.npy"
    index_path = out / "codebert_pool.index"
    pool_ids_path = out / "pool_doc_ids.npy"
    pool_meta_path = out / "pool_meta.json"

    if index_path.exists() and pool_ids_path.exists() and not args.rebuild_index:
        print("reusing existing pool index")
        pool_ids = np.load(pool_ids_path)
    else:
        print("loading embeddings...", flush=True)
        doc_ids = np.load(ids_path)
        vecs = np.load(vecs_path, mmap_mode="r")
        print("embedding shape", vecs.shape, "doc_ids", doc_ids.shape)

        # id -> repo from docs.db is faster/robust than the jsonl cache for all ids.
        db = sqlite3.connect(str(resource / "docs.db"))
        id2repo = dict(db.execute("select id, repo from docs").fetchall())
        db.close()

        keep = []
        for i, did in enumerate(doc_ids):
            sid = str(did)
            repo = id2repo.get(sid) or (meta.get(sid, {}).get("repo"))
            if repo and repo not in holdout_set:
                keep.append(i)
        keep = np.array(keep, dtype=np.int64)
        pool_ids = doc_ids[keep]
        pool_vecs = np.asarray(vecs[keep], dtype=np.float32)
        print(f"pool vectors {pool_vecs.shape} (from {len(doc_ids)})", flush=True)

        index = faiss.IndexFlatIP(pool_vecs.shape[1])
        index.add(pool_vecs)
        faiss.write_index(index, str(index_path))
        np.save(pool_ids_path, pool_ids)
        print("wrote", index_path, "ntotal", index.ntotal)

    pool_repos = Counter(meta[str(i)]["repo"] for i in pool_ids if str(i) in meta)
    pool_meta = {
        "total_docs": 249830,
        "pool_docs": int(len(pool_ids)),
        "heldout_repos": holdout,
        "pool_repos": sorted(pool_repos),
        "pool_repo_counts": dict(pool_repos),
        "index_path": str(index_path),
        "pool_ids_path": str(pool_ids_path),
    }
    with open(pool_meta_path, "w", encoding="utf-8") as f:
        json.dump(pool_meta, f, ensure_ascii=False, indent=2)
    print(json.dumps({
        "test": len(test),
        "pool_docs": len(pool_ids),
        "pool_repos": len(pool_repos),
        "holdout_repos": len(holdout),
    }, ensure_ascii=False, indent=2))
    print("written", out)


if __name__ == "__main__":
    main()