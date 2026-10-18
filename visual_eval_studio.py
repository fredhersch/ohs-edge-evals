#!/usr/bin/env python3
"""CHW Edge LLM Visual Evaluation Runner, Visualizer & RLHF Studio.

Zero-dependency local web dashboard for evaluating edge Small Language Models (SLMs),
inspecting Tier-1 deterministic and Tier-2 LLM-as-a-judge clinical safety rubrics,
comparing models side-by-side, and curating DPO/RLHF preference datasets for fine-tuning.

Usage:
  python3 visual_eval_studio.py [--port 8501] [--host 127.0.0.1]
"""

import argparse
import datetime
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_DIR = Path(__file__).resolve().parent
EVAL_CASES_FILE = WORKSPACE_DIR / "chw-edge-evals" / "dataset" / "eval_cases.json"
DPO_FILE = WORKSPACE_DIR / "chw-edge-evals" / "dataset" / "dpo_preference_data.jsonl"
SFT_FILE = WORKSPACE_DIR / "chw-edge-evals" / "dataset" / "sft_clinical_data.jsonl"
RUN_EVALS_SCRIPT = WORKSPACE_DIR / "chw-edge-evals" / "run_evals.py"

# Global state for background eval runner process
RUNNER_LOCK = threading.Lock()
ACTIVE_RUN = {
    "is_running": False,
    "started_at": None,
    "completed_at": None,
    "process": None,
    "logs": [],
    "model": None,
    "status": "idle",
    "exit_code": None,
    "output_file": None,
}


def load_eval_cases() -> List[Dict[str, Any]]:
    if EVAL_CASES_FILE.exists():
        try:
            return json.loads(EVAL_CASES_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error loading eval cases: {e}", file=sys.stderr)
    return []


def list_eval_run_files() -> List[Dict[str, Any]]:
    runs = []
    for p in WORKSPACE_DIR.glob("eval_results_*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            runs.append({
                "filename": p.name,
                "path": str(p),
                "model": data.get("model", "unknown"),
                "timestamp": data.get("timestamp", ""),
                "passes": data.get("passes", 0),
                "total_checks": data.get("total_checks", 0),
                "pass_rate_pct": data.get("pass_rate_pct", 0),
                "cases_count": len(data.get("results", [])),
                "judge_model": data.get("judge_config", {}).get("model") if isinstance(data.get("judge_config"), dict) else data.get("judge_model"),
            })
        except Exception:
            continue
    runs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return runs


def load_run_details(filename: str) -> Optional[Dict[str, Any]]:
    safe_name = Path(filename).name
    p = WORKSPACE_DIR / safe_name
    if p.exists() and p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def load_preferences() -> List[Dict[str, Any]]:
    prefs = []
    if DPO_FILE.exists():
        try:
            for line in DPO_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    prefs.append(json.loads(line))
        except Exception as e:
            print(f"Error loading preferences: {e}", file=sys.stderr)
    return prefs


def save_preference_record(record: Dict[str, Any]) -> bool:
    DPO_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(DPO_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return True
    except Exception as e:
        print(f"Error appending preference: {e}", file=sys.stderr)
        return False


def save_sft_record(record: Dict[str, Any]) -> bool:
    SFT_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(SFT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return True
    except Exception as e:
        print(f"Error appending SFT record: {e}", file=sys.stderr)
        return False


def run_eval_worker(cmd: List[str], output_file: str, model_name: str):
    global ACTIVE_RUN
    with RUNNER_LOCK:
        ACTIVE_RUN["is_running"] = True
        ACTIVE_RUN["status"] = "running"
        ACTIVE_RUN["started_at"] = datetime.datetime.now().isoformat()
        ACTIVE_RUN["completed_at"] = None
        ACTIVE_RUN["logs"] = [f"$ {' '.join(cmd)}\n"]
        ACTIVE_RUN["model"] = model_name
        ACTIVE_RUN["output_file"] = output_file
        ACTIVE_RUN["exit_code"] = None

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(WORKSPACE_DIR),
        )
        ACTIVE_RUN["process"] = proc

        for line in iter(proc.stdout.readline, ""):
            with RUNNER_LOCK:
                ACTIVE_RUN["logs"].append(line)
                if len(ACTIVE_RUN["logs"]) > 2000:
                    ACTIVE_RUN["logs"].pop(0)

        proc.stdout.close()
        code = proc.wait()
        with RUNNER_LOCK:
            ACTIVE_RUN["exit_code"] = code
            ACTIVE_RUN["is_running"] = False
            ACTIVE_RUN["status"] = "completed" if code == 0 else "failed"
            ACTIVE_RUN["completed_at"] = datetime.datetime.now().isoformat()
            ACTIVE_RUN["logs"].append(f"\n[Process exited with code {code}]\n")
    except Exception as exc:
        with RUNNER_LOCK:
            ACTIVE_RUN["exit_code"] = -1
            ACTIVE_RUN["is_running"] = False
            ACTIVE_RUN["status"] = f"error: {str(exc)}"
            ACTIVE_RUN["completed_at"] = datetime.datetime.now().isoformat()
            ACTIVE_RUN["logs"].append(f"\n[Execution error: {str(exc)}]\n")


class StudioApiHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/runs":
            self.send_json_response(list_eval_run_files())
        elif path.startswith("/api/runs/"):
            filename = path.replace("/api/runs/", "")
            data = load_run_details(filename)
            if data:
                self.send_json_response(data)
            else:
                self.send_error_response(404, "Run file not found")
        elif path == "/api/cases":
            self.send_json_response(load_eval_cases())
        elif path == "/api/preferences":
            self.send_json_response(load_preferences())
        elif path == "/api/runner/status":
            with RUNNER_LOCK:
                resp = {
                    "is_running": ACTIVE_RUN["is_running"],
                    "status": ACTIVE_RUN["status"],
                    "started_at": ACTIVE_RUN["started_at"],
                    "completed_at": ACTIVE_RUN["completed_at"],
                    "model": ACTIVE_RUN["model"],
                    "exit_code": ACTIVE_RUN["exit_code"],
                    "output_file": ACTIVE_RUN["output_file"],
                    "logs": "".join(ACTIVE_RUN["logs"][-200:]),
                }
            self.send_json_response(resp)
        elif path == "/" or path == "/index.html":
            self.serve_studio_html()
        else:
            self.send_error_response(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        if path == "/api/runner/start":
            self.handle_start_runner(body)
        elif path == "/api/preferences/save":
            self.handle_save_preference(body)
        elif path == "/api/preferences/auto-bootstrap":
            self.handle_auto_bootstrap_dpo(body)
        elif path == "/api/sft/save":
            self.handle_save_sft(body)
        else:
            self.send_error_response(404, "Endpoint not found")

    def send_json_response(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_error_response(self, status: int, message: str):
        self.send_json_response({"error": message}, status=status)

    def handle_start_runner(self, body: Dict[str, Any]):
        global ACTIVE_RUN
        with RUNNER_LOCK:
            if ACTIVE_RUN["is_running"]:
                self.send_error_response(400, "An evaluation is already actively running")
                return

        model = body.get("model", "gemma2:2b-instruct-q4_K_M")
        api_base = body.get("api_base", "http://localhost:11434")
        judge_model = body.get("judge_model", "")
        judge_provider = body.get("judge_provider", "auto")
        judge_api_key = body.get("judge_api_key", "")
        dry_run = body.get("dry_run", False)

        model_slug = (model or "dryrun").replace(":", "_").replace("/", "_")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"eval_results_{model_slug}_{timestamp}.json"

        cmd = [sys.executable, str(RUN_EVALS_SCRIPT), "--model", model, "--api-base", api_base, "--output", output_file]
        if dry_run:
            cmd.append("--dry-run")
        if judge_model:
            cmd.extend(["--judge-model", judge_model])
            if judge_provider:
                cmd.extend(["--judge-provider", judge_provider])
            if judge_api_key:
                cmd.extend(["--judge-api-key", judge_api_key])

        thread = threading.Thread(target=run_eval_worker, args=(cmd, output_file, model), daemon=True)
        thread.start()

        self.send_json_response({
            "message": "Evaluation started successfully",
            "output_file": output_file,
            "model": model,
            "cmd": cmd,
        })

    def handle_save_preference(self, body: Dict[str, Any]):
        if not body.get("prompt") or not body.get("chosen") or not body.get("rejected"):
            self.send_error_response(400, "Missing required fields (prompt, chosen, rejected)")
            return

        record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "case_id": body.get("case_id", "unknown"),
            "task": body.get("task", "general"),
            "model_chosen": body.get("model_chosen", ""),
            "model_rejected": body.get("model_rejected", ""),
            "prompt": body.get("prompt"),
            "chosen": body.get("chosen"),
            "rejected": body.get("rejected"),
            "critique_tags": body.get("critique_tags", []),
            "rationale": body.get("rationale", ""),
        }
        if save_preference_record(record):
            self.send_json_response({"message": "Preference saved successfully", "count": len(load_preferences())})
        else:
            self.send_error_response(500, "Failed to write preference record")

    def handle_save_sft(self, body: Dict[str, Any]):
        if not body.get("instruction") or not body.get("output"):
            self.send_error_response(400, "Missing instruction or output")
            return
        record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "case_id": body.get("case_id", ""),
            "task": body.get("task", "general"),
            "instruction": body.get("instruction"),
            "input": body.get("input", ""),
            "output": body.get("output"),
        }
        if save_sft_record(record):
            self.send_json_response({"message": "Gold SFT demonstration saved successfully"})
        else:
            self.send_error_response(500, "Failed to write SFT record")

    def handle_auto_bootstrap_dpo(self, body: Dict[str, Any]):
        high_run = body.get("high_model_run")
        low_run = body.get("low_model_run")
        if not high_run or not low_run:
            self.send_error_response(400, "Must specify high_model_run and low_model_run filenames")
            return

        high_data = load_run_details(high_run)
        low_data = load_run_details(low_run)
        cases = load_eval_cases()
        if not high_data or not low_data:
            self.send_error_response(404, "One or both run files could not be loaded")
            return

        cases_by_id = {c["id"]: c for c in cases}
        high_by_id = {r["id"]: r for r in high_data.get("results", [])}
        low_by_id = {r["id"]: r for r in low_data.get("results", [])}

        sum_tpl = (WORKSPACE_DIR / "chw-edge-evals" / "prompts" / "summarize_patient.md").read_text(encoding="utf-8")
        rag_tpl = (WORKSPACE_DIR / "chw-edge-evals" / "prompts" / "visit_prep_rag.md").read_text(encoding="utf-8")

        created = 0
        for cid, h_item in high_by_id.items():
            if cid not in low_by_id or cid not in cases_by_id:
                continue
            case = cases_by_id[cid]
            l_item = low_by_id[cid]

            # Summarization check
            if h_item["summarization"]["tier1_pass"] and (not l_item["summarization"]["tier1_pass"] or h_item["summarization"]["output"] != l_item["summarization"]["output"]):
                sum_prompt = sum_tpl.replace("{{patient_markdown}}", case["patient_markdown"])
                rec = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "case_id": cid,
                    "task": "summarization",
                    "model_chosen": high_data.get("model", "high_model"),
                    "model_rejected": low_data.get("model", "low_model"),
                    "prompt": sum_prompt,
                    "chosen": h_item["summarization"]["output"],
                    "rejected": l_item["summarization"]["output"],
                    "critique_tags": l_item["summarization"].get("tier1_failures", []),
                    "rationale": "Auto-bootstrapped: High model passed all Tier-1 format and clinical checks.",
                }
                save_preference_record(rec)
                created += 1

            # Visit prep check
            if h_item["visit_prep_rag"]["tier1_pass"] and (not l_item["visit_prep_rag"]["tier1_pass"] or h_item["visit_prep_rag"]["output"] != l_item["visit_prep_rag"]["output"]):
                rag_prompt = (
                    rag_tpl
                    .replace("{{patient_markdown}}", case["patient_markdown"])
                    .replace("{{guideline_chunks}}", case["guideline_chunks"])
                    .replace("{{chw_question}}", case["chw_question"])
                )
                rec = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "case_id": cid,
                    "task": "visit_prep_rag",
                    "model_chosen": high_data.get("model", "high_model"),
                    "model_rejected": low_data.get("model", "low_model"),
                    "prompt": rag_prompt,
                    "chosen": h_item["visit_prep_rag"]["output"],
                    "rejected": l_item["visit_prep_rag"]["output"],
                    "critique_tags": l_item["visit_prep_rag"].get("tier1_failures", []),
                    "rationale": "Auto-bootstrapped: High model preserved critical danger signs and refusal boundaries.",
                }
                save_preference_record(rec)
                created += 1

        self.send_json_response({"message": f"Auto-bootstrapped {created} preference pairs", "pairs_created": created})

    def serve_studio_html(self):
        html = get_embedded_studio_html()
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def get_embedded_studio_html() -> str:
    """Return single-page web app styled with official OHS Foundation design tokens and components."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OHS Edge | Edge SLM Evaluation & RLHF Studio</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Hanken+Grotesk:ital,wght@0,300..800;1,300..800&family=IBM+Plex+Mono:ital,wght@0,400..600;1,400..600&display=swap');

    :root {
      --bg: #f8faf9;
      --bg-2: #f1f5f3;
      --surface: #ffffff;
      --ink: #1c2830;
      --ink-soft: #4e5f6a;
      --ink-faint: #778893;
      --line: #e1e8eb;
      --line-soft: #edf2f4;

      /* OHS Foundation palette tokens */
      --teal: #6f4cb3;
      --teal-deep: #54328c;
      --teal-bright: #8e61d8;
      --teal-wash: #f5f0fb;

      --core: #1f75a8;
      --core-wash: #edf5fb;

      --ai: #7a4db8;
      --ai-wash: #f3effa;

      --toolkit: #1e7e8b;
      --toolkit-wash: #ecf6f7;

      --green: #1ca564;
      --green-wash: #edf8f2;

      --amber: #d97e00;
      --amber-wash: #fef7ec;

      --rose: #dc3e42;
      --rose-wash: #fdf1f1;

      --radius: 12px;
      --radius-lg: 18px;
      --radius-pill: 999px;

      --shadow-sm: 0 1px 3px rgba(28, 40, 48, 0.05), 0 2px 6px rgba(28, 40, 48, 0.04);
      --shadow-md: 0 4px 14px rgba(28, 40, 48, 0.06), 0 12px 28px rgba(28, 40, 48, 0.05);
      --shadow-lg: 0 10px 30px rgba(28, 40, 48, 0.08), 0 24px 60px rgba(28, 40, 48, 0.08);
    }

    body {
      font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
      color: var(--ink);
      background-color: var(--bg);
      -webkit-font-smoothing: antialiased;
    }

    pre, code {
      font-family: 'IBM Plex Mono', monospace;
    }

    /* OHS Foundation Brand Mark (4-rounded-square stack) */
    .logo-mark {
      display: inline-grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 2.5px;
      width: 26px;
      height: 26px;
    }
    .logo-mark i {
      border-radius: 4px;
      display: block;
    }
    .logo-mark i:nth-child(1) { background: var(--teal); }
    .logo-mark i:nth-child(2) { background: var(--core); }
    .logo-mark i:nth-child(3) { background: var(--ai); }
    .logo-mark i:nth-child(4) { background: var(--teal-deep); }

    .brandname {
      line-height: 1.15;
    }
    .brandname b {
      display: block;
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--ink);
      letter-spacing: -0.01em;
    }
    .brandname span {
      display: block;
      font-size: 0.65rem;
      font-weight: 600;
      color: var(--ink-faint);
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }

    /* Cards */
    .ohs-card {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-sm);
      transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
    }
    .ohs-card:hover {
      box-shadow: var(--shadow-md);
      border-color: #cbd7dc;
    }

    /* Buttons */
    .btn-pill {
      border-radius: var(--radius-pill);
      font-family: inherit;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 0.5em;
      transition: all 0.2s ease;
    }
    .btn-primary {
      background: var(--ai);
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(122, 77, 184, 0.25);
    }
    .btn-primary:hover {
      background: var(--teal-deep);
      transform: translateY(-1px);
    }
    .btn-secondary {
      background: var(--surface);
      border: 1px solid var(--line);
      color: var(--ink);
    }
    .btn-secondary:hover {
      background: var(--bg-2);
      border-color: #cbd7dc;
    }
    .btn-success {
      background: var(--green);
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(28, 165, 100, 0.25);
    }
    .btn-success:hover {
      background: #178a53;
      transform: translateY(-1px);
    }

    /* Badges */
    .badge-pass {
      background-color: var(--green-wash);
      color: var(--green);
      border: 1px solid rgba(28, 165, 100, 0.3);
    }
    .badge-fail {
      background-color: var(--rose-wash);
      color: var(--rose);
      border: 1px solid rgba(220, 62, 66, 0.3);
    }
    .badge-ai {
      background-color: var(--ai-wash);
      color: var(--ai);
      border: 1px solid rgba(122, 77, 184, 0.25);
    }
    .badge-core {
      background-color: var(--core-wash);
      color: var(--core);
      border: 1px solid rgba(31, 117, 168, 0.25);
    }
    .badge-toolkit {
      background-color: var(--toolkit-wash);
      color: var(--toolkit);
      border: 1px solid rgba(30, 126, 139, 0.25);
    }

    .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scroll::-webkit-scrollbar-track { background: var(--bg-2); }
    .custom-scroll::-webkit-scrollbar-thumb { background: #cbd7dc; border-radius: 3px; }
  </style>
</head>
<body class="min-h-screen flex flex-col">

  <!-- OHS Foundation Header -->
  <header class="sticky top-0 z-50 px-6 py-3 border-b border-[#e1e8eb] bg-[#f8faf9]/90 backdrop-blur-md flex items-center justify-between">
    <div class="flex items-center space-x-3">
      <div class="logo-mark" aria-hidden="true">
        <i></i><i></i><i></i><i></i>
      </div>
      <div class="brandname">
        <b>Open Health Stack</b>
        <span>Software Foundation &bull; AI Commons</span>
      </div>
      <span class="hidden md:inline-flex text-[11px] font-semibold px-2.5 py-0.5 rounded-full badge-ai ml-2">
        OHS Edge Edge Evals
      </span>
    </div>

    <!-- Live Status Pill & Global Actions -->
    <div class="flex items-center space-x-3">
      <div id="runner-status-pill" class="flex items-center space-x-2 text-xs px-3.5 py-1.5 rounded-full bg-white border border-[#e1e8eb] shadow-sm">
        <span class="w-2 h-2 rounded-full bg-slate-400" id="runner-dot"></span>
        <span id="runner-text" class="text-[#4e5f6a] font-medium">Runner Idle</span>
      </div>
      <button onclick="refreshAll()" class="p-2 text-[#4e5f6a] hover:text-[#1c2830] hover:bg-[#edf2f4] rounded-full transition" title="Refresh Data">
        <i class="fa-solid fa-rotate"></i>
      </button>
    </div>
  </header>

  <!-- OHS Navigation Tabs -->
  <nav class="bg-white border-b border-[#e1e8eb] px-6 flex space-x-1 overflow-x-auto text-sm shadow-xs">
    <button onclick="switchTab('dashboard')" id="tab-dashboard" class="tab-btn px-4 py-3 font-semibold border-b-2 border-[#7a4db8] text-[#7a4db8] flex items-center space-x-2">
      <i class="fa-solid fa-chart-column text-xs"></i><span>Benchmark Overview</span>
    </button>
    <button onclick="switchTab('explorer')" id="tab-explorer" class="tab-btn px-4 py-3 font-medium border-b-2 border-transparent text-[#4e5f6a] hover:text-[#1c2830] flex items-center space-x-2">
      <i class="fa-solid fa-microscope text-xs"></i><span>Evaluation Visualizer</span>
    </button>
    <button onclick="switchTab('comparator')" id="tab-comparator" class="tab-btn px-4 py-3 font-medium border-b-2 border-transparent text-[#4e5f6a] hover:text-[#1c2830] flex items-center space-x-2">
      <i class="fa-solid fa-code-compare text-xs"></i><span>Side-by-Side Comparator</span>
    </button>
    <button onclick="switchTab('runner')" id="tab-runner" class="tab-btn px-4 py-3 font-medium border-b-2 border-transparent text-[#4e5f6a] hover:text-[#1c2830] flex items-center space-x-2">
      <i class="fa-solid fa-play text-xs"></i><span>Live Eval Runner</span>
    </button>
    <button onclick="switchTab('rlhf')" id="tab-rlhf" class="tab-btn px-4 py-3 font-medium border-b-2 border-transparent text-[#4e5f6a] hover:text-[#1c2830] flex items-center space-x-2">
      <i class="fa-solid fa-scale-balanced text-xs"></i><span>RLHF / DPO Studio</span>
      <span id="dpo-count-badge" class="ml-1 text-[10px] bg-[#f3effa] text-[#7a4db8] px-1.5 py-0.2 rounded-full font-bold">0</span>
    </button>
    <button onclick="switchTab('pipeline')" id="tab-pipeline" class="tab-btn px-4 py-3 font-medium border-b-2 border-transparent text-[#4e5f6a] hover:text-[#1c2830] flex items-center space-x-2">
      <i class="fa-solid fa-graduation-cap text-xs"></i><span>Fine-Tuning Guide</span>
    </button>
  </nav>


  <!-- Main Container -->
  <main class="flex-1 p-6 max-w-7xl w-full mx-auto">

    <!-- TAB 1: BENCHMARK OVERVIEW -->
    <section id="view-dashboard" class="space-y-6">
      <!-- Run Selector & Summary Banner -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 ohs-card p-5 bg-white border border-[#e1e8eb]">
        <div>
          <label class="text-[11px] uppercase tracking-wider text-[#778893] font-semibold block mb-1">Active Benchmark Report</label>
          <div class="flex items-center space-x-3">
            <select id="run-select" onchange="loadSelectedRun()" class="bg-[#f8faf9] border border-[#cbd7dc] text-[#1c2830] rounded-lg px-3.5 py-2 text-xs font-medium focus:ring-2 focus:ring-[#7a4db8] focus:outline-none">
              <option value="">Loading benchmark runs...</option>
            </select>
            <span id="run-timestamp" class="text-xs text-[#778893]"></span>
          </div>
        </div>
        <div class="flex items-center space-x-3">
          <button onclick="switchTab('runner')" class="btn-pill btn-primary px-4 py-2 text-xs">
            <i class="fa-solid fa-plus text-[11px]"></i><span>Launch New Run</span>
          </button>
        </div>
      </div>

      <!-- KPI Metrics Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="ohs-card p-5 bg-white border border-[#e1e8eb] flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-[#778893] uppercase tracking-wider">Tier-1 Pass Rate</p>
            <h3 id="metric-pass-rate" class="text-2xl font-bold text-[#1c2830] mt-1">--%</h3>
            <p id="metric-pass-count" class="text-xs text-[#4e5f6a] mt-0.5">-- / -- checks passed</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-[#edf8f2] border border-[#1ca564]/30 flex items-center justify-center text-[#1ca564] text-xl shadow-xs">
            <i class="fa-solid fa-check-double"></i>
          </div>
        </div>

        <div class="ohs-card p-5 bg-white border border-[#e1e8eb] flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-[#778893] uppercase tracking-wider">Summarization Pass</p>
            <h3 id="metric-sum-rate" class="text-2xl font-bold text-[#1c2830] mt-1">--%</h3>
            <p id="metric-sum-count" class="text-xs text-[#4e5f6a] mt-0.5">-- cases passed</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-[#edf5fb] border border-[#1f75a8]/30 flex items-center justify-center text-[#1f75a8] text-xl shadow-xs">
            <i class="fa-solid fa-file-lines"></i>
          </div>
        </div>

        <div class="ohs-card p-5 bg-white border border-[#e1e8eb] flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-[#778893] uppercase tracking-wider">Mini-RAG Protocol Pass</p>
            <h3 id="metric-rag-rate" class="text-2xl font-bold text-[#1c2830] mt-1">--%</h3>
            <p id="metric-rag-count" class="text-xs text-[#4e5f6a] mt-0.5">-- cases passed</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-[#ecf6f7] border border-[#1e7e8b]/30 flex items-center justify-center text-[#1e7e8b] text-xl shadow-xs">
            <i class="fa-solid fa-notes-medical"></i>
          </div>
        </div>

        <div class="ohs-card p-5 bg-white border border-[#e1e8eb] flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-[#778893] uppercase tracking-wider">Edge Decode Speed</p>
            <h3 id="metric-speed" class="text-2xl font-bold text-[#1c2830] mt-1">-- t/s</h3>
            <p id="metric-latency" class="text-xs text-[#4e5f6a] mt-0.5">Avg latency: --s</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-[#fef7ec] border border-[#d97e00]/30 flex items-center justify-center text-[#d97e00] text-xl shadow-xs">
            <i class="fa-solid fa-bolt"></i>
          </div>
        </div>
      </div>

      <!-- Models Comparative Table -->
      <div class="ohs-card bg-white border border-[#e1e8eb] overflow-hidden">
        <div class="px-5 py-4 border-b border-[#e1e8eb] bg-[#f8faf9] flex items-center justify-between">
          <h2 class="font-bold text-[#1c2830] text-sm flex items-center space-x-2">
            <i class="fa-solid fa-trophy text-[#d97e00]"></i>
            <span>Multi-Model Benchmark Comparison</span>
          </h2>
          <span class="text-xs text-[#778893]">Evaluated on 20 Golden Clinical Scenarios</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-[#1c2830]">
            <thead class="bg-[#f1f5f3] text-[#4e5f6a] border-b border-[#e1e8eb]">
              <tr>
                <th class="px-5 py-3 font-semibold">Model Name</th>
                <th class="px-5 py-3 font-semibold">Tier-1 Score</th>
                <th class="px-5 py-3 font-semibold">Pass Rate</th>
                <th class="px-5 py-3 font-semibold">Summarization</th>
                <th class="px-5 py-3 font-semibold">Mini-RAG Protocol</th>
                <th class="px-5 py-3 font-semibold">Tier-2 Judge</th>
                <th class="px-5 py-3 font-semibold">Timestamp</th>
                <th class="px-5 py-3 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody id="models-table-body" class="divide-y divide-[#edf2f4]">
              <tr><td colspan="8" class="text-center py-6 text-[#778893]">Loading model runs...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 2: EVALUATION VISUALIZER & CASE EXPLORER -->
    <section id="view-explorer" class="space-y-6 hidden">
      <!-- Filters and Search Toolbar -->
      <div class="flex flex-col md:flex-row gap-4 items-center justify-between ohs-card p-4 bg-white border border-[#e1e8eb]">
        <div class="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div class="relative flex-1 md:w-64">
            <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-[#778893] text-xs"></i>
            <input type="text" id="explorer-search" oninput="filterExplorerCases()" placeholder="Search patient, symptoms..." class="w-full pl-9 pr-3 py-2 bg-[#f8faf9] border border-[#cbd7dc] rounded-lg text-xs text-[#1c2830] placeholder-[#778893] focus:outline-none focus:ring-1 focus:ring-[#7a4db8]">
          </div>
          <select id="explorer-domain-filter" onchange="filterExplorerCases()" class="bg-[#f8faf9] border border-[#cbd7dc] text-[#1c2830] text-xs rounded-lg px-3 py-2 focus:outline-none">
            <option value="ALL">All Clinical Domains</option>
            <option value="ANC">Antenatal Care (ANC)</option>
            <option value="Child_iCCM">Child Health & iCCM</option>
            <option value="NCD">Chronic NCDs</option>
            <option value="Infectious">Infectious Diseases</option>
            <option value="PNC">Postnatal Care (PNC)</option>
          </select>
          <select id="explorer-status-filter" onchange="filterExplorerCases()" class="bg-[#f8faf9] border border-[#cbd7dc] text-[#1c2830] text-xs rounded-lg px-3 py-2 focus:outline-none">
            <option value="ALL">All Statuses</option>
            <option value="PASS">Passed Both Checks</option>
            <option value="FAIL">Any Failure</option>
          </select>
        </div>
        <div class="text-xs text-[#778893] font-medium" id="explorer-count-label">Showing 20 cases</div>
      </div>

      <!-- Cases Cards Grid -->
      <div id="explorer-cards-container" class="space-y-4">
        <!-- Rendered dynamically -->
      </div>
    </section>

    <!-- TAB 3: SIDE-BY-SIDE COMPARATOR -->
    <section id="view-comparator" class="space-y-6 hidden">
      <div class="ohs-card p-5 bg-white border border-[#e1e8eb] flex flex-col md:flex-row items-center gap-4 justify-between">
        <div class="flex items-center space-x-3 w-full md:w-auto">
          <div>
            <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Candidate Model A</label>
            <select id="comp-model-a" onchange="renderComparison()" class="bg-[#f8faf9] border border-[#cbd7dc] text-[#1c2830] text-xs rounded-lg px-3 py-2">
            </select>
          </div>
          <div class="text-[#778893] font-bold mt-5 text-xs">VS</div>
          <div>
            <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Candidate Model B</label>
            <select id="comp-model-b" onchange="renderComparison()" class="bg-[#f8faf9] border border-[#cbd7dc] text-[#1c2830] text-xs rounded-lg px-3 py-2">
            </select>
          </div>
        </div>
        <div class="w-full md:w-auto">
          <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Select Clinical Case</label>
          <select id="comp-case-select" onchange="renderComparison()" class="bg-[#f8faf9] border border-[#cbd7dc] text-[#1c2830] text-xs rounded-lg px-3 py-2 w-full md:w-80">
          </select>
        </div>
      </div>

      <div id="comp-results-view" class="space-y-6">
        <!-- Rendered dynamically -->
      </div>
    </section>

    <!-- TAB 4: LIVE VISUAL EVAL RUNNER -->
    <section id="view-runner" class="space-y-6 hidden">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Configuration Card -->
        <div class="ohs-card p-6 bg-white border border-[#e1e8eb] space-y-4 lg:col-span-1">
          <h2 class="text-sm font-bold text-[#1c2830] flex items-center space-x-2">
            <i class="fa-solid fa-sliders text-[#7a4db8]"></i>
            <span>Run Configuration</span>
          </h2>

          <div>
            <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Target On-Device Model (Ollama)</label>
            <input type="text" id="runner-model-input" value="gemma2:2b-instruct-q4_K_M" class="w-full bg-[#f8faf9] border border-[#cbd7dc] rounded-lg px-3.5 py-2 text-xs text-[#1c2830] focus:ring-1 focus:ring-[#7a4db8] focus:outline-none">
            <p class="text-[11px] text-[#778893] mt-1">E.g., gemma2:2b-instruct-q4_K_M, llama3.2:3b, qwen2.5:3b</p>
          </div>

          <div>
            <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Ollama API Base URL</label>
            <input type="text" id="runner-apibase-input" value="http://localhost:11434" class="w-full bg-[#f8faf9] border border-[#cbd7dc] rounded-lg px-3.5 py-2 text-xs text-[#1c2830] focus:ring-1 focus:ring-[#7a4db8] focus:outline-none">
          </div>

          <div class="border-t border-[#e1e8eb] pt-3">
            <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Tier-2 Clinical Judge Model</label>
            <select id="runner-judge-select" class="w-full bg-[#f8faf9] border border-[#cbd7dc] rounded-lg px-3.5 py-2 text-xs text-[#1c2830] focus:ring-1 focus:ring-[#7a4db8] focus:outline-none">
              <option value="">None (Tier-1 Deterministic Only)</option>
              <option value="gemini-3.8-flash">Google Gemini 3.8 Flash (Cloud)</option>
              <option value="gemma4:latest">Ollama Gemma 4 (Local)</option>
              <option value="gpt-4o">OpenAI GPT-4o</option>
              <option value="claude-3-5-sonnet-20241022">Anthropic Claude 3.5 Sonnet</option>
            </select>
          </div>

          <div>
            <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Judge API Key (Optional)</label>
            <input type="password" id="runner-judgekey-input" placeholder="GEMINI_API_KEY / OPENAI_API_KEY" class="w-full bg-[#f8faf9] border border-[#cbd7dc] rounded-lg px-3.5 py-2 text-xs text-[#1c2830] focus:ring-1 focus:ring-[#7a4db8] focus:outline-none">
            <p class="text-[11px] text-[#778893] mt-1">If blank, loads from local environment or .env</p>
          </div>

          <div class="flex items-center space-x-2 pt-2">
            <input type="checkbox" id="runner-dryrun-input" class="rounded bg-[#f8faf9] border-[#cbd7dc] text-[#1ca564] focus:ring-0">
            <label for="runner-dryrun-input" class="text-xs text-[#4e5f6a] font-medium cursor-pointer">Dry-Run Mode (Mock inference for instant test)</label>
          </div>

          <button id="btn-start-run" onclick="startEvaluationRun()" class="btn-pill btn-success w-full py-2.5 text-xs justify-center font-bold">
            <i class="fa-solid fa-play text-xs"></i><span>Execute Evaluation Suite</span>
          </button>
        </div>

        <!-- Terminal & Real-Time Log Card -->
        <div class="ohs-card p-6 bg-white border border-[#e1e8eb] lg:col-span-2 flex flex-col h-[520px]">
          <div class="flex items-center justify-between pb-3 border-b border-[#e1e8eb]">
            <div class="flex items-center space-x-2">
              <i class="fa-solid fa-terminal text-[#4e5f6a] text-xs"></i>
              <h2 class="text-xs font-bold uppercase tracking-wider text-[#1c2830]">Execution Output & Telemetry</h2>
            </div>
            <span id="runner-exec-time" class="text-xs text-[#778893] font-medium">Ready</span>
          </div>

          <pre id="runner-logs" class="flex-1 overflow-y-auto custom-scroll bg-[#111820] p-4 rounded-lg border border-[#23313d] text-xs text-[#d6e2e9] font-mono mt-3 whitespace-pre-wrap">Awaiting evaluation run launch...</pre>
        </div>
      </div>
    </section>

    <!-- TAB 5: RLHF & DPO PREFERENCE STUDIO -->
    <section id="view-rlhf" class="space-y-6 hidden">
      <!-- Curation Header & Actions -->
      <div class="ohs-card p-5 bg-white border border-[#e1e8eb] flex flex-col md:flex-row items-center justify-between gap-4">

        <div>
          <h2 class="text-sm font-bold text-[#1c2830] flex items-center space-x-2">
            <i class="fa-solid fa-scale-balanced text-[#7a4db8]"></i>
            <span>Human & AI Clinical Preference Studio (RLHF / DPO)</span>
          </h2>
          <p class="text-xs text-[#4e5f6a] mt-1">Review candidate SLM responses, vote on clinical preference, edit gold corrections, and export directly to Hugging Face TRL.</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button onclick="autoBootstrapDpo()" class="btn-pill btn-primary px-3.5 py-2 text-xs">
            <i class="fa-solid fa-wand-magic-sparkles text-[11px]"></i><span>Auto-Bootstrap Pairs</span>
          </button>
          <a href="/api/preferences" target="_blank" class="btn-pill btn-secondary px-3.5 py-2 text-xs">
            <i class="fa-solid fa-download text-[11px] text-[#4e5f6a]"></i><span>Export TRL JSONL</span>
          </a>
        </div>
      </div>

      <!-- Annotation Studio Card -->
      <div class="ohs-card p-6 bg-white border border-[#e1e8eb] space-y-6">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Select Case for Review</label>
            <select id="rlhf-case-select" onchange="renderRlhfStudio()" class="w-full bg-[#f8faf9] border border-[#cbd7dc] text-[#1c2830] text-xs rounded-lg px-3 py-2 font-medium">
            </select>
          </div>
          <div>
            <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Task Type</label>
            <select id="rlhf-task-select" onchange="renderRlhfStudio()" class="w-full bg-[#f8faf9] border border-[#cbd7dc] text-[#1c2830] text-xs rounded-lg px-3 py-2 font-medium">
              <option value="summarization">Task 1: Pre-Visit Summarization (&le; 120 words)</option>
              <option value="visit_prep_rag">Task 2: Mini-RAG Visit Prep (&le; 130 words)</option>
            </select>
          </div>
          <div>
            <label class="text-xs font-semibold text-[#4e5f6a] block mb-1">Comparison Pair</label>
            <select id="rlhf-pair-select" onchange="renderRlhfStudio()" class="w-full bg-[#f8faf9] border border-[#cbd7dc] text-[#1c2830] text-xs rounded-lg px-3 py-2 font-medium">
              <option value="gemma4_vs_gemma2">Gemma 4 (Teacher) vs Gemma 2 2B (Student SLM)</option>
            </select>
          </div>
        </div>

        <!-- Prompt Preview (Collapsible) -->
        <div class="border border-[#e1e8eb] rounded-xl p-3.5 bg-[#f8faf9]">
          <div class="flex items-center justify-between cursor-pointer" onclick="togglePromptCollapse()">
            <span class="text-xs font-bold text-[#1c2830] flex items-center space-x-2">
              <i class="fa-solid fa-clipboard-question text-[#1f75a8]"></i>
              <span>Patient Clinical Context & Instruction Prompt</span>
            </span>
            <span class="text-[10px] text-[#778893] font-medium" id="prompt-toggle-icon">Click to toggle</span>
          </div>
          <pre id="rlhf-prompt-text" class="text-xs text-[#d6e2e9] bg-[#111820] p-3 rounded-lg border border-[#23313d] mt-2 whitespace-pre-wrap max-h-36 overflow-y-auto custom-scroll hidden"></pre>
        </div>

        <!-- Pairwise Review Panes -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <!-- Candidate A -->
          <div class="border border-[#e1e8eb] rounded-xl p-5 bg-white space-y-3 flex flex-col justify-between shadow-xs">
            <div>
              <div class="flex items-center justify-between pb-2 border-b border-[#e1e8eb]">
                <span class="text-xs font-bold text-[#1ca564] flex items-center space-x-1.5">
                  <i class="fa-solid fa-cube"></i><span id="rlhf-model-a-name">Candidate Model A</span>
                </span>
                <span id="rlhf-model-a-words" class="text-[11px] text-[#778893] font-medium">-- words</span>
              </div>
              <div id="rlhf-output-a" class="mt-3 text-xs text-[#1c2830] whitespace-pre-wrap leading-relaxed min-h-[140px]"></div>
            </div>
            <button onclick="submitPreferenceVote('A')" class="btn-pill btn-success w-full mt-4 py-2.5 text-xs justify-center font-bold">
              <i class="fa-solid fa-thumbs-up text-xs"></i><span>Select Candidate A as CHOSEN</span>
            </button>
          </div>

          <!-- Candidate B -->
          <div class="border border-[#e1e8eb] rounded-xl p-5 bg-white space-y-3 flex flex-col justify-between shadow-xs">
            <div>
              <div class="flex items-center justify-between pb-2 border-b border-[#e1e8eb]">
                <span class="text-xs font-bold text-[#1f75a8] flex items-center space-x-1.5">
                  <i class="fa-solid fa-cube"></i><span id="rlhf-model-b-name">Candidate Model B</span>
                </span>
                <span id="rlhf-model-b-words" class="text-[11px] text-[#778893] font-medium">-- words</span>
              </div>
              <div id="rlhf-output-b" class="mt-3 text-xs text-[#1c2830] whitespace-pre-wrap leading-relaxed min-h-[140px]"></div>
            </div>
            <button onclick="submitPreferenceVote('B')" class="btn-pill btn-primary w-full mt-4 py-2.5 text-xs justify-center font-bold">
              <i class="fa-solid fa-thumbs-up text-xs"></i><span>Select Candidate B as CHOSEN</span>
            </button>
          </div>
        </div>

        <!-- Clinical Critique & Failure Tagger -->
        <div class="bg-[#f8faf9] p-4 rounded-xl border border-[#e1e8eb] space-y-3">
          <label class="text-xs font-bold text-[#1c2830] block">Clinical Failure Tags for Rejected Completion:</label>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <label class="flex items-center space-x-2 text-[#4e5f6a] cursor-pointer">
              <input type="checkbox" name="critique" value="temporal_resolved_trap" class="rounded bg-white border-[#cbd7dc] text-[#dc3e42] focus:ring-0">
              <span>Resolved Disease as Active</span>
            </label>
            <label class="flex items-center space-x-2 text-[#4e5f6a] cursor-pointer">
              <input type="checkbox" name="critique" value="word_budget_exceeded" class="rounded bg-white border-[#cbd7dc] text-[#dc3e42] focus:ring-0">
              <span>Exceeded Word Limit</span>
            </label>
            <label class="flex items-center space-x-2 text-[#4e5f6a] cursor-pointer">
              <input type="checkbox" name="critique" value="missing_danger_sign" class="rounded bg-white border-[#cbd7dc] text-[#dc3e42] focus:ring-0">
              <span>Missed Red Flag / Referral</span>
            </label>
            <label class="flex items-center space-x-2 text-[#4e5f6a] cursor-pointer">
              <input type="checkbox" name="critique" value="unauthorized_advice" class="rounded bg-white border-[#cbd7dc] text-[#dc3e42] focus:ring-0">
              <span>Prescribed Medication</span>
            </label>
          </div>
        </div>

        <!-- Gold Correction Editor -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <label class="text-xs font-bold text-[#1c2830] flex items-center space-x-1.5">
              <i class="fa-solid fa-pen-to-square text-[#7a4db8]"></i>
              <span>Human Expert Gold Demonstration (Optional Correction for SFT / DPO Target)</span>
            </label>
            <span id="gold-word-counter" class="text-[11px] text-[#778893] font-medium">0 words</span>
          </div>
          <textarea id="rlhf-gold-editor" oninput="updateGoldWordCount()" rows="4" placeholder="Edit or write the ideal clinical response here..." class="w-full bg-[#f8faf9] border border-[#cbd7dc] rounded-lg p-3 text-xs text-[#1c2830] focus:ring-1 focus:ring-[#7a4db8] focus:outline-none custom-scroll"></textarea>
          <div class="flex justify-end space-x-3">
            <button onclick="saveGoldAsSft()" class="btn-pill btn-secondary px-4 py-2 text-xs font-semibold text-[#7a4db8] border-[#7a4db8]/40 hover:bg-[#f3effa]">
              <i class="fa-solid fa-bookmark mr-1"></i> Save as Gold SFT Demonstration
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 6: FINE-TUNING PIPELINE GUIDE -->
    <section id="view-pipeline" class="space-y-6 hidden">
      <div class="ohs-card p-6 bg-white border border-[#e1e8eb] space-y-4">
        <h2 class="text-sm font-bold text-[#1c2830] flex items-center space-x-2">
          <i class="fa-solid fa-rocket text-[#7a4db8]"></i>
          <span>Edge SLM Fine-Tuning Execution Pipeline</span>
        </h2>
        <p class="text-xs text-[#4e5f6a] leading-relaxed">
          Follow these 3 steps to take your exported clinical preference dataset and fine-tune Gemma 2 2B or Llama 3.2 3B using <strong>Direct Preference Optimization (DPO)</strong> and QLoRA.
        </p>

        <div class="space-y-4 pt-2">
          <div class="p-4 rounded-xl bg-[#f8faf9] border border-[#e1e8eb]">
            <h3 class="text-xs font-bold text-[#1ca564] uppercase tracking-wider mb-1">Step 1: Inspect & Validate Exported DPO Dataset</h3>
            <p class="text-xs text-[#4e5f6a] mb-2">Check the generated pairs in <code class="text-[#1c2830] font-bold">chw-edge-evals/dataset/dpo_preference_data.jsonl</code>:</p>
            <pre class="bg-[#111820] text-[#d6e2e9] border border-[#23313d] p-3 rounded-lg text-[11px] overflow-x-auto">python3 fine_tune_slm_dpo.py --dataset chw-edge-evals/dataset/dpo_preference_data.jsonl --dry-run</pre>
          </div>

          <div class="p-4 rounded-xl bg-[#f8faf9] border border-[#e1e8eb]">
            <h3 class="text-xs font-bold text-[#1f75a8] uppercase tracking-wider mb-1">Step 2: Run DPO QLoRA Fine-Tuning</h3>
            <p class="text-xs text-[#4e5f6a] mb-2">Train the LoRA adapter with Hugging Face TRL on GPU or Mac MPS:</p>
            <pre class="bg-[#111820] text-[#d6e2e9] border border-[#23313d] p-3 rounded-lg text-[11px] overflow-x-auto">python3 fine_tune_slm_dpo.py \
  --dataset chw-edge-evals/dataset/dpo_preference_data.jsonl \
  --model-id google/gemma-2-2b-it \
  --output-dir ./gemma2_chw_dpo_adapter \
  --epochs 3 --lr 5e-6 --beta 0.1</pre>
          </div>

          <div class="p-4 rounded-xl bg-[#f8faf9] border border-[#e1e8eb]">
            <h3 class="text-xs font-bold text-[#7a4db8] uppercase tracking-wider mb-1">Step 3: Convert to GGUF and Register in Ollama</h3>
            <p class="text-xs text-[#4e5f6a] mb-2">Merge weights, quantize to INT4/INT8 GGUF, and verify in the Visual Runner:</p>
            <pre class="bg-[#111820] text-[#d6e2e9] border border-[#23313d] p-3 rounded-lg text-[11px] overflow-x-auto"># Merge adapter and export to GGUF
python3 llama.cpp/convert_hf_to_gguf.py ./merged_model --outfile ./gemma2-2b-chw-dpo.gguf --outtype q8_0

# Create Ollama model
ollama create gemma2:2b-chw-dpo -f Modelfile.dpo

# Re-run benchmark to verify pass-rate improvements
python3 chw-edge-evals/run_evals.py --model gemma2:2b-chw-dpo</pre>
          </div>
        </div>
      </div>
    </section>


  </main>

  <script>
    // State
    let runsList = [];
    let currentRunData = null;
    let evalCases = [];
    let preferences = [];
    let currentTab = 'dashboard';
    let pollInterval = null;

    async function init() {
      await loadCases();
      await loadRuns();
      await loadPreferencesCount();
      startRunnerPolling();
    }

    async function loadCases() {
      try {
        const res = await fetch('/api/cases');
        evalCases = await res.json();
        populateCaseSelectors();
      } catch (e) {
        console.error('Failed to load cases:', e);
      }
    }

    async function loadRuns() {
      try {
        const res = await fetch('/api/runs');
        runsList = await res.json();
        populateRunSelectors();
        renderModelsTable();
        if (runsList.length > 0) {
          const select = document.getElementById('run-select');
          if (select && select.value) {
            await loadRunDetails(select.value);
          } else if (runsList.length > 0) {
            select.value = runsList[0].filename;
            await loadRunDetails(runsList[0].filename);
          }
        }
      } catch (e) {
        console.error('Failed to load runs:', e);
      }
    }

    async function loadPreferencesCount() {
      try {
        const res = await fetch('/api/preferences');
        preferences = await res.json();
        const badge = document.getElementById('dpo-count-badge');
        if (badge) badge.innerText = preferences.length;
      } catch (e) {}
    }

    function populateRunSelectors() {
      const select = document.getElementById('run-select');
      const compA = document.getElementById('comp-model-a');
      const compB = document.getElementById('comp-model-b');
      if (!select) return;

      select.innerHTML = '';
      compA.innerHTML = '';
      compB.innerHTML = '';

      runsList.forEach((r, idx) => {
        const opt = document.createElement('option');
        opt.value = r.filename;
        opt.innerText = `${r.model} (${r.pass_rate_pct}% - ${r.passes}/${r.total_checks})`;
        select.appendChild(opt);

        const optA = opt.cloneNode(true);
        const optB = opt.cloneNode(true);
        compA.appendChild(optA);
        compB.appendChild(optB);
      });

      if (runsList.length > 1) {
        compB.selectedIndex = 1;
      }
    }

    function populateCaseSelectors() {
      const compSelect = document.getElementById('comp-case-select');
      const rlhfSelect = document.getElementById('rlhf-case-select');
      if (!compSelect || !rlhfSelect) return;

      compSelect.innerHTML = '';
      rlhfSelect.innerHTML = '';

      evalCases.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.innerText = `[${c.domain || 'General'}] ${c.title}`;
        compSelect.appendChild(opt);

        const opt2 = opt.cloneNode(true);
        rlhfSelect.appendChild(opt2);
      });
    }

    async function loadSelectedRun() {
      const select = document.getElementById('run-select');
      if (select && select.value) {
        await loadRunDetails(select.value);
      }
    }

    async function loadRunDetails(filename) {
      try {
        const res = await fetch(`/api/runs/${filename}`);
        currentRunData = await res.json();
        updateDashboardMetrics();
        renderExplorerCases();
        renderComparison();
        renderRlhfStudio();
      } catch (e) {
        console.error('Failed to load run details:', e);
      }
    }

    function updateDashboardMetrics() {
      if (!currentRunData) return;
      document.getElementById('run-timestamp').innerText = currentRunData.timestamp ? new Date(currentRunData.timestamp).toLocaleString() : '';
      document.getElementById('metric-pass-rate').innerText = `${currentRunData.pass_rate_pct}%`;
      document.getElementById('metric-pass-count').innerText = `${currentRunData.passes} / ${currentRunData.total_checks} checks passed`;

      const results = currentRunData.results || [];
      const sumPasses = results.filter(r => r.summarization?.tier1_pass).length;
      const ragPasses = results.filter(r => r.visit_prep_rag?.tier1_pass).length;

      document.getElementById('metric-sum-rate').innerText = results.length ? `${Math.round((sumPasses / results.length) * 100)}%` : '--%';
      document.getElementById('metric-sum-count').innerText = `${sumPasses} / ${results.length} cases`;

      document.getElementById('metric-rag-rate').innerText = results.length ? `${Math.round((ragPasses / results.length) * 100)}%` : '--%';
      document.getElementById('metric-rag-count').innerText = `${ragPasses} / ${results.length} cases`;

      let totalSpeed = 0, totalLatency = 0, count = 0;
      results.forEach(r => {
        if (r.summarization?.metrics?.tok_per_sec) {
          totalSpeed += r.summarization.metrics.tok_per_sec;
          totalLatency += r.summarization.metrics.latency_s || 0;
          count++;
        }
      });
      const avgSpeed = count ? (totalSpeed / count).toFixed(1) : '--';
      const avgLatency = count ? (totalLatency / count).toFixed(2) : '--';

      document.getElementById('metric-speed').innerText = `${avgSpeed} t/s`;
      document.getElementById('metric-latency').innerText = `Avg latency: ${avgLatency}s`;
    }

    function renderModelsTable() {
      const tbody = document.getElementById('models-table-body');
      if (!tbody) return;
      tbody.innerHTML = '';

      if (runsList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-slate-500">No benchmark runs found. Launch one in Live Runner!</td></tr>';
        return;
      }

      runsList.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-[#f8faf9] transition';
        const passBadge = r.pass_rate_pct >= 80 ? 'badge-pass' : 'badge-fail';
        tr.innerHTML = `
          <td class="px-5 py-3 font-semibold text-[#1c2830] flex items-center space-x-2">
            <i class="fa-solid fa-microchip text-[#7a4db8]"></i>
            <span>${r.model}</span>
          </td>
          <td class="px-5 py-3 font-mono font-medium">${r.passes}/${r.total_checks}</td>
          <td class="px-5 py-3"><span class="px-2 py-0.5 rounded-full text-[11px] font-bold ${passBadge}">${r.pass_rate_pct}%</span></td>
          <td class="px-5 py-3 text-[#4e5f6a]">${r.cases_count} cases</td>
          <td class="px-5 py-3 text-[#4e5f6a]">${r.cases_count} cases</td>
          <td class="px-5 py-3 text-[#778893]">${r.judge_model || 'None'}</td>
          <td class="px-5 py-3 text-[#778893]">${r.timestamp ? new Date(r.timestamp).toLocaleDateString() : 'N/A'}</td>
          <td class="px-5 py-3 text-right">
            <button onclick="inspectRun('${r.filename}')" class="btn-pill btn-secondary px-3 py-1 text-xs text-[#7a4db8] hover:bg-[#f3effa] font-bold">Inspect</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function inspectRun(filename) {
      const select = document.getElementById('run-select');
      if (select) select.value = filename;
      loadRunDetails(filename);
      switchTab('explorer');
    }

    function renderExplorerCases() {
      const container = document.getElementById('explorer-cards-container');
      if (!container || !currentRunData) return;

      const results = currentRunData.results || [];
      const casesById = {};
      evalCases.forEach(c => casesById[c.id] = c);

      container.innerHTML = '';

      results.forEach(res => {
        const caseMeta = casesById[res.id] || {};
        const sumPass = res.summarization?.tier1_pass;
        const ragPass = res.visit_prep_rag?.tier1_pass;
        const allPass = sumPass && ragPass;

        const card = document.createElement('div');
        card.className = `ohs-card p-5 bg-white border ${allPass ? 'border-[#e1e8eb]' : 'border-[#dc3e42]/40'} space-y-4 explorer-case-card`;
        card.dataset.domain = caseMeta.domain || 'General';
        card.dataset.status = allPass ? 'PASS' : 'FAIL';
        card.dataset.text = (res.title + ' ' + (caseMeta.patient_markdown || '')).toLowerCase();

        card.innerHTML = `
          <div class="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-[#e1e8eb] gap-2">
            <div>
              <div class="flex items-center space-x-2">
                <span class="text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full badge-toolkit">${caseMeta.domain || 'General'}</span>
                <h3 class="font-bold text-[#1c2830] text-sm">${res.title}</h3>
              </div>
              <p class="text-xs text-[#778893] mt-0.5 font-mono">${res.id}</p>
            </div>
            <div class="flex items-center space-x-2">
              <span class="px-2.5 py-0.5 rounded-full text-xs font-bold ${sumPass ? 'badge-pass' : 'badge-fail'}">
                Sum: ${sumPass ? 'PASS' : 'FAIL'}
              </span>
              <span class="px-2.5 py-0.5 rounded-full text-xs font-bold ${ragPass ? 'badge-pass' : 'badge-fail'}">
                RAG: ${ragPass ? 'PASS' : 'FAIL'}
              </span>
            </div>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
            <!-- Summarization Check -->
            <div class="p-3.5 rounded-xl bg-[#f8faf9] border border-[#e1e8eb] space-y-2">
              <div class="flex items-center justify-between">
                <span class="font-bold text-[#1c2830] flex items-center space-x-1.5">
                  <i class="fa-solid fa-file-lines text-[#1f75a8]"></i>
                  <span>Pre-Visit Summary (${res.summarization?.metrics?.latency_s || '--'}s, ${res.summarization?.metrics?.tok_per_sec || '--'} t/s)</span>
                </span>
                <span class="text-[11px] text-[#778893] font-medium">${res.summarization?.output?.split(/\\s+/).length || 0} words</span>
              </div>
              <pre class="bg-[#111820] text-[#d6e2e9] border border-[#23313d] p-3 rounded-lg whitespace-pre-wrap max-h-40 overflow-y-auto custom-scroll">${escapeHtml(res.summarization?.output || 'No output')}</pre>
              ${res.summarization?.tier1_failures?.length ? `
                <div class="text-[#dc3e42] text-[11px] font-semibold space-y-0.5 pt-1">
                  ${res.summarization.tier1_failures.map(f => `<div><i class="fa-solid fa-triangle-exclamation mr-1"></i>${escapeHtml(f)}</div>`).join('')}
                </div>
              ` : '<div class="text-[#1ca564] text-[11px] font-semibold"><i class="fa-solid fa-check mr-1"></i>All Tier-1 format and entity checks passed</div>'}
            </div>

            <!-- Mini-RAG Protocol Check -->
            <div class="p-3.5 rounded-xl bg-[#f8faf9] border border-[#e1e8eb] space-y-2">
              <div class="flex items-center justify-between">
                <span class="font-bold text-[#1c2830] flex items-center space-x-1.5">
                  <i class="fa-solid fa-notes-medical text-[#7a4db8]"></i>
                  <span>Mini-RAG Protocol Counseling (${res.visit_prep_rag?.metrics?.latency_s || '--'}s)</span>
                </span>
                <span class="text-[11px] text-[#778893] font-medium">${res.visit_prep_rag?.output?.split(/\\s+/).length || 0} words</span>
              </div>
              <pre class="bg-[#111820] text-[#d6e2e9] border border-[#23313d] p-3 rounded-lg whitespace-pre-wrap max-h-40 overflow-y-auto custom-scroll">${escapeHtml(res.visit_prep_rag?.output || 'No output')}</pre>
              ${res.visit_prep_rag?.tier1_failures?.length ? `
                <div class="text-[#dc3e42] text-[11px] font-semibold space-y-0.5 pt-1">
                  ${res.visit_prep_rag.tier1_failures.map(f => `<div><i class="fa-solid fa-triangle-exclamation mr-1"></i>${escapeHtml(f)}</div>`).join('')}
                </div>
              ` : '<div class="text-[#1ca564] text-[11px] font-semibold"><i class="fa-solid fa-check mr-1"></i>All danger signs and guideline assertions preserved</div>'}
            </div>
          </div>
        `;
        container.appendChild(card);
      });
      filterExplorerCases();
    }

    function filterExplorerCases() {
      const search = (document.getElementById('explorer-search')?.value || '').toLowerCase();
      const domain = document.getElementById('explorer-domain-filter')?.value || 'ALL';
      const status = document.getElementById('explorer-status-filter')?.value || 'ALL';

      const cards = document.querySelectorAll('.explorer-case-card');
      let visible = 0;
      cards.forEach(c => {
        const matchesDomain = domain === 'ALL' || c.dataset.domain.toLowerCase().includes(domain.toLowerCase());
        const matchesStatus = status === 'ALL' || c.dataset.status === status;
        const matchesSearch = !search || c.dataset.text.includes(search);

        if (matchesDomain && matchesStatus && matchesSearch) {
          c.style.display = 'block';
          visible++;
        } else {
          c.style.display = 'none';
        }
      });
      document.getElementById('explorer-count-label').innerText = `Showing ${visible} of ${cards.length} cases`;
    }

    async function renderComparison() {
      const fileA = document.getElementById('comp-model-a')?.value;
      const fileB = document.getElementById('comp-model-b')?.value;
      const caseId = document.getElementById('comp-case-select')?.value;
      const container = document.getElementById('comp-results-view');
      if (!container || !fileA || !fileB || !caseId) return;

      const [runA, runB] = await Promise.all([
        fetch(`/api/runs/${fileA}`).then(r => r.json()),
        fetch(`/api/runs/${fileB}`).then(r => r.json())
      ]);

      const itemA = (runA.results || []).find(r => r.id === caseId) || {};
      const itemB = (runB.results || []).find(r => r.id === caseId) || {};

      container.innerHTML = `
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div class="ohs-card p-5 bg-white border border-[#e1e8eb] space-y-3 shadow-xs">
            <div class="flex items-center justify-between pb-2 border-b border-[#e1e8eb]">
              <span class="font-bold text-[#1ca564] text-sm flex items-center space-x-1.5">
                <i class="fa-solid fa-cube"></i><span>${runA.model}</span>
              </span>
              <span class="text-xs text-[#778893]">${itemA.summarization?.metrics?.tok_per_sec || '--'} t/s | ${itemA.summarization?.metrics?.latency_s || '--'}s</span>
            </div>
            <h4 class="text-xs font-bold text-[#1c2830]">Pre-Visit Summarization Check</h4>
            <pre class="bg-[#111820] text-[#d6e2e9] border border-[#23313d] p-3 rounded-lg text-xs whitespace-pre-wrap">${escapeHtml(itemA.summarization?.output || 'N/A')}</pre>
            <div class="text-xs">${itemA.summarization?.tier1_pass ? '<span class="badge-pass px-2.5 py-0.5 rounded-full font-bold">Tier-1 PASS</span>' : '<span class="badge-fail px-2.5 py-0.5 rounded-full font-bold">Tier-1 FAIL</span>: <span class="text-[#dc3e42] font-semibold">' + (itemA.summarization?.tier1_failures || []).join(', ') + '</span>'}</div>
          </div>

          <div class="ohs-card p-5 bg-white border border-[#e1e8eb] space-y-3 shadow-xs">
            <div class="flex items-center justify-between pb-2 border-b border-[#e1e8eb]">
              <span class="font-bold text-[#1f75a8] text-sm flex items-center space-x-1.5">
                <i class="fa-solid fa-cube"></i><span>${runB.model}</span>
              </span>
              <span class="text-xs text-[#778893]">${itemB.summarization?.metrics?.tok_per_sec || '--'} t/s | ${itemB.summarization?.metrics?.latency_s || '--'}s</span>
            </div>
            <h4 class="text-xs font-bold text-[#1c2830]">Pre-Visit Summarization Check</h4>
            <pre class="bg-[#111820] text-[#d6e2e9] border border-[#23313d] p-3 rounded-lg text-xs whitespace-pre-wrap">${escapeHtml(itemB.summarization?.output || 'N/A')}</pre>
            <div class="text-xs">${itemB.summarization?.tier1_pass ? '<span class="badge-pass px-2.5 py-0.5 rounded-full font-bold">Tier-1 PASS</span>' : '<span class="badge-fail px-2.5 py-0.5 rounded-full font-bold">Tier-1 FAIL</span>: <span class="text-[#dc3e42] font-semibold">' + (itemB.summarization?.tier1_failures || []).join(', ') + '</span>'}</div>
          </div>
        </div>
      `;
    }


    async function renderRlhfStudio() {
      const caseId = document.getElementById('rlhf-case-select')?.value;
      const task = document.getElementById('rlhf-task-select')?.value || 'summarization';
      if (!caseId || !runsList.length) return;

      const caseMeta = evalCases.find(c => c.id === caseId) || {};
      const runA_file = runsList[0].filename;
      const runB_file = runsList.length > 1 ? runsList[1].filename : runsList[0].filename;

      const [runA, runB] = await Promise.all([
        fetch(`/api/runs/${runA_file}`).then(r => r.json()),
        fetch(`/api/runs/${runB_file}`).then(r => r.json())
      ]);

      const itemA = (runA.results || []).find(r => r.id === caseId) || {};
      const itemB = (runB.results || []).find(r => r.id === caseId) || {};

      const outA = itemA[task]?.output || 'No output';
      const outB = itemB[task]?.output || 'No output';

      document.getElementById('rlhf-model-a-name').innerText = runA.model;
      document.getElementById('rlhf-model-b-name').innerText = runB.model;
      document.getElementById('rlhf-output-a').innerText = outA;
      document.getElementById('rlhf-output-b').innerText = outB;
      document.getElementById('rlhf-model-a-words').innerText = `${outA.split(/\\s+/).length} words`;
      document.getElementById('rlhf-model-b-words').innerText = `${outB.split(/\\s+/).length} words`;

      document.getElementById('rlhf-prompt-text').innerText = task === 'summarization' ? caseMeta.patient_markdown : `${caseMeta.patient_markdown}\\n\\n[Guideline]\\n${caseMeta.guideline_chunks}\\n\\n[Question]\\n${caseMeta.chw_question}`;
      document.getElementById('rlhf-gold-editor').value = outA;
      updateGoldWordCount();
    }

    function togglePromptCollapse() {
      const pre = document.getElementById('rlhf-prompt-text');
      if (pre) pre.classList.toggle('hidden');
    }

    function updateGoldWordCount() {
      const text = document.getElementById('rlhf-gold-editor')?.value || '';
      const words = text.trim() ? text.trim().split(/\\s+/).length : 0;
      const label = document.getElementById('gold-word-counter');
      if (label) {
        label.innerText = `${words} words`;
        label.className = words > 120 ? 'text-[11px] text-red-400 font-bold' : 'text-[11px] text-emerald-400 font-bold';
      }
    }

    async function submitPreferenceVote(chosenWinner) {
      const caseId = document.getElementById('rlhf-case-select')?.value;
      const task = document.getElementById('rlhf-task-select')?.value;
      const modelA = document.getElementById('rlhf-model-a-name')?.innerText;
      const modelB = document.getElementById('rlhf-model-b-name')?.innerText;
      const outA = document.getElementById('rlhf-output-a')?.innerText;
      const outB = document.getElementById('rlhf-output-b')?.innerText;
      const prompt = document.getElementById('rlhf-prompt-text')?.innerText;

      const checkedTags = Array.from(document.querySelectorAll('input[name="critique"]:checked')).map(el => el.value);

      const payload = {
        case_id: caseId,
        task: task,
        model_chosen: chosenWinner === 'A' ? modelA : modelB,
        model_rejected: chosenWinner === 'A' ? modelB : modelA,
        prompt: prompt,
        chosen: chosenWinner === 'A' ? outA : outB,
        rejected: chosenWinner === 'A' ? outB : outA,
        critique_tags: checkedTags,
        rationale: `Clinician manually preferred Candidate ${chosenWinner}.`
      };

      try {
        const res = await fetch('/api/preferences/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        alert(`Preference saved! Total curated pairs: ${data.count}`);
        loadPreferencesCount();
      } catch (e) {
        alert('Failed to save preference: ' + e);
      }
    }

    async function saveGoldAsSft() {
      const caseId = document.getElementById('rlhf-case-select')?.value;
      const task = document.getElementById('rlhf-task-select')?.value;
      const goldText = document.getElementById('rlhf-gold-editor')?.value;
      const prompt = document.getElementById('rlhf-prompt-text')?.innerText;

      if (!goldText) {
        alert('Please write or edit gold response before saving.');
        return;
      }

      try {
        const res = await fetch('/api/sft/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            case_id: caseId,
            task: task,
            instruction: task === 'summarization' ? 'Summarize patient record in 3 bullets under 120 words' : 'Provide grounded visit prep counseling under 130 words',
            input: prompt,
            output: goldText
          })
        });
        alert('Gold SFT demonstration saved to sft_clinical_data.jsonl!');
      } catch (e) {
        alert('Failed to save SFT demonstration: ' + e);
      }
    }

    async function autoBootstrapDpo() {
      if (runsList.length < 2) {
        alert('Auto-bootstrap requires at least 2 evaluated benchmark runs (e.g. Gemma 4 vs Gemma 2).');
        return;
      }
      const highRun = runsList.find(r => r.pass_rate_pct >= 80) || runsList[0];
      const lowRun = runsList.find(r => r.pass_rate_pct < 80) || runsList[runsList.length - 1];

      if (confirm(`Auto-bootstrap DPO preference pairs using ${highRun.model} as chosen and ${lowRun.model} as rejected?`)) {
        try {
          const res = await fetch('/api/preferences/auto-bootstrap', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              high_model_run: highRun.filename,
              low_model_run: lowRun.filename
            })
          });
          const data = await res.json();
          alert(data.message);
          loadPreferencesCount();
        } catch (e) {
          alert('Failed to auto-bootstrap: ' + e);
        }
      }
    }

    async function startEvaluationRun() {
      const model = document.getElementById('runner-model-input').value;
      const apiBase = document.getElementById('runner-apibase-input').value;
      const judgeModel = document.getElementById('runner-judge-select').value;
      const judgeKey = document.getElementById('runner-judgekey-input').value;
      const dryRun = document.getElementById('runner-dryrun-input').checked;

      const payload = {
        model: model,
        api_base: apiBase,
        judge_model: judgeModel,
        judge_api_key: judgeKey,
        dry_run: dryRun
      };

      try {
        const res = await fetch('/api/runner/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          document.getElementById('runner-logs').innerText = 'Starting evaluation run...\\n';
        } else {
          const err = await res.json();
          alert('Error: ' + err.error);
        }
      } catch (e) {
        alert('Failed to start run: ' + e);
      }
    }

    function startRunnerPolling() {
      if (pollInterval) clearInterval(pollInterval);
      pollInterval = setInterval(async () => {
        try {
          const res = await fetch('/api/runner/status');
          const data = await res.json();

          const dot = document.getElementById('runner-dot');
          const text = document.getElementById('runner-text');
          const logsEl = document.getElementById('runner-logs');

          if (data.is_running) {
            dot.className = 'w-2 h-2 rounded-full bg-[#7a4db8] animate-pulse';
            text.innerText = `Evaluating ${data.model}...`;
          } else if (data.status === 'completed') {
            dot.className = 'w-2 h-2 rounded-full bg-[#1ca564]';
            text.innerText = 'Run Completed';
          } else if (data.status === 'failed') {
            dot.className = 'w-2 h-2 rounded-full bg-[#dc3e42]';
            text.innerText = 'Run Failed';
          } else {
            dot.className = 'w-2 h-2 rounded-full bg-[#cbd7dc]';
            text.innerText = 'Runner Idle';
          }

          if (data.logs && logsEl) {
            logsEl.innerText = data.logs;
            logsEl.scrollTop = logsEl.scrollHeight;
          }
        } catch (e) {}
      }, 1500);
    }

    function switchTab(tabId) {
      currentTab = tabId;
      document.querySelectorAll('section').forEach(s => s.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('border-[#7a4db8]', 'text-[#7a4db8]', 'font-semibold');
        b.classList.add('border-transparent', 'text-[#4e5f6a]');
      });

      const activeView = document.getElementById(`view-${tabId}`);
      const activeTabBtn = document.getElementById(`tab-${tabId}`);
      if (activeView) activeView.classList.remove('hidden');
      if (activeTabBtn) {
        activeTabBtn.classList.remove('border-transparent', 'text-[#4e5f6a]');
        activeTabBtn.classList.add('border-[#7a4db8]', 'text-[#7a4db8]', 'font-semibold');
      }

      if (tabId === 'comparator') renderComparison();
      if (tabId === 'rlhf') renderRlhfStudio();
    }


    function refreshAll() {
      loadRuns();
      loadPreferencesCount();
    }

    function escapeHtml(str) {
      if (!str) return '';
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Auto-init on page load
    window.onload = init;
  </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="CHW Edge LLM Visual Evaluation & RLHF Studio")
    parser.add_argument("--port", type=int, default=8501, help="Port to serve the studio UI (default: 8501)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    args = parser.parse_args()

    # Pre-generate preference dataset if not present
    if not DPO_FILE.exists():
        DPO_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Empty initialization
        DPO_FILE.touch()

    handler = StudioApiHandler
    socketserver.TCPServer.allow_reuse_address = True

    target_port = args.port
    httpd = None

    for p in range(target_port, target_port + 20):
        try:
            httpd = socketserver.TCPServer((args.host, p), handler)
            target_port = p
            break
        except OSError as e:
            if e.errno == 48:  # Address already in use
                continue
            raise e

    if not httpd:
        print(f"Error: Could not bind to any port in range {args.port} - {args.port + 20}", file=sys.stderr)
        sys.exit(1)

    if target_port != args.port:
        print(f"\n[Notice] Port {args.port} was busy. Automatically switched to port {target_port}.")
        print(f"Tip: To free port {args.port}, run: lsof -ti :{args.port} | xargs kill -9 2>/dev/null")

    print("\n" + "=" * 80)
    print(f" Open Health Stack | Edge SLM Visual Evaluation & RLHF Studio")
    print(f" Studio Web Interface:  http://{args.host}:{target_port}")
    print(f" Active Dataset:        {EVAL_CASES_FILE}")
    print(f" DPO Export File:       {DPO_FILE}")
    print(f" SFT Export File:       {SFT_FILE}")
    print("=" * 80 + "\n")

    with httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Studio server...")


if __name__ == "__main__":
    main()

