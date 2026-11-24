# Experiment

This branch keeps three experiment groups:

1. **945-sample CoRaCMG-prompt validation** — reruns the 945 samples with
   CoRaCMG's `SIMILAR_PROMPT` and one exemplar, scored with the CoRaCMG metric
   pipeline.
2. **Paper Table 3 plugin comparison** — the comparison against the three
   VS Code extensions, scored from the aligned 945-sample outputs.
3. **495-sample leakage-controlled P2** — repository-disjoint split with
   temporal/issue/hash filters, 1-exemplar and 5-exemplar tool generation,
   scored with both the CoRaCMG and Table 3 pipelines.

## Layout

- `inputs/raw/`: raw plugin outputs.
- `inputs/aligned/`: outputs aligned to the 945 valid samples (Table 3 input).
- `inputs/sample_commit.jsonl`: filtered 945-sample dataset.
- `outputs/`: large per-sample JSONL outputs (ignored by Git).
- `results/`: curated small tables and reports (tracked).
- `scripts/`: experiment and scoring scripts.
- `configs/`: configuration templates and the Table 3 scoring config.
- `requirements.txt`: Python dependencies for the experiment scripts.

## Retained scripts

| Script | Group |
|---|---|
| `run_coracmg_prompt_experiment.py`, `score_coracmg_prompt_results.py` | 945 CoRaCMG prompt |
| `score_merged.py`, `summarize_scored_results.py` | Paper Table 3 plugin comparison |
| `build_leakage_split.py`, `retrieve_p2_top5.py`, `run_p2_tool_generation.py` | 495 P2 generation |
| `score_p2_tool_table3.py`, `score_p2_test_plugins_coracmg.py` | 495 P2 scoring |

## Results

`results/` contains the small result tables for the three groups:

- `results/table3/` — Table 3 summaries.
- `results/coracmg_prompt_945/` — 945-sample diagnostic and scores.
- `results/p2_495/` — 495-sample test set, tool outputs, and scores.

The large `*_tasks.jsonl`, `top5_*.jsonl`, pool index, and per-sample 945/495
JSONL files stay under `outputs/` and are distributed separately (release
archive or Zenodo).

## Inputs that are not stored in Git

- `inputs/aligned/`: required for Table 3 scoring.
- `experiment/outputs/retrieval/top5_945.jsonl`: required by the 945
  CoRaCMG-prompt run (top-1 after self-exclusion).
- `resource/`: full ApacheCM corpus and FAISS/embedding resources.

## Sample dataset

The filtered 945-sample experiment dataset is
[`inputs/sample_commit.jsonl`](inputs/sample_commit.jsonl). Each retained
sample has a non-empty `diff` field.

## Leakage-controlled experiments

The split starts from 497 queries over 22 held-out repositories; strict
temporal/issue/hash filters leave the 495-query test set used in the paper.

See [`../docs/REPRODUCE.md`](../docs/REPRODUCE.md) for commands and expected
outputs.