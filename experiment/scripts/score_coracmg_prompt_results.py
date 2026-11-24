# -*- coding: utf-8 -*-
"""Score the CoRaCMG-prompt rerun with CoRaCMG's metric pipeline.

Compares:
  - new CoRaCMG-prompt outputs (single exemplar, no Conventional constraint)
  - current CoRaCommit outputs on the same sample ids
  - CoRaCMG paper-reported values (different dataset/model; reference only)

Metrics: GLEU, ROUGE-L BootstrapAggregator, NLTK METEOR, custom CIDEr.
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
    parser.add_argument("--results", default=str(EXPERIMENT_DIR / "outputs" / "coracmg_prompt" / "cora_prompt_500.jsonl"))
    parser.add_argument("--current-scored", default=str(EXPERIMENT_DIR / "outputs" / "plugin_comparison" / "merged_aligned_945_scored_hf.jsonl"))
    parser.add_argument("--output-csv", default=str(EXPERIMENT_DIR / "outputs" / "reports" / "cora_prompt_500_scores.csv"))
    parser.add_argument("--output-md", default=str(EXPERIMENT_DIR / "outputs" / "reports" / "cora_prompt_500_scores.md"))
    parser.add_argument("--label-new", default="new: CoRaCMG prompt + 1 exemplar")
    parser.add_argument("--label-current", default="current: CoRaCommit (same ids)")
    parser.add_argument("--label-reported", default="CoRaCMG paper (reference)")
    args = parser.parse_args()
    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)

    results = []
    for r in read_jsonl(args.results):
        if r.get("status") == "success" and r.get("pred") is not None:
            results.append(r)

    current = {}
    for r in read_jsonl(args.current_scored):
        sid = str(r["id"])
        pr = next((x for x in r.get("plugin_results", []) if x["plugin_name"] == "auto-gen-message"), None)
        if pr:
            current[sid] = {"label": r.get("ground_truth", ""), "pred": pr.get("generated_message", "")}

    new_refs, new_preds = [], []
    cur_refs, cur_preds = [], []
    prompt_tokens = completion_tokens = 0
    for r in results:
        sid = str(r.get("id"))
        if sid not in current:
            continue
        ref = r.get("label", "") or current[sid]["label"]
        new_refs.append(ref)
        new_preds.append(r.get("pred", ""))
        cur_refs.append(current[sid]["label"])
        cur_preds.append(current[sid]["pred"])
        usage = r.get("usage") or {}
        prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens += int(usage.get("completion_tokens", 0) or 0)

    new_m = metrics(new_refs, new_preds)
    cur_m = metrics(cur_refs, cur_preds)
    # CoRaCMG paper-reported values (DeepSeek-R1, ApacheCM-10K): reference only.
    reported = {
        "n": "paper (different data/model)",
        "BLEU_GLEU": 17.42,
        "ROUGE_L": 29.10,
        "METEOR": 28.76,
        "CIDEr_scorer": None,
        "CIDEr_eval_print": 13.32,
    }

    rows = [
        (args.label_new, new_m),
        (args.label_current, cur_m),
        (args.label_reported, reported),
    ]
    with open(args.output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["setting", "n", "BLEU_GLEU", "ROUGE_L", "METEOR", "CIDEr_scorer", "CIDEr_eval_print"])
        for name, m in rows:
            writer.writerow([name, m["n"], round(m["BLEU_GLEU"], 4), round(m["ROUGE_L"], 4),
                             round(m["METEOR"], 4),
                             "" if m["CIDEr_scorer"] is None else round(m["CIDEr_scorer"], 4),
                             round(m["CIDEr_eval_print"], 4)])

    lines = [
        "# CoRaCMG-prompt rerun (single exemplar, first 500)",
        "",
        f"- scored samples: {new_m['n']}",
        f"- prompt tokens: {prompt_tokens:,}",
        f"- completion tokens: {completion_tokens:,}",
        f"- estimated cost (CNY, input 2/M, output 3/M): "
        f"¥{prompt_tokens * 2.0 / 1_000_000 + completion_tokens * 3.0 / 1_000_000:.2f}",
        "",
        "| Setting | n | BLEU (GLEU) | ROUGE-L | METEOR | CIDEr (scorer) | CIDEr (eval print) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m in rows:
        cider_scorer = "" if m["CIDEr_scorer"] is None else f"{m['CIDEr_scorer']:.4f}"
        lines.append(
            f"| {name} | {m['n']} | {m['BLEU_GLEU']:.2f} | {m['ROUGE_L']:.2f} | {m['METEOR']:.2f} | "
            f"{cider_scorer} | {m['CIDEr_eval_print']:.2f} |"
        )
    lines += [
        "",
        "Notes:",
        "- CoRaCMG reported values use DeepSeek-R1 and ApacheCM-10K; the rerun uses DeepSeek-V3.2 and the first 500 samples.",
        "- CIDEr_scorer is the CiderScorer output; CoRaCMG eval.py prints it ×10, shown as CIDEr_eval_print.",
    ]
    open(args.output_md, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("scored", new_m["n"], "samples")
    for name, m in rows:
        print(f"{name}: n={m['n']} BLEU={m['BLEU_GLEU']:.2f} ROUGE={m['ROUGE_L']:.2f} "
              f"METEOR={m['METEOR']:.2f} CIDEr={m['CIDEr_eval_print']:.2f}")
    print("written", args.output_csv)
    print("written", args.output_md)


if __name__ == "__main__":
    main()