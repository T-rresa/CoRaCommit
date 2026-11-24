# -*- coding: utf-8 -*-
"""Run P2-tool generation: tool default prompt + P2 top-5 exemplars.

Replicates node_service PromptBuilder:
  - system: GPTPrompt system
  - format: Conventional Commits rules
  - style: Angular style ("concise subject and optional body")
  - examples: per-example diff truncated to 2000 chars, total 6000 chars
  - output: "Output only the final commit message. No explanations."

Model: SiliconFlow deepseek-ai/DeepSeek-V3.2, temperature=0, max_tokens=1024.

Run:
  python experiment/scripts/run_p2_tool_generation.py
"""

import argparse
import concurrent.futures
import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEST = REPO_ROOT / "experiment" / "outputs" / "leakage" / "leakage_test_495.jsonl"
DEFAULT_TOP5 = REPO_ROOT / "experiment" / "outputs" / "leakage" / "top5_p2_strict_495.jsonl"
DEFAULT_OUT = REPO_ROOT / "experiment" / "outputs" / "leakage" / "p2_tool_495.jsonl"
DEFAULT_ENV = REPO_ROOT / "experiment" / "configs" / ".env.siliconflow"

SYSTEM = "You are an expert software engineer generating Git commit messages."
FORMAT = """Use Conventional Commits format:
type(scope): subject
Examples of types: feat, fix, docs, refactor, test, chore"""
STYLE = "Use Angular commit style with concise subject and optional body."
OUTPUT = "Output only the final commit message. No explanations."
MAX_EXAMPLES_DIFF_CHARS = 6000
MAX_SINGLE_EXAMPLE_DIFF_CHARS = 2000


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_env(path):
    if not path or not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def build_prompt(diff, examples, no_exemplar_cap=False):
    examples_text = ""
    max_total = float("inf") if no_exemplar_cap else MAX_EXAMPLES_DIFF_CHARS
    max_single = float("inf") if no_exemplar_cap else MAX_SINGLE_EXAMPLE_DIFF_CHARS
    remaining = max_total
    included = []
    for i, ex in enumerate(examples):
        if remaining <= 0:
            break
        raw_diff = str(ex.get("diff", "") or "")
        limit = min(max_single, remaining)
        if len(raw_diff) > limit:
            trimmed = raw_diff[:limit] + "\n\n[...EXAMPLE DIFF TRUNCATED...]"
        else:
            trimmed = raw_diff
        remaining = max(0, remaining - len(trimmed))
        examples_text += (
            f"\nExample {i + 1}:\nDiff:\n{trimmed}\n\n"
            f"Commit message:\n{ex.get('message', '')}\n"
        )
        included.append(str(ex.get("commit_id")))
    text = (
        f"\n{SYSTEM}\n\n{FORMAT}\n\n{STYLE}\n\n"
        f"Here are relevant examples:\n{examples_text}\n"
        f"Now generate a commit message for the following diff:\n\n{diff}\n\n{OUTPUT}\n"
    )
    return text, included


def clean_output(text):
    if not text:
        return ""
    text = text.strip()
    m = re.search(r"<message>(.*?)</message>", text, re.S | re.I)
    if m:
        text = m.group(1).strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


class Runner:
    def __init__(self, args, tasks):
        self.args = args
        self.tasks = tasks
        self.lock = threading.Lock()
        self.ok = self.failed = 0
        self.prompt_tokens = self.completion_tokens = 0
        self.key = os.environ.get("SILICONFLOW_API_KEY", "")
        self.base = args.base_url.rstrip("/")
        self.out = Path(args.output)
        self.out.parent.mkdir(parents=True, exist_ok=True)

    def call(self, task):
        payload = {
            "model": self.args.model,
            "messages": task["messages"],
            "temperature": self.args.temperature,
            "max_tokens": self.args.max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        started = time.time()
        last = None
        for attempt in range(1, self.args.retries + 1):
            try:
                r = requests.post(f"{self.base}/chat/completions", json=payload, headers=headers, timeout=self.args.timeout)
                elapsed = time.time() - started
                if r.status_code == 429 or 500 <= r.status_code < 600:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
                if r.status_code != 200:
                    return {"id": task["id"], "status": "error", "http_status": r.status_code, "error": r.text[:1000], "elapsed": elapsed}
                body = r.json()
                content = body["choices"][0]["message"]["content"]
                usage = body.get("usage") or {}
                with self.lock:
                    self.ok += 1
                    self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
                    self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)
                return {
                    "id": task["id"],
                    "status": "success",
                    "model": self.args.model,
                    "response": content,
                    "pred": clean_output(content),
                    "label": task["label"],
                    "used_example_ids": task["used_example_ids"],
                    "included_example_ids": task["included_example_ids"],
                    "usage": usage,
                    "elapsed": elapsed,
                }
            except Exception as e:
                last = str(e)
                time.sleep(min(2 ** attempt, 30))
        with self.lock:
            self.failed += 1
        return {"id": task["id"], "status": "exception", "error": last, "elapsed": time.time() - started}

    def run(self):
        with open(self.out, "w", encoding="utf-8") as f:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.args.concurrency) as pool:
                futures = [pool.submit(self.call, t) for t in self.tasks]
                for i, fut in enumerate(concurrent.futures.as_completed(futures), start=1):
                    rec = fut.result()
                    with self.lock:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        f.flush()
                    if i % 25 == 0 or i == len(self.tasks):
                        print(f"[{i}/{len(self.tasks)}] ok={self.ok} failed={self.failed}", flush=True)
        summary = {
            "tasks": len(self.tasks),
            "success": self.ok,
            "failed": self.failed,
            "model": self.args.model,
            "temperature": self.args.temperature,
            "max_tokens": self.args.max_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "estimated_cost_cny": self.prompt_tokens * 2.0 / 1e6 + self.completion_tokens * 3.0 / 1e6,
            "finished_at": datetime.now().isoformat(),
        }
        with open(self.out.with_suffix(".summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", default=str(DEFAULT_TEST))
    parser.add_argument("--top5", default=str(DEFAULT_TOP5))
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    parser.add_argument("--model", default="deepseek-ai/DeepSeek-V3.2")
    parser.add_argument("--base-url", default="https://api.siliconflow.cn/v1")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-exemplar-cap", action="store_true",
                        help="disable the 6000/2000 char exemplar diff cap")
    args = parser.parse_args()

    load_env(args.env_file)
    test = {str(r["id"]): r for r in read_jsonl(args.test)}
    tasks = []
    for r in read_jsonl(args.top5):
        sid = str(r["id"])
        q = test[sid]
        examples = r.get("top5", [])
        text, included = build_prompt(q.get("diff", ""), examples, args.no_exemplar_cap)
        tasks.append({
            "id": q["id"],
            "label": q.get("message", ""),
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": text},
            ],
            "used_example_ids": [x.get("commit_id") for x in examples],
            "included_example_ids": included,
        })
    print("tasks", len(tasks), "unique included counts", len({len(t["included_example_ids"]) for t in tasks}), flush=True)

    if args.dry_run:
        out = Path(args.output).with_name(Path(args.output).stem + "_tasks.jsonl")
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for t in tasks:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        print("dry run wrote", out, flush=True)
        return

    if not os.environ.get("SILICONFLOW_API_KEY"):
        raise SystemExit(f"SILICONFLOW_API_KEY not set in {args.env_file}")
    Runner(args, tasks).run()


if __name__ == "__main__":
    main()