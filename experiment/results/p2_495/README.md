# Leakage-controlled P2 dataset (497 test queries)

## What is here

| File | Contents |
|---|---|
| `split_repo_disjoint_22.json` | 22 held-out repos, seed 42, test ids, repo counts |
| `leakage_test_497.jsonl` | 497 test queries with id/repo/date/diff/message/files |
| `leakage_test_495.jsonl` | 495 strict P2 queries (excludes the 2 P2a fallback ids) |
| `pool_meta.json` | pool size (110,644 docs, 28 repos) and index paths |
| `codebert_pool.index` | pool-only FAISS index (mean-pooled CodeBERT vectors) |
| `pool_doc_ids.npy` | FAISS position -> corpus doc id |
| `doc_meta.jsonl` | cached id -> date/repo/files for the corpus |
| `top5_p2_497.jsonl` | all 497 queries with 5 exemplars (495 strict P2 + 2 P2a) |
| `top5_p2_strict_495.jsonl` | 495 strict P2 queries only |
| `p2a_fallback_2.jsonl` | 2 early-2014 CouchDB queries using P2a fallback |
| `leakage_audit_497.csv` | per-query filter counts and provenance |
| `p2_summary.json` | summary statistics |

## Test set

- Held-out repos: 22 (seed 42), listed in `split_repo_disjoint_22.json`.
- Test queries: 497, all from held-out repos.
- Pool: 110,644 CodeBERT vectors from 28 non-heldout repos.
- The pool index was built from existing mean-pooled CodeBERT vectors; the query encoder uses the same mean pooling.

## P2 filters

For each query:

1. **Repository-disjoint** — pool index excludes all 22 held-out repos; no exemplar from the query repo.
2. **Temporal** — candidate date must be strictly before the query date; missing/equal dates are excluded.
3. **Self-exclusion** — query id excluded.
4. **Same prefixed issue key** — `FLINK-1234`-style keys are excluded; bare `#123` is only reported, not filtered.
5. **Exact hash** — identical normalized diff or message is excluded.
6. **Jaccard** — not used for filtering (only exact hash).

Retrieval: pool index top-128 (fallback 4096), BM25 global-IDF rerank, 0.7 vector + 0.3 BM25, then top-5 after filters.

## Results

- 497/497 queries have 5 exemplars.
- **495 strict P2** queries: all exemplars satisfy temporal + repo + issue + exact-hash filters.
- **2 P2a fallback** queries (`147995`, `148004`, both early CouchDB 2014): temporal pool was too small, so repo-disjoint-only fallback was used; they contain **9 future exemplars** and are marked `p2a_fallback: true`.
- Same repo in top-5: **0**
- Same prefixed issue in top-5: **0**
- Exact diff/message duplicate in top-5: **0**
- Unique top-1 ids: **467**
- Unique exemplar ids: **2,218**
- Top-1 max frequency: **10** (one doc, 2% of queries)
- Top-1 same-file: **5** (reported, not filtered)
- Average top-1 days before query: **773**

## How to use

- Use `top5_p2_strict_495.jsonl` (495 queries) for the strict P2 experiment.
- Each row has `used_example_ids` and `top5` with `commit_id`, `score`,
  `raw_vector_score`, `bm25_score`, `message`, `diff`, `repo`, `date`,
  `temporal_ok`, `same_file`, `same_issue`, `exact_diff_dup`,
  `exact_message_dup`.

## P2-tool generation

Use the strict 495 set with the retained generation script:

```bash
python experiment/scripts/run_p2_tool_generation.py \
  --test experiment/outputs/leakage/leakage_test_495.jsonl \
  --top5 experiment/outputs/leakage/top5_p2_strict_495.jsonl \
  --output experiment/outputs/leakage/p2_tool_495.jsonl
```

For the 5-exemplar condition, add `--no-exemplar-cap` and write to
`experiment/outputs/leakage/p2_tool_495_5ex.jsonl`. Fill the API key in the
environment file before running.

## Caveats

- The pool has 110,644 docs, not 118,053: 15,031 corpus docs without CodeBERT vectors were skipped.
- The 2 P2a queries are early 2014 and have almost no eligible temporal history in the non-heldout pool; report them as fallback, not strict P2.
- No Jaccard near-duplicate filtering was applied, per the agreed plan.
- same-file top-1 is reported, not excluded; cross-repo file names (e.g., `CHANGES.txt`) can coincide.