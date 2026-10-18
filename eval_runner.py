#!/usr/bin/env python3
"""Lightweight zero-dependency evaluation runner for local Ollama models."""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


OLLAMA_API_URL = "http://localhost:11434/api/chat"


def query_ollama(model: str, prompt: str, temperature: float = 0.0) -> Dict[str, Any]:
    """Send a chat completion request to the local Ollama server."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": temperature,
            "seed": 42,
        },
    }
    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - start

    eval_count = data.get("eval_count", 0)
    eval_duration_ns = data.get("eval_duration", 0)
    tok_per_sec = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns else 0.0

    return {
        "response": data.get("message", {}).get("content", "").strip(),
        "latency_s": round(elapsed, 3),
        "tokens": eval_count,
        "tok_per_sec": round(tok_per_sec, 1),
    }


def score_response(actual: str, expected: str, match_type: str) -> bool:
    """Grade the model response against expected output."""
    cleaned = actual.strip().strip("`").strip()
    if match_type == "exact":
        return cleaned.rstrip(".").lower() == expected.strip().lower()
    if match_type == "contains":
        return expected.lower() in cleaned.lower()
    if match_type == "json":
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        try:
            return json.loads(cleaned) == json.loads(expected)
        except json.JSONDecodeError:
            return False
    return False


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    cases = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local LLM evals against Ollama.")
    parser.add_argument(
        "--model",
        default="gemma2:2b-instruct-q4_K_M",
        help="Ollama model tag to evaluate (default: gemma2:2b-instruct-q4_K_M)",
    )
    parser.add_argument(
        "--dataset",
        default="eval_dataset.jsonl",
        help="Path to JSONL evaluation dataset",
    )
    parser.add_argument(
        "--output",
        default="eval_results.json",
        help="Path to save detailed JSON results",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: dataset file not found at {dataset_path}", file=sys.stderr)
        return 1

    cases = load_dataset(dataset_path)
    print(f"Running {len(cases)} eval cases on model '{args.model}'...\n")
    print(f"{'ID':<12} {'CATEGORY':<18} {'STATUS':<8} {'LATENCY':<10} {'TOK/S':<8} {'OUTPUT'}")
    print("-" * 80)

    results = []
    passed_count = 0

    for case in cases:
        try:
            res = query_ollama(args.model, case["prompt"])
        except urllib.error.URLError as exc:
            print(f"\nError connecting to Ollama at {OLLAMA_API_URL}: {exc}", file=sys.stderr)
            print("Make sure 'ollama serve' is running and the model is pulled.", file=sys.stderr)
            return 1

        passed = score_response(res["response"], case["expected"], case["match_type"])
        if passed:
            passed_count += 1

        status_str = "PASS" if passed else "FAIL"
        preview = res["response"].replace("\n", " ")[:35]
        print(
            f"{case['id']:<12} {case['category']:<18} {status_str:<8} "
            f"{res['latency_s']:<10.2f} {res['tok_per_sec']:<8.1f} {preview}"
        )

        results.append({
            **case,
            "actual": res["response"],
            "passed": passed,
            "latency_s": res["latency_s"],
            "tok_per_sec": res["tok_per_sec"],
        })

    accuracy = (passed_count / len(cases)) * 100 if cases else 0.0
    avg_tok_s = sum(r["tok_per_sec"] for r in results) / len(results) if results else 0.0

    print("-" * 80)
    print(f"Summary: {passed_count}/{len(cases)} passed ({accuracy:.1f}%) | Avg speed: {avg_tok_s:.1f} tok/s")

    output_path = Path(args.output)
    output_path.write_text(json.dumps({
        "model": args.model,
        "total": len(cases),
        "passed": passed_count,
        "accuracy_pct": round(accuracy, 2),
        "avg_tok_per_sec": round(avg_tok_s, 1),
        "results": results,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Saved detailed results to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
