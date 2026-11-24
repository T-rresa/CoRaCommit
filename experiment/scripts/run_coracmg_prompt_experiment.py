# -*- coding: utf-8 -*-
"""Rerun the first N samples with CoRaCMG's prompt and one exemplar.

Settings:
  - Prompt: CoRaCMG scripts/prompt.py SIMILAR_PROMPT (single exemplar)
  - Retrieval: top-1 after self-exclusion from experiment/outputs/retrieval/top5_945.jsonl
  - No Conventional Commits constraint
  - Model: SiliconFlow deepseek-ai/DeepSeek-V3.2
  - temperature=0, max_tokens=1024

API key: put it in experiment/configs/.env.siliconflow (gitignored), e.g.
  SILICONFLOW_API_KEY=sk-...
or export SILICONFLOW_API_KEY in the environment.

Dry run (no API calls, writes prompts):
  python experiment/scripts/run_coracmg_prompt_experiment.py --dry-run --limit 500
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLES = REPO_ROOT / "experiment" / "inputs" / "sample_commit.jsonl"
DEFAULT_TOP5 = REPO_ROOT / "experiment" / "outputs" / "retrieval" / "top5_945.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "experiment" / "outputs" / "coracmg_prompt" / "cora_prompt_500.jsonl"
DEFAULT_ENV = REPO_ROOT / "experiment" / "configs" / ".env.siliconflow"

SIMILAR_PROMPT = """You are a developer, and your task is to write a concise commit message based on the code changes (in .diff format) in a commit. First, a similar commit example (including both code diff and commit message) is provided for reference. Then, you will be given a code diff which is your task, and you need to write a commit message for it.

## Input Format:

=== START OF SIMILAR COMMIT ===

--- START OF CODE DIFF ---
(Code changes in .diff format)
--- END OF CODE DIFF ---

--- START OF COMMIT MESSAGE ---
A commit message describing the code changes, wrapped in <message> </message> tags.
E.g. <message>Fixed a bug in the user authentication flow</message>
--- END OF COMMIT MESSAGE ---

=== END OF SIMILAR COMMIT ===

=== START OF YOUR TASK ===

--- START OF CODE DIFF ---
(Code changes in .diff format)
--- END OF CODE DIFF ---

=== END OF YOUR TASK ===

## Output Format:

A concise commit message describing the code changes, wrapped in <message> </message> tags.
E.g. <message>Fixed a bug in the user authentication flow</message>
E.g. <message>feat(server): Add new API endpoint for user registration</message>
"""


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_env_file(path):
    if not path or not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def build_messages(query_diff, exemplar):
    user = (
        "=== START OF SIMILAR COMMIT ===\n"
        "--- START OF CODE DIFF ---\n"
        f"{exemplar.get('diff', '')}\n"
        "--- END OF CODE DIFF ---\n"
        "--- START OF COMMIT MESSAGE ---\n"
        f"<message>{exemplar.get('message', '')}</message>\n"
        "--- END OF COMMIT MESSAGE ---\n"
        "=== END OF SIMILAR COMMIT ===\n\n"
        "\n\n=== START OF YOUR TASK ===\n"
        "--- START OF CODE DIFF ---\n"
        f"{query_diff}\n"
        "--- END OF CODE DIFF ---\n"
        "=== END OF YOUR TASK ==="
    )
    return [
        {"role": "system", "content": SIMILAR_PROMPT},
        {"role": "user", "content": user},
    ]


def extract_message(text):
    if not text:
        return ""
    m = re.search(r"<message>(.*?)</message>", text, re.S | re.I)
    if m:
        return m.group(1).strip()
    return text.strip()


class Runner:
    def __init__(self, args, tasks):
        self.args = args
        self.tasks = tasks
        self.lock = threading.Lock()
        self.ok = 0
        self.failed = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.api_key = os.environ.get("SILICONFLOW_API_KEY", "")
        self.base_url = args.base_url.rstrip("/")
        self.output = Path(args.output)
        self.output.parent.mkdir(parents=True, exist_ok=True)

    def call(self, task):
        payload = {
            "model": self.args.model,
            "messages": task["messages"],
            "temperature": self.args.temperature,
            "max_tokens": self.args.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.time()
        last_error = None
        for attempt in range(1, self.args.retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.args.timeout,
                )
                elapsed = time.time() - started
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                if resp.status_code != 200:
                    return {
                        "task_id": task["task_id"],
                        "id": task["id"],
                        "status": "error",
                        "http_status": resp.status_code,
                        "error": resp.text[:1000],
                        "elapsed": elapsed,
                    }
                body = resp.json()
                content = body["choices"][0]["message"]["content"]
                usage = body.get("usage") or {}
                with self.lock:
                    self.ok += 1
                    self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
                    self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)
                return {
                    "task_id": task["task_id"],
                    "id": task["id"],
                    "status": "success",
                    "model": self.args.model,
                    "response": content,
                    "pred": extract_message(content),
                    "label": task["label"],
                    "used_example_id": task["used_example_id"],
                    "messages": task["messages"],
                    "usage": usage,
                    "elapsed": elapsed,
                }
            except Exception as e:
                last_error = str(e)
                time.sleep(min(2 ** attempt, 30))
        with self.lock:
            self.failed += 1
        return {
            "task_id": task["task_id"],
            "id": task["id"],
            "status": "exception",
            "error": last_error,
            "elapsed": time.time() - started,
        }

    def run(self):
        with open(self.output, "w", encoding="utf-8") as out:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.args.concurrency) as pool:
                futures = [pool.submit(self.call, t) for t in self.tasks]
                for i, fut in enumerate(concurrent.futures.as_completed(futures), start=1):
                    record = fut.result()
                    with self.lock:
                        out.write(json.dumps(record, ensure_ascii=False) + "\n")
                        out.flush()
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
            "estimated_cost_cny": (
                self.prompt_tokens * 2.0 / 1_000_000
                + self.completion_tokens * 3.0 / 1_000_000
            ),
            "finished_at": datetime.now().isoformat(),
        }
        with open(self.output.with_suffix(".summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES))
    parser.add_argument("--top5", default=str(DEFAULT_TOP5))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--model", default="deepseek-ai/DeepSeek-V3.2")
    parser.add_argument("--base-url", default="https://api.siliconflow.cn/v1")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env_file(args.env_file)
    samples = list(read_jsonl(args.samples))
    if args.offset:
        samples = samples[args.offset:]
    if args.limit:
        samples = samples[:args.limit]
    top5 = {str(r["id"]): r for r in read_jsonl(args.top5)}

    tasks = []
    for s in samples:
        sid = str(s.get("_id"))
        ex = (top5.get(sid, {}).get("top5") or [])
        exemplar = ex[0] if ex else {"diff": "", "message": ""}
        task_id = f"{s.get('owner', '')}_{s.get('repo', '')}_{str(s.get('commit_sha', ''))[:7]}"
        tasks.append({
            "task_id": task_id,
            "id": s.get("_id"),
            "label": s.get("message", ""),
            "messages": build_messages(s.get("diff", ""), exemplar),
            "used_example_id": exemplar.get("commit_id"),
        })

    print(f"built {len(tasks)} tasks", flush=True)
    if args.dry_run:
        out = Path(args.output).with_name(Path(args.output).stem + "_tasks.jsonl")
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for t in tasks:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        print("dry run: wrote", out, flush=True)
        return

    if not os.environ.get("SILICONFLOW_API_KEY"):
        raise SystemExit(
            "SILICONFLOW_API_KEY is not set. Put it in "
            f"{args.env_file} or export it in the environment."
        )
    Runner(args, tasks).run()


if __name__ == "__main__":
    main()