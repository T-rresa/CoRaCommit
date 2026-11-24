# -*- coding: utf-8 -*-
"""Score P2-tool with the paper's Table 3 metric pipeline.

BLEU: sacrebleu sentence_bleu (13a, exp, effective order), per-sample mean.
ROUGE-L: rouge_score, no stemmer, per-sample mean.
METEOR: NLTK single_meteor_score, per-sample mean.
CIDEr: pycocoevalcap Cider + PTBTokenizer, corpus mean.
Normalization: NFKC, newline->space, collapse whitespace, strip, lowercase.
"""

import argparse
import csv
import json
import re
import statistics
import unicodedata
from collections import OrderedDict
from pathlib import Path

import sacrebleu
from nltk import word_tokenize
from nltk.translate import meteor_score
from rouge_score import rouge_scorer
from pycocoevalcap.cider.cider import Cider as PyCider
from pycocoevalcap.tokenizer.ptbtokenizer import PTBTokenizer

SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = SCRIPT_DIR.parent


def norm(text):
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def metrics(refs, preds):
    n = len(refs)
    rs = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
    bleu, rouge, meteor = [], [], []
    for r, p in zip(refs, preds):
        rn, pn = norm(r), norm(p)
        if not rn or not pn:
            bleu.append(0.0); rouge.append(0.0); meteor.append(0.0); continue
        bleu.append(sacrebleu.sentence_bleu(pn, [rn], tokenize="13a").score / 100.0)
        rouge.append(rs.score(rn, pn)["rougeL"].fmeasure)
        meteor.append(meteor_score.single_meteor_score(word_tokenize(rn), word_tokenize(pn)))
    ptb = PTBTokenizer()
    gts = ptb.tokenize(OrderedDict((str(i), [{"caption": norm(r)}]) for i, r in enumerate(refs)))
    res = ptb.tokenize(OrderedDict((str(i), [{"caption": norm(p)}]) for i, p in enumerate(preds)))
    cider, _ = PyCider().compute_score(gts, res)
    return {
        "n": n,
        "BLEU": sum(bleu) / n * 100,
        "ROUGE_L": sum(rouge) / n * 100,
        "METEOR": sum(meteor) / n * 100,
        "CIDEr_raw": float(cider),
        "CIDEr_table3": float(cider),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(EXPERIMENT_DIR / "outputs" / "leakage" / "p2_tool_495.jsonl"))
    parser.add_argument("--current-scored", default=str(EXPERIMENT_DIR / "outputs" / "plugin_comparison" / "merged_aligned_945_scored_hf.jsonl"))
    parser.add_argument("--output-csv", default=str(EXPERIMENT_DIR / "outputs" / "reports" / "p2_tool_495_scores_table3.csv"))
    parser.add_argument("--output-md", default=str(EXPERIMENT_DIR / "outputs" / "reports" / "p2_tool_495_scores_table3.md"))
    args = parser.parse_args()
    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)

    results = [r for r in read_jsonl(args.results) if r.get("status") == "success"]
    current = {}
    for r in read_jsonl(args.current_scored):
        sid = str(r["id"])
        pr = next((x for x in r.get("plugin_results", []) if x["plugin_name"] == "auto-gen-message"), None)
        if pr:
            current[sid] = {"label": r.get("ground_truth", ""), "pred": pr.get("generated_message", "")}

    new_refs, new_preds = [], []
    cur_refs, cur_preds = [], []
    for r in results:
        sid = str(r.get("id"))
        if sid not in current:
            continue
        new_refs.append(r.get("label", "") or current[sid]["label"])
        new_preds.append(r.get("pred", ""))
        cur_refs.append(current[sid]["label"])
        cur_preds.append(current[sid]["pred"])

    new_m = metrics(new_refs, new_preds)
    cur_m = metrics(cur_refs, cur_preds)
    rows = [("P2-tool (495)", new_m), ("P3 original (same 495)", cur_m)]
    with open(args.output_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["setting", "n", "BLEU", "ROUGE-L", "METEOR", "CIDEr"])
        for name, m in rows:
            w.writerow([name, m["n"], round(m["BLEU"], 4), round(m["ROUGE_L"], 4), round(m["METEOR"], 4), round(m["CIDEr_table3"], 4)])
    lines = [
        "# P2-tool vs P3 original (Table 3 metric pipeline)",
        "",
        "| Setting | n | BLEU | ROUGE-L | METEOR | CIDEr |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, m in rows:
        lines.append(f"| {name} | {m['n']} | {m['BLEU']:.2f} | {m['ROUGE_L']:.2f} | {m['METEOR']:.2f} | {m['CIDEr_table3']:.4f} |")
    lines += [
        "",
        "BLEU/ROUGE/METEOR are 0-100; CIDEr is the raw 0-10 Cider score.",
    ]
    open(args.output_md, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("written", args.output_csv)
    print("written", args.output_md)


if __name__ == "__main__":
    main()