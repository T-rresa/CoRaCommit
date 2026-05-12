import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
COMPARE_ROOT = SCRIPT_DIR.parent

def read_jsonl(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows):
    out = "\n".join(json.dumps(o, ensure_ascii=False, separators=(",", ":")) for o in rows)
    if out:
        out += "\n"
    path.write_text(out, encoding="utf-8")


def load_config(config_path: Path):
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    cfg.setdefault("score_scale", "0_1")
    config_dir = config_path.resolve().parent
    for key in ["input_jsonl", "output_jsonl"]:
        if key in cfg:
            value = Path(cfg[key])
            if not value.is_absolute():
                cfg[key] = str((config_dir / value).resolve())
    cfg.setdefault("empty_output_strategy", "empty_string")
    cfg.setdefault("normalize", {})
    cfg.setdefault("bleu", {"enabled": True})
    cfg.setdefault("rouge", {"enabled": True})
    cfg.setdefault("meteor", {"enabled": True})
    cfg.setdefault("cider", {"enabled": True})
    return cfg


def normalize_text(text: str, norm_cfg: dict):
    if text is None:
        text = ""
    if not isinstance(text, str):
        text = str(text)

    if norm_cfg.get("unicode_nfkc", True):
        import unicodedata

        text = unicodedata.normalize("NFKC", text)

    if norm_cfg.get("newline_to_space", True):
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")

    if norm_cfg.get("collapse_whitespace", True):
        text = re.sub(r"\s+", " ", text)

    if norm_cfg.get("strip", True):
        text = text.strip()

    if norm_cfg.get("lowercase", True):
        text = text.lower()

    return text


def apply_scale(value, scale: str, metric_name: str):
    if value is None:
        return None
    if scale == "0_100":
        return float(value)
    if scale == "0_1":
        if metric_name == "BLEU":
            return float(value) / 100.0
        if metric_name == "CIDEr":
            return float(value) / 10.0
        return float(value)
    raise ValueError(f"Unknown score_scale: {scale}")


def compute_bleu_sacrebleu(hyps, refs, bleu_cfg: dict):
    import sacrebleu

    tokenize = bleu_cfg.get("tokenize", "13a")
    smooth_method = bleu_cfg.get("smooth_method", "exp")
    smooth_value = bleu_cfg.get("smooth_value", None)
    lowercase = bool(bleu_cfg.get("lowercase", False))
    use_effective_order = bool(bleu_cfg.get("use_effective_order", True))

    scores = []
    for h, r in zip(hyps, refs):
        if h == "" or r == "":
            scores.append(0.0)
            continue
        s = sacrebleu.sentence_bleu(
            h,
            [r],
            tokenize=tokenize,
            smooth_method=smooth_method,
            smooth_value=smooth_value,
            lowercase=lowercase,
            use_effective_order=use_effective_order,
        )
        scores.append(float(s.score))
    return scores


def compute_rouge_l_rouge_score(hyps, refs, rouge_cfg: dict):
    from rouge_score import rouge_scorer

    use_stemmer = bool(rouge_cfg.get("use_stemmer", False))
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=use_stemmer)
    scores = []
    for h, r in zip(hyps, refs):
        if h == "" or r == "":
            scores.append(0.0)
            continue
        s = scorer.score(r, h)["rougeL"].fmeasure
        scores.append(float(s))
    return scores


def _parse_meteor_segment_scores(stdout: str, stderr: str, expected_count: int):
    seg_re = re.compile(
        r"^\s*Segment\s+(\d+)\s+score:\s*([0-9]*\.?[0-9]+)\s*$",
        flags=re.MULTILINE,
    )
    float_line_re = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*$")

    combined = (stderr or "") + "\n" + (stdout or "")

    pairs = seg_re.findall(combined)
    if pairs:
        scores = [None] * expected_count
        for idx_str, score_str in pairs:
            idx = int(idx_str)
            if 1 <= idx <= expected_count:
                scores[idx - 1] = float(score_str)
        if any(s is None for s in scores):
            missing = sum(1 for s in scores if s is None)
            raise RuntimeError(f"METEOR output missing {missing}/{expected_count} segment scores")
        return scores

    def parse_float_lines(text: str):
        vals = []
        for line in (text or "").splitlines():
            m = float_line_re.match(line)
            if m:
                vals.append(float(m.group(1)))
        return vals

    vals = parse_float_lines(stderr)
    if len(vals) == expected_count:
        return vals

    vals = parse_float_lines(combined)
    if len(vals) >= expected_count:
        return vals[:expected_count]

    preview = (combined[:1200] + "…") if len(combined) > 1200 else combined
    raise RuntimeError(f"Failed to parse METEOR segment scores from output. Output preview:\n{preview}")


def compute_meteor_official_jar(hyps, refs, meteor_cfg: dict, empty_strategy: str):
    java_bin = meteor_cfg.get("java", "java")
    jar_path = meteor_cfg.get("jar_path")
    if not jar_path:
        raise ValueError("meteor.jar_path is required when meteor.enabled=true")
    jar_path = str(Path(jar_path))
    language = meteor_cfg.get("language", "en")
    memory = meteor_cfg.get("memory", "2G")
    use_norm = bool(meteor_cfg.get("normalize", True))
    use_lower = bool(meteor_cfg.get("lowercase_only", False))

    active_indices = []
    active_hyps = []
    active_refs = []
    for i, (h, r) in enumerate(zip(hyps, refs)):
        if empty_strategy == "skip" and (h == "" or r == ""):
            continue
        active_indices.append(i)
        active_hyps.append(h)
        active_refs.append(r)

    if not active_indices:
        return [None] * len(hyps)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        hyp_path = td_path / "hyp.txt"
        ref_path = td_path / "ref.txt"
        hyp_path.write_text("\n".join(active_hyps) + "\n", encoding="utf-8")
        ref_path.write_text("\n".join(active_refs) + "\n", encoding="utf-8")

        args = [java_bin, f"-Xmx{memory}", "-jar", jar_path, str(hyp_path), str(ref_path), "-l", language, "-q"]
        if use_norm:
            args.append("-norm")
        elif use_lower:
            args.append("-lower")

        proc = subprocess.run(args, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"METEOR failed (exit={proc.returncode}): {proc.stderr or proc.stdout}")

        stderr = proc.stderr or ""
        stdout = proc.stdout or ""
        seg_scores = _parse_meteor_segment_scores(stdout, stderr, len(active_indices))

    out = [None] * len(hyps)
    for idx, score in zip(active_indices, seg_scores):
        out[idx] = float(score)
    if empty_strategy == "empty_string":
        out = [0.0 if s is None else s for s in out]
    return out


def compute_cider_pycocoevalcap(hyps, refs, cider_cfg: dict, empty_strategy: str):
    from pycocoevalcap.cider.cider import Cider
    from pycocoevalcap.tokenizer.ptbtokenizer import PTBTokenizer

    active_indices = []
    gts = {}
    res = {}
    for i, (h, r) in enumerate(zip(hyps, refs)):
        if empty_strategy == "skip" and (h == "" or r == ""):
            continue
        key = str(i)
        active_indices.append(i)
        gts[key] = [{"caption": r}]
        res[key] = [{"caption": h}]

    if not active_indices:
        return [None] * len(hyps)

    tokenizer = PTBTokenizer()
    gts_tok = tokenizer.tokenize(gts)
    res_tok = tokenizer.tokenize(res)
    scorer = Cider()
    _, scores = scorer.compute_score(gts_tok, res_tok)

    out = [None] * len(hyps)
    for idx, score in zip(active_indices, scores):
        out[idx] = float(score)
    if empty_strategy == "empty_string":
        out = [0.0 if s is None else s for s in out]
    return out


def compute_bertscore_f1(hyps, refs, bertscore_cfg: dict, empty_strategy: str):
    try:
        from bert_score import score as bert_score
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Missing dependency 'bert-score'. Install with: python -m pip install --user bert-score"
        ) from e

    model_type = bertscore_cfg.get("model_type", "roberta-large")
    lang = bertscore_cfg.get("lang", "en")
    batch_size = int(bertscore_cfg.get("batch_size", 32))
    rescale_with_baseline = bool(bertscore_cfg.get("rescale_with_baseline", True))
    device = bertscore_cfg.get("device", None)

    active_indices = []
    cands = []
    refs_active = []
    for i, (h, r) in enumerate(zip(hyps, refs)):
        if h == "" or r == "":
            continue
        active_indices.append(i)
        cands.append(h)
        refs_active.append(r)

    out = [None] * len(hyps)
    if not active_indices:
        if empty_strategy == "empty_string":
            return [0.0] * len(hyps)
        return out

    P, R, F = bert_score(
        cands,
        refs_active,
        model_type=model_type,
        lang=lang,
        batch_size=batch_size,
        rescale_with_baseline=rescale_with_baseline,
        device=device,
        verbose=False,
    )
    f_list = [float(x) for x in F.tolist()]

    for idx, f1 in zip(active_indices, f_list):
        out[idx] = f1

    if empty_strategy == "empty_string":
        out = [0.0 if v is None else v for v in out]

    return out


def build_scores_for_sample(bleu_v, rouge_v, meteor_v, cider_v, scale: str):
    return [
        {"metrics": "BLEU", "score": None if bleu_v is None else round(apply_scale(bleu_v, scale, "BLEU"), 6)},
        {"metrics": "Rouge-L", "score": None if rouge_v is None else round(apply_scale(rouge_v, scale, "Rouge-L"), 6)},
        {"metrics": "METEOR", "score": None if meteor_v is None else round(apply_scale(meteor_v, scale, "METEOR"), 6)},
        {"metrics": "CIDEr", "score": None if cider_v is None else round(apply_scale(cider_v, scale, "CIDEr"), 6)},
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(COMPARE_ROOT / "configs" / "score_config.json"))
    args = parser.parse_args()

    config_path = Path(args.config)
    cfg = load_config(config_path)

    base_dir = config_path.parent.resolve()
    input_path = Path(cfg.get("input_jsonl", "merged_aligned_945.jsonl"))
    if not input_path.is_absolute():
        input_path = base_dir / input_path
    output_path = Path(cfg.get("output_jsonl", str(input_path)))
    if not output_path.is_absolute():
        output_path = base_dir / output_path

    rows = read_jsonl(input_path)
    empty_strategy = cfg.get("empty_output_strategy", "empty_string")
    norm_cfg = cfg.get("normalize", {})
    scale = cfg.get("score_scale", "0_1")

    refs = [normalize_text(r.get("ground_truth", ""), norm_cfg) for r in rows]

    plugin_names = []
    if rows:
        plugin_names = [p.get("plugin_name") for p in rows[0].get("plugin_results", [])]

    plugin_hyps = {}
    for pn in plugin_names:
        plugin_hyps[pn] = []

    for r in rows:
        prs = r.get("plugin_results", [])
        by_name = {p.get("plugin_name"): p for p in prs}
        for pn in plugin_names:
            hyp = by_name.get(pn, {}).get("generated_message", "")
            plugin_hyps[pn].append(normalize_text(hyp, norm_cfg))

    bleu_cfg = cfg.get("bleu", {})
    rouge_cfg = cfg.get("rouge", {})
    meteor_cfg = cfg.get("meteor", {})
    cider_cfg = cfg.get("cider", {})
    bertscore_cfg = cfg.get("bertscore", {"enabled": False})

    if meteor_cfg.get("enabled", True) and not meteor_cfg.get("jar_path"):
        meteor_cfg["enabled"] = False

    per_plugin_scores = {}
    for pn in plugin_names:
        hyps = plugin_hyps[pn]
        bleu_scores = [None] * len(rows)
        rouge_scores = [None] * len(rows)
        meteor_scores = [None] * len(rows)
        cider_scores = [None] * len(rows)
        bert_f1_scores = [None] * len(rows)

        if bleu_cfg.get("enabled", True):
            bleu_scores = compute_bleu_sacrebleu(hyps, refs, bleu_cfg)
            if empty_strategy == "skip":
                bleu_scores = [None if (h == "" or r == "") else s for h, r, s in zip(hyps, refs, bleu_scores)]
        if rouge_cfg.get("enabled", True):
            rouge_scores = compute_rouge_l_rouge_score(hyps, refs, rouge_cfg)
            if empty_strategy == "skip":
                rouge_scores = [None if (h == "" or r == "") else s for h, r, s in zip(hyps, refs, rouge_scores)]
        if meteor_cfg.get("enabled", True):
            meteor_scores = compute_meteor_official_jar(hyps, refs, meteor_cfg, empty_strategy)
        if cider_cfg.get("enabled", True):
            cider_scores = compute_cider_pycocoevalcap(hyps, refs, cider_cfg, empty_strategy)
        if bertscore_cfg.get("enabled", False):
            bert_f1_scores = compute_bertscore_f1(hyps, refs, bertscore_cfg, empty_strategy)

        per_plugin_scores[pn] = {
            "BLEU": bleu_scores,
            "Rouge-L": rouge_scores,
            "METEOR": meteor_scores,
            "CIDEr": cider_scores,
            "BERTScore-F1": bert_f1_scores,
        }

    for i, r in enumerate(rows):
        for pr in r.get("plugin_results", []):
            pn = pr.get("plugin_name")
            scores_map = per_plugin_scores.get(pn, {})
            scores = build_scores_for_sample(
                scores_map.get("BLEU", [None] * len(rows))[i],
                scores_map.get("Rouge-L", [None] * len(rows))[i],
                scores_map.get("METEOR", [None] * len(rows))[i],
                scores_map.get("CIDEr", [None] * len(rows))[i],
                scale,
            )
            bert_v = scores_map.get("BERTScore-F1", [None] * len(rows))[i]
            scores.append({"metrics": "BERTScore-F1", "score": None if bert_v is None else round(float(bert_v), 6)})
            pr["scores"] = scores

    write_jsonl(output_path, rows)


if __name__ == "__main__":
    main()
