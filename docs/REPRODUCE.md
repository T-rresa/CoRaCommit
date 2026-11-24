# Reproducing the experiments

## Environment

```bash
conda env create -f fusion_search/environment.yml
conda activate coracommit_env
pip install -r experiment/requirements.txt
python -m nltk.downloader punkt punkt_tab wordnet omw-1.4
```

## Inputs

| Input | Path |
|---|---|
| 945 evaluation samples | `experiment/inputs/sample_commit.jsonl` |
| Full corpus | `resource/docs.jsonl` + `resource/embeddings` + `resource/faiss` |
| Demo corpus | `resource_demo/` |
| Plugin outputs | `experiment/inputs/raw/`, `experiment/inputs/aligned/` |
| 945 top-5 retrieval input | `experiment/outputs/retrieval/top5_945.jsonl` (release archive) |
| Curated result tables | `experiment/results/` |

## Plugin comparison (Table 3)

1. Ensure the four aligned outputs are present:
   - `ai-commit#deepseek_output_aligned_945.jsonl`
   - `auto_commit#output_messages_aligned_945.jsonl`
   - `auto-gen-message#experiment_results_aligned_945.jsonl`
   - `commit_sage#output_messages_aligned_945.jsonl`
2. Score:
   ```bash
   python experiment/scripts/score_merged.py \
     --config experiment/configs/score_config.json
   python experiment/scripts/summarize_scored_results.py
   ```
3. Expected outputs:
   - `experiment/outputs/plugin_comparison/merged_aligned_945_scored.jsonl`
   - `experiment/outputs/plugin_comparison/merged_aligned_945_summary.csv`
   - canonical paper result: `experiment/results/table3/merged_aligned_945_summary_hf.csv`

`score_merged.py` now uses NLTK METEOR, so the generated
`merged_aligned_945_summary.csv` should match the paper's
`merged_aligned_945_summary_hf.csv` exactly:

```bash
diff experiment/outputs/plugin_comparison/merged_aligned_945_summary.csv \
     experiment/results/table3/merged_aligned_945_summary_hf.csv
```

The Table 3 pipeline is defined in `experiment/scripts/score_merged.py`
(sacrebleu BLEU, rouge_score ROUGE-L, NLTK METEOR, PTB/pycocoevalcap CIDEr).

## Leakage-controlled P2

1. Build the 22-repo split, pool-only index, and 497 candidate queries:
   ```bash
   python experiment/scripts/build_leakage_split.py
   ```
   Strict temporal/issue/hash filters leave the 495-query test set.
2. Retrieve P2 top-5:
   ```bash
   python experiment/scripts/retrieve_p2_top5.py
   ```
3. Generate with the tool prompt and strict P2 top-5:
   ```bash
   python experiment/scripts/run_p2_tool_generation.py --no-exemplar-cap
   ```
4. Score with both pipelines:
   ```bash
   python experiment/scripts/score_p2_tool_table3.py
   python experiment/scripts/score_p2_test_plugins_coracmg.py
   ```

Outputs are under `experiment/outputs/leakage/` and
`experiment/results/p2_495/`.

## CoRaCMG-prompt diagnostic

```bash
python experiment/scripts/run_coracmg_prompt_experiment.py \
  --limit 945 --concurrency 8
```

The diagnostic uses CoRaCMG `SIMILAR_PROMPT`, one exemplar, no Conventional
constraint, and DeepSeek-V3.2. It reads top-1 exemplars (after self-exclusion)
from `experiment/outputs/retrieval/top5_945.jsonl`, distributed in the release
archive. See
`experiment/results/coracmg_prompt_945/cora_prompt_945_diagnostic.md`.

## Metrics

Two pipelines are used:

1. **Table 3 pipeline**: sacrebleu BLEU, rouge_score ROUGE-L, NLTK METEOR,
   PTB-tokenized Cider.
2. **CoRaCMG pipeline**: GLEU, HF-style ROUGE BootstrapAggregator, NLTK METEOR,
   custom Cider.

Do not compare numbers across pipelines without reading the metric footnotes.