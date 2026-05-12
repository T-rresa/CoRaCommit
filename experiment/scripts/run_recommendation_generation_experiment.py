import argparse
import concurrent.futures
import copy
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

#Model scoring update strategy - 
#script for model to generate and commit messages

SCRIPT_DIR = Path(__file__).resolve().parent
COMPARE_ROOT = SCRIPT_DIR.parent
DEFAULT_CONFIG_PATH = COMPARE_ROOT / "configs" / "recommendation_experiment_config.example.json"


def load_config(config_path: Path):
    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    required_keys = ["node_service_url", "input_file", "output_file", "request"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")

    request_config = config["request"]
    if not request_config.get("models"):
        raise ValueError("Config request.models must contain at least one model")

    config.setdefault("concurrency", 3)

    config_dir = config_path.resolve().parent
    for key in ["input_file", "output_file"]:
        value = Path(config[key])
        if not value.is_absolute():
            config[key] = str((config_dir / value).resolve())
    return config


def read_jsonl(path: Path):
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


class ExperimentRunner:
    def __init__(self, config, limit=0):
        self.config = config
        self.limit = limit
        self.node_service_url = config["node_service_url"]
        self.concurrency = int(config.get("concurrency", 3))
        self.request_template = config["request"]
        self.output_path = Path(config["output_file"])
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        self.file_lock = threading.Lock()
        self.counter_lock = threading.Lock()
        self.processed = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0

    def build_payload(self, sample):
        payload = copy.deepcopy(self.request_template)
        payload["diff"] = sample.get("diff", "")
        payload["userId"] = str(sample.get("_id"))
        return payload

    def process_sample(self, sample, line_num, outfile):
        diff = sample.get("diff", "")
        sample_id = sample.get("_id")
        ground_truth = sample.get("message", "")

        if not diff or not str(diff).strip():
            result = {
                "id": sample_id,
                "status": "skipped",
                "reason": "empty_diff",
                "ground_truth": ground_truth
            }
            with self.counter_lock:
                self.skipped += 1
            with self.file_lock:
                outfile.write(json.dumps(result, ensure_ascii=False) + "\n")
                outfile.flush()
            return

        payload = self.build_payload(sample)
        started_at = time.time()

        try:
            response = requests.post(self.node_service_url, json=payload, timeout=180)
            elapsed = time.time() - started_at

            if response.status_code == 200:
                response_json = response.json()
                record = {
                    "id": sample_id,
                    "status": "success",
                    "timestamp": datetime.now().isoformat(),
                    "models_requested": [model["name"] for model in payload.get("models", [])],
                    "candidates": response_json.get("suggestions", []),
                    "used_example_ids": response_json.get("used_example_ids", []),
                    "ground_truth": ground_truth,
                    "diff": diff,
                    "_experiment_meta": {
                        "line_num": line_num,
                        "duration_seconds": elapsed,
                        "status_code": response.status_code
                    }
                }
                with self.counter_lock:
                    self.success += 1
                print(f"[{line_num}] success | id={sample_id} | {elapsed:.2f}s")
            else:
                record = {
                    "id": sample_id,
                    "status": "error",
                    "timestamp": datetime.now().isoformat(),
                    "ground_truth": ground_truth,
                    "diff": diff,
                    "error_code": response.status_code,
                    "error_text": response.text,
                    "_experiment_meta": {
                        "line_num": line_num,
                        "duration_seconds": elapsed,
                        "status_code": response.status_code
                    }
                }
                with self.counter_lock:
                    self.failed += 1
                print(f"[{line_num}] failed | id={sample_id} | status={response.status_code} | {elapsed:.2f}s")
        except Exception as error:
            elapsed = time.time() - started_at
            record = {
                "id": sample_id,
                "status": "exception",
                "timestamp": datetime.now().isoformat(),
                "ground_truth": ground_truth,
                "diff": diff,
                "error_text": str(error),
                "_experiment_meta": {
                    "line_num": line_num,
                    "duration_seconds": elapsed
                }
            }
            with self.counter_lock:
                self.failed += 1
            print(f"[{line_num}] exception | id={sample_id} | error={error}")

        with self.file_lock:
            outfile.write(json.dumps(record, ensure_ascii=False) + "\n")
            outfile.flush()
        with self.counter_lock:
            self.processed += 1

    def run(self):
        input_path = Path(self.config["input_file"])
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        samples = list(read_jsonl(input_path))
        if self.limit > 0:
            samples = samples[: self.limit]

        print(f"Loaded {len(samples)} samples from {input_path}")
        print(f"Using models: {[model['name'] for model in self.request_template.get('models', [])]}")
        print(f"Output file: {self.output_path}")
        print(f"Target URL: {self.node_service_url}")
        print(f"Concurrency: {self.concurrency}")

        with open(self.output_path, "w", encoding="utf-8") as outfile:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                futures = []
                for index, sample in enumerate(samples, start=1):
                    futures.append(executor.submit(self.process_sample, sample, index, outfile))
                concurrent.futures.wait(futures)

        summary = {
            "input_file": str(input_path),
            "output_file": str(self.output_path),
            "models_requested": [model["name"] for model in self.request_template.get("models", [])],
            "processed": self.processed,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "limit": self.limit,
            "concurrency": self.concurrency,
            "finished_at": datetime.now().isoformat()
        }

        summary_path = self.output_path.with_suffix(".summary.json")
        with open(summary_path, "w", encoding="utf-8") as file:
            json.dump(summary, file, ensure_ascii=False, indent=2)

        print("\nExperiment finished.")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"Summary saved to: {summary_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate raw multi-model outputs for model recommendation experiments."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to experiment config json."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional number of samples to run. Use 0 for all samples."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    runner = ExperimentRunner(config=config, limit=args.limit)
    runner.run()


if __name__ == "__main__":
    main()
