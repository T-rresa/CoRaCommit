import argparse
import concurrent.futures
import copy
import json
import statistics
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests
#系统测试脚本

SCRIPT_DIR = Path(__file__).resolve().parent
COMPARE_ROOT = SCRIPT_DIR.parent
DEFAULT_CONFIG_PATH = COMPARE_ROOT / "configs" / "system_test_config.example.json"


def load_config(path: Path):
    with open(path, "r", encoding="utf-8") as file:
        config = json.load(file)
    config.setdefault("benchmark", {})
    config["benchmark"].setdefault("sequential_samples", 20)
    config["benchmark"].setdefault("concurrent_samples", 30)
    config["benchmark"].setdefault("concurrency", 5)
    config["benchmark"].setdefault("feedback_under_load_requests", 10)
    config["benchmark"].setdefault("enable_real_concurrent_benchmark", True)
    config["benchmark"].setdefault("enable_mock_concurrent_benchmark", True)

    config_dir = path.resolve().parent
    for key in ["sample_file", "report_dir"]:
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


def first_non_empty_samples(sample_file: Path, limit: int):
    rows = []
    for row in read_jsonl(sample_file):
        if row.get("diff") and str(row["diff"]).strip():
            rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def percentile(values, p):
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lower = int(k)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (k - lower)


class SystemTester:
    def __init__(self, config):
        self.config = config
        self.node_api_base = config["node_api_base"].rstrip("/")
        self.sample_file = Path(config["sample_file"])
        self.report_dir = Path(config["report_dir"])
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.generation_request_template = config["generation_request"]

    def build_generation_payload(self, sample):
        payload = copy.deepcopy(self.generation_request_template)
        payload["diff"] = sample.get("diff", "")
        payload["userId"] = str(sample.get("_id", sample.get("id", "")))
        return payload

    def get_health(self, url):
        started = time.time()
        try:
            response = requests.get(url, timeout=15)
            elapsed = time.time() - started
            return {
                "url": url,
                "status_code": response.status_code,
                "ok": response.status_code == 200,
                "duration_seconds": round(elapsed, 6),
                "body": response.json() if "application/json" in response.headers.get("content-type", "") else response.text
            }
        except requests.RequestException as error:
            elapsed = time.time() - started
            return {
                "url": url,
                "status_code": None,
                "ok": False,
                "duration_seconds": round(elapsed, 6),
                "error": str(error),
            }

    def post_json(self, path, payload, timeout=120):
        url = f"{self.node_api_base}{path}"
        started = time.time()
        response = requests.post(url, json=payload, timeout=timeout)
        elapsed = time.time() - started
        return response, elapsed

    def safe_get_json(self, url, timeout=15):
        started = time.time()
        try:
            response = requests.get(url, timeout=timeout)
            elapsed = time.time() - started
            return {
                "status_code": response.status_code,
                "ok": response.status_code == 200,
                "duration_seconds": round(elapsed, 6),
                "body": response.json() if "application/json" in response.headers.get("content-type", "") else response.text
            }
        except requests.RequestException as error:
            elapsed = time.time() - started
            return {
                "status_code": None,
                "ok": False,
                "duration_seconds": round(elapsed, 6),
                "error": str(error),
            }

    def safe_post_json(self, path, payload, timeout=120):
        try:
            response, elapsed = self.post_json(path, payload, timeout=timeout)
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return {
                "status_code": response.status_code,
                "ok": response.status_code == 200,
                "duration_seconds": round(elapsed, 6),
                "body": body if isinstance(body, dict) else {},
            }
        except requests.RequestException as error:
            return {
                "status_code": None,
                "ok": False,
                "duration_seconds": None,
                "body": {},
                "error": str(error),
            }

    def run_basic_function_tests(self):
        sample = first_non_empty_samples(self.sample_file, 1)[0]
        report = {"sample_id": sample["_id"], "tests": {}}

        # Health checks
        report["tests"]["node_api_health"] = self.get_health(f"{self.node_api_base}/health")
        report["tests"]["retrieval_health"] = self.get_health(self.config["retrieval_backend_health"])
        report["tests"]["evaluation_health"] = self.get_health(self.config["evaluation_backend_health"])

        # Config endpoints
        for name, path in [
            ("models", "/config/models"),
            ("templates", "/config/templates"),
            ("languages", "/config/languages"),
        ]:
            report["tests"][f"config_{name}"] = self.safe_get_json(f"{self.node_api_base}{path}", timeout=15)

        # Similarity search
        search_result = self.safe_post_json("/similarity-search", {"diff": sample["diff"]}, timeout=60)
        search_body = search_result["body"]
        report["tests"]["similarity_search"] = {
            "status_code": search_result["status_code"],
            "ok": search_result["ok"],
            "duration_seconds": search_result["duration_seconds"],
            "matches_count": len(search_body.get("matches", [])) if isinstance(search_body, dict) else None,
            "recommended_model": search_body.get("recommended_model") if isinstance(search_body, dict) else None,
            "error": search_result.get("error"),
        }

        # Commit suggestion
        payload = self.build_generation_payload(sample)
        generation_result = self.safe_post_json("/commit-suggestion", payload, timeout=180)
        generation_body = generation_result["body"]
        report["tests"]["commit_suggestion"] = {
            "status_code": generation_result["status_code"],
            "ok": generation_result["ok"],
            "duration_seconds": generation_result["duration_seconds"],
            "suggestions_count": len(generation_body.get("suggestions", [])) if isinstance(generation_body, dict) else None,
            "used_example_ids_count": len(generation_body.get("used_example_ids", [])) if isinstance(generation_body, dict) else None,
            "error": generation_result.get("error"),
        }

        # Feedback submit
        candidates = generation_body.get("suggestions", []) if isinstance(generation_body, dict) else []
        feedback_payload = {
            "user_id": f"system-test-{uuid.uuid4()}",
            "models_requested": [model["name"] for model in payload.get("models", [])],
            "candidates": [
                {
                    "model": candidate.get("model"),
                    "generated_message": candidate.get("message", ""),
                    "message_quality": 0.0
                }
                for candidate in candidates
            ],
            "selected_model": candidates[0].get("model") if candidates else "",
            "final_message": sample.get("message", ""),
            "is_edited": True,
            "timestamp": datetime.now().isoformat(),
            "example_ids": generation_body.get("used_example_ids", []) if isinstance(generation_body, dict) else [],
            "diff": sample.get("diff", "")
        }
        feedback_result = self.safe_post_json("/feedback/commit", feedback_payload, timeout=30)
        feedback_body = feedback_result["body"]
        report["tests"]["feedback_submit"] = {
            "status_code": feedback_result["status_code"],
            "ok": feedback_result["ok"],
            "duration_seconds": feedback_result["duration_seconds"],
            "session_id": feedback_body.get("session_id") if isinstance(feedback_body, dict) else None,
            "error": feedback_result.get("error"),
        }
        return report

    def run_sequential_benchmark(self):
        sample_count = int(self.config["benchmark"]["sequential_samples"])
        samples = first_non_empty_samples(self.sample_file, sample_count)
        latencies = []
        success = 0
        failures = 0

        for sample in samples:
            payload = self.build_generation_payload(sample)
            try:
                response, elapsed = self.post_json("/commit-suggestion", payload, timeout=180)
                latencies.append(elapsed)
                if response.status_code == 200:
                    success += 1
                else:
                    failures += 1
            except Exception:
                failures += 1

        return {
            "samples": len(samples),
            "success": success,
            "failures": failures,
            "avg_latency_seconds": round(statistics.mean(latencies), 6) if latencies else None,
            "p95_latency_seconds": round(percentile(latencies, 0.95), 6) if latencies else None,
            "max_latency_seconds": round(max(latencies), 6) if latencies else None,
        }

    def run_concurrent_benchmark(self):
        sample_count = int(self.config["benchmark"]["concurrent_samples"])
        concurrency = int(self.config["benchmark"]["concurrency"])
        samples = first_non_empty_samples(self.sample_file, sample_count)
        latencies = []
        success = 0
        failures = 0
        lock = threading.Lock()

        def task(sample):
            nonlocal success, failures
            payload = self.build_generation_payload(sample)
            try:
                response, elapsed = self.post_json("/commit-suggestion", payload, timeout=180)
                with lock:
                    latencies.append(elapsed)
                    if response.status_code == 200:
                        success += 1
                    else:
                        failures += 1
            except Exception:
                with lock:
                    failures += 1

        started = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            executor.map(task, samples)
        total_elapsed = time.time() - started

        return {
            "samples": len(samples),
            "concurrency": concurrency,
            "success": success,
            "failures": failures,
            "total_duration_seconds": round(total_elapsed, 6),
            "avg_latency_seconds": round(statistics.mean(latencies), 6) if latencies else None,
            "p95_latency_seconds": round(percentile(latencies, 0.95), 6) if latencies else None,
            "max_latency_seconds": round(max(latencies), 6) if latencies else None,
        }

    def run_mock_concurrent_benchmark(self):
        sample_count = int(self.config["benchmark"]["concurrent_samples"])
        concurrency = int(self.config["benchmark"]["concurrency"])
        samples = first_non_empty_samples(self.sample_file, sample_count)
        latencies = []
        success = 0
        failures = 0
        lock = threading.Lock()

        def task(sample):
            nonlocal success, failures
            payload = self.build_generation_payload(sample)
            payload["mockLLM"] = True
            payload["mockLatencyMs"] = int(self.config["benchmark"].get("mock_llm_latency_ms", 0))
            try:
                response, elapsed = self.post_json("/commit-suggestion", payload, timeout=180)
                with lock:
                    latencies.append(elapsed)
                    if response.status_code == 200:
                        success += 1
                    else:
                        failures += 1
            except Exception:
                with lock:
                    failures += 1

        started = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            executor.map(task, samples)
        total_elapsed = time.time() - started

        return {
            "samples": len(samples),
            "concurrency": concurrency,
            "mock_llm": True,
            "mock_latency_ms": int(self.config["benchmark"].get("mock_llm_latency_ms", 0)),
            "success": success,
            "failures": failures,
            "total_duration_seconds": round(total_elapsed, 6),
            "avg_latency_seconds": round(statistics.mean(latencies), 6) if latencies else None,
            "p95_latency_seconds": round(percentile(latencies, 0.95), 6) if latencies else None,
            "max_latency_seconds": round(max(latencies), 6) if latencies else None,
        }

    def run_feedback_under_load_test(self):
        load_requests = int(self.config["benchmark"]["feedback_under_load_requests"])
        concurrency = int(self.config["benchmark"]["concurrency"])
        load_samples = first_non_empty_samples(self.sample_file, max(load_requests, concurrency))

        generation_latencies = []
        feedback_latencies = []
        feedback_statuses = []
        lock = threading.Lock()

        def generation_task(sample, idx):
            payload = self.build_generation_payload(sample)
            try:
                response, elapsed = self.post_json("/commit-suggestion", payload, timeout=180)
                with lock:
                    generation_latencies.append(elapsed)
                if response.status_code == 200:
                    body = response.json()
                    candidates = body.get("suggestions", [])
                    feedback_payload = {
                        "user_id": f"load-test-{idx}-{uuid.uuid4()}",
                        "models_requested": [model["name"] for model in payload.get("models", [])],
                        "candidates": [
                            {
                                "model": candidate.get("model"),
                                "generated_message": candidate.get("message", ""),
                                "message_quality": 0.0
                            }
                            for candidate in candidates
                        ],
                        "selected_model": candidates[0].get("model") if candidates else "",
                        "final_message": sample.get("message", ""),
                        "is_edited": True,
                        "timestamp": datetime.now().isoformat(),
                        "example_ids": body.get("used_example_ids", []),
                        "diff": sample.get("diff", "")
                    }
                    feedback_response, feedback_elapsed = self.post_json("/feedback/commit", feedback_payload, timeout=30)
                    with lock:
                        feedback_latencies.append(feedback_elapsed)
                        feedback_statuses.append(feedback_response.status_code)
            except Exception:
                pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            for idx, sample in enumerate(load_samples[:load_requests], start=1):
                executor.submit(generation_task, sample, idx)

        feedback_success = sum(1 for status in feedback_statuses if status == 200)
        feedback_failures = len(feedback_statuses) - feedback_success
        return {
            "load_requests": load_requests,
            "concurrency": concurrency,
            "avg_generation_latency_seconds": round(statistics.mean(generation_latencies), 6) if generation_latencies else None,
            "avg_feedback_latency_seconds": round(statistics.mean(feedback_latencies), 6) if feedback_latencies else None,
            "p95_feedback_latency_seconds": round(percentile(feedback_latencies, 0.95), 6) if feedback_latencies else None,
            "feedback_success": feedback_success,
            "feedback_failures": feedback_failures,
        }

    def run_all(self):
        benchmark_cfg = self.config["benchmark"]
        report = {
            "generated_at": datetime.now().isoformat(),
            "config": self.config,
            "basic_function_tests": self.run_basic_function_tests(),
            "sequential_benchmark": self.run_sequential_benchmark(),
            "concurrent_benchmark": (
                self.run_concurrent_benchmark()
                if benchmark_cfg.get("enable_real_concurrent_benchmark", True)
                else {"enabled": False, "skipped": True}
            ),
            "mock_concurrent_benchmark": (
                self.run_mock_concurrent_benchmark()
                if benchmark_cfg.get("enable_mock_concurrent_benchmark", True)
                else {"enabled": False, "skipped": True}
            ),
            "feedback_under_load_test": self.run_feedback_under_load_test(),
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.report_dir / f"system_test_report_{timestamp}.json"
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\nSaved report to: {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run system test suite for auto_gen_message.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to system test config JSON.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(Path(args.config))
    tester = SystemTester(config)
    tester.run_all()


if __name__ == "__main__":
    main()
