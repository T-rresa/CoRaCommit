import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
#Experimental script for model scoring update strategy

SCRIPT_DIR = Path(__file__).resolve().parent
COMPARE_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = COMPARE_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.embedding.codebert import CodeBERTEmbedding
from app.embedding.jina import JinaEmbedding
from app.utils.rouge import calculate_rouge_l


def parse_args():
    parser = argparse.ArgumentParser(
        description="Precompute SimScore and replay offline model recommendation strategies."
    )
    parser.add_argument(
        "--input",
        default=str(COMPARE_ROOT / "outputs" / "recommendation" / "recommendation_generation_results.jsonl"),
        help="Path to the generated multi-model result jsonl file.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(COMPARE_ROOT / "outputs" / "recommendation_replay"),
        help="Directory to store intermediate and summary outputs.",
    )
    parser.add_argument(
        "--fixed-model",
        default="deepseek-chat",
        help="Model used by the fixed-model baseline and cold-start fallback.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional number of valid samples to replay. Use 0 for all valid samples.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.7,
        help="Weight of semantic similarity in SimScore.",
    )
    parser.add_argument(
        "--beta",
        type=float,
        default=0.3,
        help="Weight of lexical similarity in SimScore.",
    )
    parser.add_argument(
        "--lambda-val",
        type=float,
        default=0.7,
        help="Weight of SingleScore in FinalScore.",
    )
    parser.add_argument(
        "--w1",
        type=float,
        default=0.6,
        help="Weight of SimScore in SingleScore.",
    )
    parser.add_argument(
        "--w2",
        type=float,
        default=0.4,
        help="Weight of PreferenceScore in SingleScore.",
    )
    parser.add_argument(
        "--s1",
        type=float,
        default=0.9,
        help="Preference score when selected output is accepted without edits.",
    )
    parser.add_argument(
        "--s2",
        type=float,
        default=0.6,
        help="Preference score when selected output is selected but edited.",
    )
    parser.add_argument(
        "--ema-alpha",
        type=float,
        default=0.1,
        help="EMA factor for global and example-level updates.",
    )
    parser.add_argument(
        "--semantic-model",
        default="codebert",
        choices=["codebert", "jina"],
        help="Embedding model used for semantic similarity.",
    )
    return parser.parse_args()


def read_jsonl(path: Path):
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(path: Path, rows):
    with open(path, "w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_text(text):
    if text is None:
        return ""
    text = str(text)
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def safe_round(value, digits=6):
    if value is None:
        return None
    return round(float(value), digits)


def round_nested(value, digits=6):
    if isinstance(value, dict):
        return {key: round_nested(sub_value, digits) for key, sub_value in value.items()}
    if isinstance(value, list):
        return [round_nested(item, digits) for item in value]
    if isinstance(value, (int, float, np.integer, np.floating)):
        return safe_round(value, digits)
    return value


def build_encoder(model_name: str):
    if model_name == "codebert":
        return CodeBERTEmbedding()
    if model_name == "jina":
        return JinaEmbedding()
    raise ValueError(f"Unsupported semantic model: {model_name}")


def compute_semantic_score(encoder, generated_message: str, ground_truth: str) -> float:
    if not generated_message or not ground_truth:
        return 0.0

    vec_gen = encoder.encode(generated_message)
    vec_gt = encoder.encode(ground_truth)
    dot_product = np.dot(vec_gen, vec_gt)
    norm_gen = np.linalg.norm(vec_gen)
    norm_gt = np.linalg.norm(vec_gt)
    if norm_gen <= 0 or norm_gt <= 0:
        return 0.0
    return float(dot_product / (norm_gen * norm_gt))


def compute_similarity_metrics(encoder, generated_message: str, ground_truth: str, alpha: float, beta: float):
    semantic_score = compute_semantic_score(encoder, generated_message, ground_truth)
    lexical_score = calculate_rouge_l(generated_message, ground_truth)
    similarity_score = alpha * semantic_score + beta * lexical_score
    return {
        "semantic_score": semantic_score,
        "lexical_score": lexical_score,
        "sim_score": similarity_score,
    }


def build_candidate_payload(record):
    payload = []
    for candidate in record.get("candidates", []):
        generated_message = candidate.get("generated_message")
        if generated_message is None:
            generated_message = candidate.get("message", "")
        model = candidate.get("model")
        if not model:
            continue
        payload.append({
            "model": model,
            "generated_message": generated_message or "",
        })
    return payload


def load_valid_records(input_path: Path, limit: int):
    valid_records = []
    skipped = []

    for raw_record in read_jsonl(input_path):
        status = raw_record.get("status")
        if status and status != "success":
            skipped.append({"id": raw_record.get("id"), "reason": status})
            continue

        candidates = build_candidate_payload(raw_record)
        if len(candidates) < 2:
            skipped.append({"id": raw_record.get("id"), "reason": "insufficient_candidates"})
            continue

        ground_truth = raw_record.get("ground_truth", "")
        if not normalize_text(ground_truth):
            skipped.append({"id": raw_record.get("id"), "reason": "empty_ground_truth"})
            continue

        valid_records.append(raw_record)
        if limit and len(valid_records) >= limit:
            break

    return valid_records, skipped


def precompute_sim_scores(records, encoder, args):
    sim_rows = []

    for index, record in enumerate(records, start=1):
        candidates = build_candidate_payload(record)
        candidate_metrics = []

        for candidate in candidates:
            metrics = compute_similarity_metrics(
                encoder=encoder,
                generated_message=candidate["generated_message"],
                ground_truth=record["ground_truth"],
                alpha=args.alpha,
                beta=args.beta,
            )
            candidate_metrics.append({
                "model": candidate["model"],
                "generated_message": candidate["generated_message"],
                "metrics": metrics,
            })

        selected_by_similarity = max(candidate_metrics, key=lambda item: item["metrics"]["sim_score"])
        is_edited = normalize_text(selected_by_similarity["generated_message"]) != normalize_text(record["ground_truth"])

        sim_rows.append({
            "index": index,
            "id": record.get("id"),
            "timestamp": record.get("timestamp"),
            "used_example_ids": record.get("used_example_ids", []) or [],
            "ground_truth": record["ground_truth"],
            "selected_by_similarity": {
                "model": selected_by_similarity["model"],
                "sim_score": safe_round(selected_by_similarity["metrics"]["sim_score"]),
            },
            "is_edited": is_edited,
            "candidates": [
                {
                    "model": item["model"],
                    "generated_message": item["generated_message"],
                    "metrics": {
                        "semantic_score": safe_round(item["metrics"]["semantic_score"]),
                        "lexical_score": safe_round(item["metrics"]["lexical_score"]),
                        "sim_score": safe_round(item["metrics"]["sim_score"]),
                    },
                }
                for item in candidate_metrics
            ],
        })

    return sim_rows


def evaluate_candidates_from_sim(record, args):
    selected_model = record["selected_by_similarity"]["model"]
    is_edited = bool(record["is_edited"])
    evaluated_candidates = []
    max_single_score = 0.0

    for candidate in record["candidates"]:
        model = candidate["model"]
        sim_score = float(candidate["metrics"]["sim_score"])
        user_preference = 0.3
        if model == selected_model:
            user_preference = args.s1 if not is_edited else args.s2

        single_score = args.w1 * sim_score + args.w2 * user_preference
        max_single_score = max(max_single_score, single_score)

        evaluated_candidates.append({
            "model": model,
            "generated_message": candidate["generated_message"],
            "metrics": {
                "semantic_score": float(candidate["metrics"]["semantic_score"]),
                "lexical_score": float(candidate["metrics"]["lexical_score"]),
                "sim_score": sim_score,
                "user_preference": user_preference,
                "single_score": single_score,
                "compare_score": 0.0,
                "final_score": 0.0,
            },
        })

    if max_single_score <= 0:
        max_single_score = 1.0

    for candidate in evaluated_candidates:
        single_score = candidate["metrics"]["single_score"]
        compare_score = single_score / max_single_score
        final_score = args.lambda_val * single_score + (1.0 - args.lambda_val) * compare_score
        candidate["metrics"]["compare_score"] = compare_score
        candidate["metrics"]["final_score"] = final_score

    return evaluated_candidates


class ReplayState:
    def __init__(self, fixed_model, ema_alpha):
        self.fixed_model = fixed_model
        self.ema_alpha = ema_alpha
        self.global_mean_sum = defaultdict(float)
        self.global_mean_count = defaultdict(int)
        self.global_ema = {}
        self.example_model_scores = defaultdict(dict)
        self.strategy_records = defaultdict(list)

    def choose_fixed(self, available_models):
        if self.fixed_model in available_models:
            return self.fixed_model, "fixed_model", {}
        return available_models[0], "fallback_first_available", {}

    def choose_global_mean(self, available_models):
        score_map = {}
        best_model = None
        best_score = -1.0
        for model in available_models:
            count = self.global_mean_count.get(model, 0)
            if count <= 0:
                continue
            score = self.global_mean_sum[model] / count
            score_map[model] = score
            if score > best_score:
                best_score = score
                best_model = model
        if best_model is not None:
            return best_model, "global_mean", score_map
        return self.choose_fixed(available_models)[0], "cold_start_fixed", score_map

    def choose_global_ema(self, available_models):
        score_map = {}
        best_model = None
        best_score = -1.0
        for model in available_models:
            if model not in self.global_ema:
                continue
            score = self.global_ema[model]
            score_map[model] = score
            if score > best_score:
                best_score = score
                best_model = model
        if best_model is not None:
            return best_model, "global_ema", score_map
        return self.choose_fixed(available_models)[0], "cold_start_fixed", score_map

    def choose_context_ema(self, available_models, used_example_ids):
        weighted_scores = defaultdict(float)
        weight_sums = defaultdict(float)
        example_breakdown = {}

        for example_id in used_example_ids or []:
            model_scores = self.example_model_scores.get(str(example_id), {})
            example_breakdown[str(example_id)] = {
                model: model_scores[model]
                for model in available_models
                if model in model_scores
            }
            for model in available_models:
                if model not in model_scores:
                    continue
                weighted_scores[model] += model_scores[model]
                weight_sums[model] += 1.0

        score_map = {}
        best_model = None
        best_score = -1.0
        for model in available_models:
            if weight_sums.get(model, 0.0) <= 0:
                continue
            score = weighted_scores[model] / weight_sums[model]
            score_map[model] = score
            if score > best_score:
                best_score = score
                best_model = model

        debug = {
            "score_map": score_map,
            "example_breakdown": example_breakdown,
        }
        if best_model is not None:
            return best_model, "context_ema", debug

        fallback_model, fallback_reason, fallback_scores = self.choose_global_ema(available_models)
        debug["fallback_global_ema"] = fallback_scores
        if fallback_model in available_models:
            return fallback_model, f"fallback_{fallback_reason}", debug
        return self.choose_fixed(available_models)[0], "cold_start_fixed", debug

    def update(self, used_example_ids, evaluated_candidates):
        for candidate in evaluated_candidates:
            model = candidate["model"]
            final_score = float(candidate["metrics"]["final_score"])
            single_score = float(candidate["metrics"]["single_score"])

            self.global_mean_sum[model] += final_score
            self.global_mean_count[model] += 1

            if model not in self.global_ema:
                self.global_ema[model] = final_score
            else:
                self.global_ema[model] = self.ema_alpha * final_score + (1.0 - self.ema_alpha) * self.global_ema[model]

            for example_id in used_example_ids or []:
                example_key = str(example_id)
                old_score = self.example_model_scores[example_key].get(model)
                if old_score is None:
                    self.example_model_scores[example_key][model] = single_score
                else:
                    self.example_model_scores[example_key][model] = (
                        self.ema_alpha * single_score + (1.0 - self.ema_alpha) * old_score
                    )

    def snapshot(self, available_models, used_example_ids):
        context_scores = {}
        for example_id in used_example_ids or []:
            model_scores = self.example_model_scores.get(str(example_id), {})
            context_scores[str(example_id)] = {
                model: safe_round(model_scores[model])
                for model in available_models
                if model in model_scores
            }

        return {
            "global_mean": {
                model: safe_round(self.global_mean_sum[model] / self.global_mean_count[model])
                for model in available_models
                if self.global_mean_count.get(model, 0) > 0
            },
            "global_ema": {
                model: safe_round(self.global_ema[model])
                for model in available_models
                if model in self.global_ema
            },
            "context_ema": context_scores,
        }


def select_oracle(evaluated_candidates):
    return max(evaluated_candidates, key=lambda item: item["metrics"]["final_score"])


def get_strategy_summaries(records):
    if not records:
        return {}
    hit_count = sum(1 for item in records if item["hit"])
    return {
        "samples": len(records),
        "hit_rate": safe_round(hit_count / len(records)),
        "avg_final_score": safe_round(statistics.mean(item["chosen_final_score"] for item in records)),
        "avg_single_score": safe_round(statistics.mean(item["chosen_single_score"] for item in records)),
        "avg_sim_score": safe_round(statistics.mean(item["chosen_sim_score"] for item in records)),
        "avg_compare_score": safe_round(statistics.mean(item["chosen_compare_score"] for item in records)),
        "avg_user_preference": safe_round(statistics.mean(item["chosen_user_preference"] for item in records)),
        "avg_regret": safe_round(statistics.mean(item["regret"] for item in records)),
    }


def summarize_by_phase(records):
    if not records:
        return {}
    total = len(records)
    phase_boundaries = {
        "cold_start": (0, max(1, int(total * 0.2))),
        "growth": (max(1, int(total * 0.2)), max(1, int(total * 0.5))),
        "stable": (max(1, int(total * 0.5)), total),
    }

    phase_summary = {}
    for phase_name, (start, end) in phase_boundaries.items():
        phase_records = records[start:end]
        phase_summary[phase_name] = get_strategy_summaries(phase_records)
    return phase_summary


def replay_from_sim_records(sim_records, args):
    state = ReplayState(fixed_model=args.fixed_model, ema_alpha=args.ema_alpha)
    detail_rows = []
    trace_rows = []

    for record in sim_records:
        used_example_ids = record.get("used_example_ids", []) or []
        available_models = [candidate["model"] for candidate in record["candidates"]]
        state_before = state.snapshot(available_models, used_example_ids)

        evaluated_candidates = evaluate_candidates_from_sim(record, args)
        evaluated_by_model = {item["model"]: item for item in evaluated_candidates}
        oracle = select_oracle(evaluated_candidates)
        oracle_model = oracle["model"]

        strategies = {
            "fixed_model": state.choose_fixed(available_models),
            "global_mean": state.choose_global_mean(available_models),
            "global_ema": state.choose_global_ema(available_models),
            "context_ema": state.choose_context_ema(available_models, used_example_ids),
        }

        strategy_trace = {}
        for strategy_name, (chosen_model, reason, debug) in strategies.items():
            chosen = evaluated_by_model[chosen_model]
            oracle_score = float(oracle["metrics"]["final_score"])
            chosen_score = float(chosen["metrics"]["final_score"])
            row = {
                "strategy": strategy_name,
                "index": record["index"],
                "id": record.get("id"),
                "chosen_model": chosen_model,
                "reason": reason,
                "oracle_model": oracle_model,
                "hit": chosen_model == oracle_model,
                "chosen_final_score": chosen_score,
                "chosen_single_score": float(chosen["metrics"]["single_score"]),
                "chosen_sim_score": float(chosen["metrics"]["sim_score"]),
                "chosen_compare_score": float(chosen["metrics"]["compare_score"]),
                "chosen_user_preference": float(chosen["metrics"]["user_preference"]),
                "oracle_final_score": oracle_score,
                "regret": oracle_score - chosen_score,
                "used_example_ids_count": len(used_example_ids),
                "used_example_ids": used_example_ids,
                "decision_debug": round_nested(debug),
            }
            state.strategy_records[strategy_name].append(row)
            detail_rows.append(row)

            strategy_trace[strategy_name] = {
                "chosen_model": chosen_model,
                "reason": reason,
                "decision_debug": row["decision_debug"],
                "chosen_metrics": {
                    "sim_score": safe_round(chosen["metrics"]["sim_score"]),
                    "single_score": safe_round(chosen["metrics"]["single_score"]),
                    "compare_score": safe_round(chosen["metrics"]["compare_score"]),
                    "final_score": safe_round(chosen["metrics"]["final_score"]),
                    "user_preference": safe_round(chosen["metrics"]["user_preference"]),
                },
                "hit": chosen_model == oracle_model,
                "regret": safe_round(oracle_score - chosen_score),
            }

        trace_rows.append({
            "index": record["index"],
            "id": record.get("id"),
            "used_example_ids": used_example_ids,
            "selected_by_similarity": record["selected_by_similarity"],
            "is_edited": bool(record["is_edited"]),
            "available_models": available_models,
            "state_before": state_before,
            "candidate_metrics": [
                {
                    "model": candidate["model"],
                    "sim_score": safe_round(candidate["metrics"]["sim_score"]),
                    "single_score": safe_round(candidate["metrics"]["single_score"]),
                    "compare_score": safe_round(candidate["metrics"]["compare_score"]),
                    "final_score": safe_round(candidate["metrics"]["final_score"]),
                    "user_preference": safe_round(candidate["metrics"]["user_preference"]),
                }
                for candidate in evaluated_candidates
            ],
            "oracle_model": oracle_model,
            "oracle_final_score": safe_round(oracle["metrics"]["final_score"]),
            "strategy_trace": strategy_trace,
        })

        state.update(used_example_ids, evaluated_candidates)

    return state, detail_rows, trace_rows


def build_summary(args, input_path: Path, valid_records, skipped, state):
    summary = {
        "input": str(input_path),
        "valid_samples": len(valid_records),
        "skipped_samples": len(skipped),
        "fixed_model": args.fixed_model,
        "semantic_model": args.semantic_model,
        "alpha": args.alpha,
        "beta": args.beta,
        "lambda_val": args.lambda_val,
        "w1": args.w1,
        "w2": args.w2,
        "s1": args.s1,
        "s2": args.s2,
        "ema_alpha": args.ema_alpha,
        "strategies": {},
        "phase_summary": {},
    }

    for strategy_name, records in state.strategy_records.items():
        summary["strategies"][strategy_name] = get_strategy_summaries(records)
        summary["phase_summary"][strategy_name] = summarize_by_phase(records)

    return summary


def save_summary_csv(path: Path, summary):
    csv_lines = [
        "strategy,samples,hit_rate,avg_final_score,avg_single_score,avg_sim_score,avg_compare_score,avg_user_preference,avg_regret"
    ]
    for strategy_name, metrics in summary["strategies"].items():
        csv_lines.append(",".join([
            strategy_name,
            str(metrics.get("samples", 0)),
            str(metrics.get("hit_rate", "")),
            str(metrics.get("avg_final_score", "")),
            str(metrics.get("avg_single_score", "")),
            str(metrics.get("avg_sim_score", "")),
            str(metrics.get("avg_compare_score", "")),
            str(metrics.get("avg_user_preference", "")),
            str(metrics.get("avg_regret", "")),
        ]))
    path.write_text("\n".join(csv_lines) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_records, skipped = load_valid_records(input_path, args.limit)

    encoder = build_encoder(args.semantic_model)
    sim_records = precompute_sim_scores(valid_records, encoder, args)
    sim_cache_path = output_dir / "candidate_sim_scores.jsonl"
    write_jsonl(sim_cache_path, sim_records)

    state, detail_rows, trace_rows = replay_from_sim_records(sim_records, args)
    summary = build_summary(args, input_path, valid_records, skipped, state)

    summary_path = output_dir / "strategy_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    details_path = output_dir / "strategy_details.jsonl"
    write_jsonl(details_path, detail_rows)

    trace_path = output_dir / "strategy_trace.jsonl"
    write_jsonl(trace_path, trace_rows)

    skipped_path = output_dir / "strategy_skipped.json"
    skipped_path.write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = output_dir / "strategy_summary.csv"
    save_summary_csv(csv_path, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved candidate sim cache to: {sim_cache_path}")
    print(f"Saved summary to: {summary_path}")
    print(f"Saved per-strategy details to: {details_path}")
    print(f"Saved per-step trace to: {trace_path}")
    print(f"Saved skipped records to: {skipped_path}")


if __name__ == "__main__":
    main()
