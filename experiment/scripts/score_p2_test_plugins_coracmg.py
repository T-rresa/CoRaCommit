# -*- coding: utf-8 -*-
"""Score original plugin outputs on the 495 P2 test ids (CoRaCMG metrics).

Inputs:
  - experiment/outputs/plugin_comparison/merged_aligned_945_scored_hf.jsonl
  - experiment/outputs/leakage/leakage_test_495.jsonl
  - experiment/outputs/leakage/p2_tool_495_5ex.jsonl (optional context)
  - experiment/outputs/leakage/p2_tool_495.jsonl (capped, optional context)

Outputs:
  - revision/p2_test495_plugin_scores_coracmg.csv / .md
"""

import argparse
import csv
import json
import os
import re
import statistics
import sys
from collections import OrderedDict
from pathlib import Path

from nltk import word_tokenize
from nltk.translate import gleu_score, meteor_score
from rouge_score import rouge_scorer, scoring
from sacrebleu.tokenizers.tokenizer_13a import Tokenizer13a

SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = SCRIPT_DIR.parent

CORACMG_METRIC_DIR = os.environ.get("CORACMG_METRIC_DIR")
if CORACMG_METRIC_DIR:
    sys.path.insert(0, CORACMG_METRIC_DIR)
try:
    from cider_scorer import CiderScorer
except ModuleNotFoundError as exc:
    raise SystemExit(
        "cider_scorer not found. Clone CoRaCMG and set "
        "CORACMG_METRIC_DIR=/path/to/CoRaCMG/scripts/metric"
    ) from exc


def tokenize_custom(text):
    tokens = Tokenizer13a()(text).split()
    def split_symbols(tok):
        return re.sub(r"([^a-zA-Z0-9])", r" \1 ", tok).split()
    def split_camel(tok):
        return re.sub(r"(?<!^)(?=[A-Z][a-z])", " ", tok).split()
    out = []
    for tok in tokens:
        for part in split_symbols(tok):
            out.extend(split_camel(part))
    return [x.lower() for x in out]


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def metrics(refs, preds):
    n = len(refs)
    ref_tok = [[tokenize_custom(r)] for r in refs]
    pred_tok = [tokenize_custom(p) for p in preds]
    gleu = gleu_score.corpus_gleu(ref_tok, pred_tok) * 100

    rs = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
    agg = scoring.BootstrapAggregator()
    meteor = []
    for r, p in zip(refs, preds):
        agg.add_scores(rs.score(r, p))
        meteor.append(meteor_score.single_meteor_score(word_tokenize(r), word_tokenize(p)))
    rouge = agg.aggregate()["rougeL"].mid.fmeasure * 100

    scorer = CiderScorer(n=4, sigma=6.0)
    for r, p in zip(refs, preds):
        scorer += (" ".join(tokenize_custom(p)), [" ".join(tokenize_custom(r))])
    cider, _ = scorer.compute_score()
    return {
        "n": n,
        "BLEU_GLEU": gleu,
        "ROUGE_L": float(rouge),
        "METEOR": statistics.mean(meteor) * 100,
        "CIDEr_scorer": float(cider),
        "CIDEr_eval_print": float(cider) * 10,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scored", default=str(EXPERIMENT_DIR / "outputs" / "plugin_comparison" / "merged_aligned_945_scored_hf.jsonl"))
    parser.add_argument("--test", default=str(EXPERIMENT_DIR / "outputs" / "leakage" / "leakage_test_495.jsonl"))
    parser.add_argument("--p2-tool-5ex", default=str(EXPERIMENT_DIR / "outputs" / "leakage" / "p2_tool_495_5ex.jsonl"))
    parser.add_argument("--output-csv", default=str(EXPERIMENT_DIR / "outputs" / "reports" / "p2_test495_plugin_scores_coracmg.csv"))
    parser.add_argument("--output-md", default=str(EXPERIMENT_DIR / "outputs" / "reports" / "p2_test495_plugin_scores_coracmg.md"))
    args = parser.parse_args()
    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)

    test_ids = [str(r["id"]) for r in read_jsonl(args.test)]
    test_set = set(test_ids)
    scored = {str(r["id"]): r for r in read_jsonl(args.scored)}
    missing = [i for i in test_ids if i not in scored]
    print("test ids", len(test_ids), "missing in scored", len(missing))

    plugin_names = ["ai-commit", "auto_commit", "auto-gen-message", "commit_sage"]
    display = {
        "ai-commit": "AI Commit",
        "auto_commit": "Auto Commit Message",
        "auto-gen-message": "CoRaCommit (old run)",
        "commit_sage": "Commit Sage",
    }
    rows = []
    for plugin in plugin_names:
        refs, preds = [], []
        for tid in test_ids:
            row = scored[tid]
            pr = next((x for x in row.get("plugin_results", []) if x["plugin_name"] == plugin), None)
            if not pr:
                continue
            refs.append(row.get("ground_truth", ""))
            preds.append(pr.get("generated_message", ""))
        m = metrics(refs, preds)
        rows.append((display[plugin], m))

    # Context row: P2-tool 5ex on the same ids.
    for path, label in [
        (args.p2_tool_5ex, "P2-tool 5ex"),
    ]:
        try:
            results = {str(r["id"]): r for r in read_jsonl(path) if r.get("status") == "success"}
        except FileNotFoundError:
            continue
        refs, preds = [], []
        for tid in test_ids:
            if tid not in results or tid not in scored:
                continue
            refs.append(scored[tid].get("ground_truth", ""))
            preds.append(results[tid].get("pred", ""))
        if refs:
            rows.append((label, metrics(refs, preds)))

    rows.append(("CoRaCMG paper (reference)", {
        "n": "ApacheCM-10K",
        "BLEU_GLEU": 17.42,
        "ROUGE_L": 29.10,
        "METEOR": 28.76,
        "CIDEr_scorer": None,
        "CIDEr_eval_print": 13.32,
    }))

    with open(args.output_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["setting", "n", "BLEU_GLEU", "ROUGE_L", "METEOR", "CIDEr_scorer", "CIDEr_eval_print"])
        for name, m in rows:
            w.writerow([name, m["n"], round(m["BLEU_GLEU"], 4), round(m["ROUGE_L"], 4),
                        round(m["METEOR"], 4),
                        "" if m["CIDEr_scorer"] is None else round(m["CIDEr_scorer"], 4),
                        round(m["CIDEr_eval_print"], 4)])

    lines = [
        "# Other plugins on the 495 P2 test set (CoRaCMG metrics)",
        "",
        "| Setting | n | BLEU (GLEU) | ROUGE-L | METEOR | CIDEr (scorer) | CIDEr (eval print) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m in rows:
        cider = "" if m["CIDEr_scorer"] is None else f"{m['CIDEr_scorer']:.4f}"
        lines.append(f"| {name} | {m['n']} | {m['BLEU_GLEU']:.2f} | {m['ROUGE_L']:.2f} | {m['METEOR']:.2f} | {cider} | {m['CIDEr_eval_print']:.2f} |")
    lines += [
        "",
        "Notes:",
        "- All rows except the CoRaCMG paper reference are on the same 495 strict P2 test ids.",
        "- CoRaCommit (old run) is the legacy Table 3 output; its example_ids were empty, so it likely ran without retrieval.",
        "- CIDEr_eval_print follows CoRaCMG eval.py (CiderScorer output x10).",
    ]
    open(args.output_md, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("written", args.output_csv)
    print("written", args.output_md)


if __name__ == "__main__":
    main()