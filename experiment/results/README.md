# Experiment results

Curated result tables for the three experiment groups retained on this branch:

1. 945-sample CoRaCMG-prompt validation.
2. The paper's Table 3 plugin comparison.
3. The 495-sample leakage-controlled P2 experiments.

The large per-sample JSONL outputs remain under `experiment/outputs/` (ignored
by Git) and are distributed separately through a release archive or Zenodo
record. This directory keeps the small tables and reports needed to check the
paper's numbers.

| Directory | Experiment | Contents |
|---|---|---|
| `table3/` | Paper Table 3 plugin comparison | `merged_aligned_945_summary_hf.csv` (paper Table 3; NLTK METEOR). `score_merged.py` now emits the same NLTK summary under `experiment/outputs/plugin_comparison/`. |
| `coracmg_prompt_945/` | 945-sample CoRaCMG-prompt validation | diagnostic report and score tables |
| `p2_495/` | 495-sample leakage-controlled P2 | test set, 1-exemplar and 5-exemplar tool outputs, CoRaCMG/Table 3 scores, leakage audit |

Not tracked here (large/intermediate): `experiment/outputs/coracmg_prompt/cora_prompt_945*.jsonl`,
`experiment/outputs/retrieval/top5_945.jsonl`,
`experiment/outputs/leakage/top5_p2_strict_495.jsonl`,
`experiment/outputs/leakage/codebert_pool.index`,
`experiment/outputs/leakage/doc_meta.jsonl`, and the `*_tasks.jsonl` files.
They can be regenerated with the scripts or obtained from the release archive.