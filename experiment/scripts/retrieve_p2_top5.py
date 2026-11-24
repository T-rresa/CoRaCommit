# -*- coding: utf-8 -*-
"""Retrieve P2 leakage-controlled top-5 exemplars for the 497 test queries.

P2 filters:
  - repository-disjoint (pool-only index already excludes held-out repos)
  - temporal: candidate date strictly before query date
  - same prefixed issue key: excluded
  - exact hash: identical normalized diff or message excluded
  - Jaccard near-duplicate: NOT used (reported only if needed)

Retrieval:
  - CodeBERT mean-pooled query encoder (matches pool index)
  - pool-only FAISS top-128 (fallback 512 / 2048)
  - BM25 global-IDF rerank, 0.7 vector + 0.3 BM25
  - return top-5 after filters
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import statistics
import unicodedata
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
import sys
sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_OUT = REPO_ROOT / "experiment" / "outputs" / "leakage"

PREFIXED_ISSUE = re.compile(r"\b([A-Za-z][A-Za-z0-9]+-\d+)\b")
BARE_ISSUE = re.compile(r"#\d+")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def tokenize_diff(diff):
    if not diff:
        return []
    diff = diff.lower()
    diff = re.sub(r"diff --git.*", " ", diff)
    diff = re.sub(r"index .*", " ", diff)
    diff = re.sub(r"@@.*@@", " ", diff)
    diff = re.sub(r"\+\+\+|---", " ", diff)
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", diff)


def normalize_diff(diff):
    if not diff:
        return ""
    diff = unicodedata.normalize("NFKC", str(diff))
    diff = diff.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in diff.split("\n")]
    return "\n".join(lines).strip()


def normalize_message(msg):
    if not msg:
        return ""
    msg = unicodedata.normalize("NFKC", str(msg))
    msg = re.sub(r"\s+", " ", msg).strip().lower()
    return msg


def sha1(text):
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()


def prefixed_issue_keys(text):
    return {m.group(1).upper() for m in PREFIXED_ISSUE.finditer(text or "")}


def parse_dt(text):
    if not text:
        return None
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except Exception:
        return None


def file_set(value):
    if isinstance(value, list):
        return {str(x) for x in value}
    if isinstance(value, str) and value.strip():
        try:
            v = json.loads(value)
            if isinstance(v, list):
                return {str(x) for x in v}
        except Exception:
            pass
        return {value}
    return set()


class FastBM25:
    def __init__(self, path):
        import pickle
        with open(path, "rb") as f:
            d = pickle.load(f)
        self.idf = d["idf"]
        self.avgdl = float(d["avgdl"])
        self.k1 = float(d["k1"])
        self.b = float(d["b"])

    def score(self, query_tokens, tokens):
        if not tokens:
            return 0.0
        tf = Counter(tokens)
        dl = len(tokens)
        s = 0.0
        for t in query_tokens:
            f = tf.get(t)
            if not f:
                continue
            idf = self.idf.get(t, 0.0)
            s += idf * (f * (self.k1 + 1.0)) / (f + self.k1 * (1.0 - self.b + self.b * dl / self.avgdl))
        return s


def minmax(values):
    vals = list(values)
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return [1.0 for _ in vals]
    return [(v - lo) / (hi - lo) for v in vals]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--leakage-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--resource", default=str(REPO_ROOT / "resource"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--k", type=int, default=128)
    parser.add_argument("--fallback-k", type=int, default=4096)
    parser.add_argument("--model", default="codebert")
    args = parser.parse_args()

    out = Path(args.leakage_dir)
    resource = Path(args.resource)
    test = list(read_jsonl(out / "leakage_test_497.jsonl"))
    pool_ids = np.load(out / "pool_doc_ids.npy")
    index = faiss.read_index(str(out / "codebert_pool.index"), faiss.IO_FLAG_MMAP)
    doc_meta = {}
    for d in read_jsonl(out / "doc_meta.jsonl"):
        doc_meta[str(d["id"])] = d
    print("test", len(test), "pool", index.ntotal, "meta", len(doc_meta), flush=True)

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from app.embedding.codebert import CodeBERTEmbedding
    encoder = CodeBERTEmbedding()
    print("encoding query diffs...", flush=True)
    vectors = encoder.encode_batch([q.get("diff", "") for q in test], batch_size=16)
    print("encoded", vectors.shape, flush=True)

    bm25 = FastBM25(str(resource / "bm25" / "bm25.data.pkl"))
    db = sqlite3.connect(str(resource / "docs.db"), check_same_thread=False)
    token_cache = {}
    hash_cache = {}
    issue_cache = {}

    def candidate_info(cid):
        cid = str(cid)
        if cid in hash_cache:
            return hash_cache[cid]
        cur = db.cursor()
        cur.execute("SELECT message, diff, repo FROM docs WHERE id=?", (cid,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        msg, diff, repo = row[0] or "", row[1] or "", row[2] or ""
        rec = {
            "commit_id": cid,
            "message": msg,
            "diff": diff,
            "repo": repo,
            "date": doc_meta.get(cid, {}).get("date", ""),
            "files": doc_meta.get(cid, {}).get("files", []),
            "diff_hash": sha1(normalize_diff(diff)),
            "msg_hash": sha1(normalize_message(msg)),
            "issue_keys": prefixed_issue_keys(msg),
            "bare_issues": len(BARE_ISSUE.findall(msg or "")),
        }
        hash_cache[cid] = rec
        return rec

    audit_rows = []
    n_short = 0
    top1_ids = Counter()
    exemplar_ids = Counter()
    same_file_top1 = 0
    days_top1 = []

    out_path = out / "top5_p2_497.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for qi, (q, vec) in enumerate(zip(test, vectors), start=1):
            qid = str(q["id"])
            qrepo = q.get("repo", "")
            qdate = parse_dt(q.get("date", ""))
            qdiff_hash = sha1(normalize_diff(q.get("diff", "")))
            qmsg_hash = sha1(normalize_message(q.get("message", "")))
            qissue = prefixed_issue_keys(q.get("message", ""))
            qfiles = file_set(q.get("files", []))
            qbare = len(BARE_ISSUE.findall(q.get("message", "") or ""))

            def retrieve(k):
                dists, idxs = index.search(np.expand_dims(vec.astype(np.float32), axis=0), min(k, index.ntotal))
                cands = []
                for dist, idx in zip(dists[0], idxs[0]):
                    if idx == -1:
                        continue
                    cid = str(pool_ids[idx])
                    info = candidate_info(cid)
                    if not info:
                        continue
                    info = dict(info)
                    info["raw_vector_score"] = float(dist)
                    cands.append(info)
                return cands

            k = args.k
            cands = retrieve(k)
            # Filter counts
            after_repo = [c for c in cands if c["repo"] != qrepo and c["commit_id"] != qid]
            after_temporal = []
            for c in after_repo:
                cdt = parse_dt(c.get("date", ""))
                if qdate and cdt and cdt < qdate:
                    after_temporal.append(c)
            after_issue = [c for c in after_temporal if not (qissue & c["issue_keys"])]
            after_hash = [c for c in after_issue if c["diff_hash"] != qdiff_hash and c["msg_hash"] != qmsg_hash]

            if len(after_hash) < args.top_k and k < args.fallback_k:
                k = args.fallback_k
                cands = retrieve(k)
                after_repo = [c for c in cands if c["repo"] != qrepo and c["commit_id"] != qid]
                after_temporal = []
                for c in after_repo:
                    cdt = parse_dt(c.get("date", ""))
                    if qdate and cdt and cdt < qdate:
                        after_temporal.append(c)
                after_issue = [c for c in after_temporal if not (qissue & c["issue_keys"])]
                after_hash = [c for c in after_issue if c["diff_hash"] != qdiff_hash and c["msg_hash"] != qmsg_hash]

            # P2a fallback: repo-disjoint only, no temporal filter, if P2 has <5.
            after_p2a = [
                c for c in after_repo
                if not (qissue & c["issue_keys"])
                and c["diff_hash"] != qdiff_hash
                and c["msg_hash"] != qmsg_hash
            ]
            p2a_used = len(after_hash) < args.top_k and len(after_p2a) >= len(after_hash)
            rank_pool = after_p2a if p2a_used else after_hash

            # Rank allowed candidates: vector min-max + BM25 0.7/0.3
            q_tokens = tokenize_diff(q.get("diff", ""))
            vec_scores = minmax([c["raw_vector_score"] for c in rank_pool]) if rank_pool else []
            bm25_scores = []
            for c in rank_pool:
                cid = c["commit_id"]
                if cid not in token_cache:
                    token_cache[cid] = tokenize_diff(c["diff"])
                bm25_scores.append(bm25.score(q_tokens, token_cache[cid]))
            bm25_norm = minmax(bm25_scores) if bm25_scores else []
            for c, vs, bs, bn in zip(rank_pool, vec_scores, bm25_scores, bm25_norm):
                c["bm25_score"] = float(bs)
                c["score"] = 0.7 * vs + 0.3 * bn
            ranked = sorted(rank_pool, key=lambda x: x["score"], reverse=True)
            top = ranked[:args.top_k]

            if len(top) < args.top_k:
                n_short += 1

            top_out = []
            for c in top:
                cdt = parse_dt(c.get("date", ""))
                days = (qdate - cdt).days if (qdate and cdt) else None
                same_file = bool(qfiles & file_set(c.get("files", [])))
                same_issue = bool(qissue & c["issue_keys"])
                top_out.append({
                    "commit_id": c["commit_id"],
                    "score": c["score"],
                    "raw_vector_score": c["raw_vector_score"],
                    "bm25_score": c["bm25_score"],
                    "repo": c["repo"],
                    "date": c.get("date", ""),
                    "files": c.get("files", []),
                    "message": c["message"],
                    "diff": c["diff"],
                    "days_diff": days,
                    "temporal_ok": bool(qdate and cdt and cdt < qdate),
                    "same_file": same_file,
                    "same_issue": same_issue,
                    "exact_diff_dup": c["diff_hash"] == qdiff_hash,
                    "exact_message_dup": c["msg_hash"] == qmsg_hash,
                })
                if same_file:
                    same_file_top1 += 0
            record = {
                "id": q["id"],
                "repo": qrepo,
                "date": q.get("date", ""),
                "diff_hash": qdiff_hash,
                "message_hash": qmsg_hash,
                "pool_size": int(index.ntotal),
                "candidates_retrieved": int(k),
                "after_repo": len(after_repo),
                "after_temporal": len(after_temporal),
                "after_issue": len(after_issue),
                "after_hash": len(after_hash),
                "after_p2a": len(after_p2a),
                "p2a_fallback": p2a_used,
                "p2a_future_examples": sum(1 for x in top_out if not x["temporal_ok"]),
                "n_final": len(top_out),
                "shortfall": len(top_out) < args.top_k,
                "top5": top_out,
                "used_example_ids": [x["commit_id"] for x in top_out],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

            if top_out:
                top1_ids[top_out[0]["commit_id"]] += 1
                if top_out[0]["same_file"]:
                    same_file_top1 += 1
                if top_out[0]["days_diff"] is not None:
                    days_top1.append(top_out[0]["days_diff"])
            for x in top_out:
                exemplar_ids[x["commit_id"]] += 1

            audit_rows.append({
                "query_id": qid,
                "query_repo": qrepo,
                "query_date": q.get("date", ""),
                "pool_size": int(index.ntotal),
                "candidates_retrieved": int(k),
                "after_repo": len(after_repo),
                "after_temporal": len(after_temporal),
                "after_issue": len(after_issue),
                "after_hash": len(after_hash),
                "after_p2a": len(after_p2a),
                "p2a_fallback": p2a_used,
                "p2a_future_examples": sum(1 for x in top_out if not x["temporal_ok"]),
                "n_final": len(top_out),
                "shortfall": len(top_out) < args.top_k,
                "top1_id": top_out[0]["commit_id"] if top_out else "",
                "top1_repo": top_out[0]["repo"] if top_out else "",
                "top1_same_repo": bool(top_out and top_out[0]["repo"] == qrepo),
                "top1_same_file": bool(top_out and top_out[0]["same_file"]),
                "top1_same_issue": bool(top_out and top_out[0]["same_issue"]),
                "top1_days_diff": top_out[0]["days_diff"] if top_out else None,
                "top1_exact_dup": bool(top_out and (top_out[0]["exact_diff_dup"] or top_out[0]["exact_message_dup"])),
                "query_bare_issues": qbare,
            })
            if qi % 25 == 0 or qi == len(test):
                print(f"[{qi}/{len(test)}] short={n_short} top1={top_out[0]['commit_id'] if top_out else None}", flush=True)

    with open(out / "leakage_audit_497.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(audit_rows[0].keys()))
        writer.writeheader()
        writer.writerows(audit_rows)

    summary = {
        "test_queries": len(test),
        "pool_size": int(index.ntotal),
        "queries_with_5": sum(1 for r in audit_rows if r["n_final"] == args.top_k),
        "shortfall_queries": sum(1 for r in audit_rows if r["shortfall"]),
        "p2a_fallback_queries": sum(1 for r in audit_rows if r["p2a_fallback"]),
        "p2a_future_examples": sum(r["p2a_future_examples"] for r in audit_rows),
        "unique_top1_ids": len(top1_ids),
        "unique_exemplar_ids": len(exemplar_ids),
        "top1_max_frequency": top1_ids.most_common(5),
        "top1_same_repo": sum(1 for r in audit_rows if r["top1_same_repo"]),
        "top1_same_file": same_file_top1,
        "top1_same_issue": sum(1 for r in audit_rows if r["top1_same_issue"]),
        "top1_exact_dup": sum(1 for r in audit_rows if r["top1_exact_dup"]),
        "avg_top1_days_diff": statistics.mean(days_top1) if days_top1 else None,
    }
    with open(out / "p2_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("written", out_path)


if __name__ == "__main__":
    main()