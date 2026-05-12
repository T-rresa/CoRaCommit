import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
#Script to summarize scored results from plugin comparison experiments

SCRIPT_DIR = Path(__file__).resolve().parent
COMPARE_ROOT = SCRIPT_DIR.parent


def read_jsonl(path: Path):
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def safe_round(value, digits=6):
    if value is None:
        return None
    return round(float(value), digits)


def summarize_rows(rows):
    metric_values = defaultdict(lambda: defaultdict(list))
    win_counts = defaultdict(lambda: defaultdict(int))
    total_rows = 0

    for row in rows:
        plugin_results = row.get("plugin_results", [])
        if not plugin_results:
            continue

        total_rows += 1
        metric_to_plugin_scores = defaultdict(list)

        for plugin_result in plugin_results:
            plugin_name = plugin_result.get("plugin_name")
            for score_item in plugin_result.get("scores", []):
                metric_name = score_item.get("metrics")
                score_value = score_item.get("score")
                if plugin_name is None or metric_name is None or score_value is None:
                    continue
                score_value = float(score_value)
                metric_values[plugin_name][metric_name].append(score_value)
                metric_to_plugin_scores[metric_name].append((plugin_name, score_value))

        for metric_name, pairs in metric_to_plugin_scores.items():
            if not pairs:
                continue
            best_score = max(score for _, score in pairs)
            for plugin_name, score in pairs:
                if score == best_score:
                    win_counts[plugin_name][metric_name] += 1

    plugin_names = sorted(metric_values.keys())
    metric_names = sorted({metric for plugin in plugin_names for metric in metric_values[plugin].keys()})

    summary = {
        "samples": total_rows,
        "plugins": {},
        "metric_names": metric_names,
    }

    for plugin_name in plugin_names:
        plugin_summary = {
            "metrics": {},
            "wins": {},
        }
        for metric_name in metric_names:
            values = metric_values[plugin_name].get(metric_name, [])
            avg_value = safe_round(statistics.mean(values)) if values else None
            plugin_summary["metrics"][metric_name] = {
                "avg": avg_value,
                "count": len(values),
            }
            wins = win_counts[plugin_name].get(metric_name, 0)
            plugin_summary["wins"][metric_name] = {
                "count": wins,
                "rate": safe_round(wins / total_rows) if total_rows else None,
            }
        summary["plugins"][plugin_name] = plugin_summary

    return summary


def write_csv(path: Path, summary: dict):
    metric_names = summary["metric_names"]
    header = ["plugin"]
    for metric_name in metric_names:
        header.append(f"avg_{metric_name}")
        header.append(f"win_count_{metric_name}")
        header.append(f"win_rate_{metric_name}")

    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        for plugin_name, plugin_summary in summary["plugins"].items():
            row = [plugin_name]
            for metric_name in metric_names:
                row.append(plugin_summary["metrics"][metric_name]["avg"])
                row.append(plugin_summary["wins"][metric_name]["count"])
                row.append(plugin_summary["wins"][metric_name]["rate"])
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Summarize scored plugin comparison results.")
    parser.add_argument(
        "--input",
        default=str(COMPARE_ROOT / "outputs" / "plugin_comparison" / "merged_aligned_945_scored.jsonl"),
        help="Path to scored comparison jsonl.",
    )
    parser.add_argument(
        "--output-json",
        default=str(COMPARE_ROOT / "outputs" / "plugin_comparison" / "merged_aligned_945_summary.json"),
        help="Path to summary json output.",
    )
    parser.add_argument(
        "--output-csv",
        default=str(COMPARE_ROOT / "outputs" / "plugin_comparison" / "merged_aligned_945_summary.csv"),
        help="Path to summary csv output.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_json = Path(args.output_json)
    output_csv = Path(args.output_csv)

    rows = list(read_jsonl(input_path))
    summary = summarize_rows(rows)

    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(output_csv, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved summary json to: {output_json}")
    print(f"Saved summary csv to: {output_csv}")


if __name__ == "__main__":
    main()
