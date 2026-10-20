#!/usr/bin/env python3
"""Interactive aCDU Clinical Simulator Web Application.
Zero-dependency Python HTTP server serving an interactive SPA that displays:
1. Clinical Scenario Explorer (from simple to complex: L1 -> L2 -> L3 -> L4)
2. FHIR PlanDefinitions with aCDU code mappings (with a to-do for full FHIRPath runner)
3. Live Interactive aCDU Editor with real-time Token Budgeting & Negative Boundary Linting
4. Triple-View Output Comparison:
   - Raw Baseline Unconstrained Output vs. aCDU-Clamped SLM Output
   - Before vs. After aCDU Tweak Diff
   - Live Model Selection & Simulation Execution
"""

import argparse
import http.server
import json
import os
import socketserver
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List

from data_adapter import load_all_scenarios, load_all_acdus
from lint_engine import lint_cdu
from inference_engine import (
    simulate_slm_synthesis,
    verify_output,
    get_cached_raw_output,
    assemble_prompt
)

PORT = 8520
ALL_SCENARIOS = load_all_scenarios()
ALL_ACDUS = load_all_acdus()
# In-memory working copies of aCDUs for live interactive tweaking
SESSION_ACDUS = {k: dict(v) for k, v in ALL_ACDUS.items()}

# Cache of previous simulation outputs for "Before vs After" tweak comparisons
PREVIOUS_RUNS = {}

class SimulatorHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = get_html_page()
            self.wfile.write(html.encode("utf-8"))
            return
            
        elif path == "/api/scenarios":
            self.send_json_response(ALL_SCENARIOS)
            return
            
        elif path == "/api/acdus":
            self.send_json_response(list(SESSION_ACDUS.values()))
            return
            
        elif path == "/api/cdu":
            query = urllib.parse.parse_qs(parsed.query)
            cdu_id = query.get("id", [""])[0]
            cdu = SESSION_ACDUS.get(cdu_id)
            if cdu:
                self.send_json_response(cdu)
            else:
                self.send_json_response({"error": "CDU not found"}, status=404)
            return

        elif path == "/api/health":
            self.send_json_response({"status": "ok", "scenarios": len(ALL_SCENARIOS), "acdus": len(SESSION_ACDUS)})
            return
            
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if path == "/api/lint":
            cdu = data.get("cdu", {})
            res = lint_cdu(cdu)
            self.send_json_response(res)
            return

        elif path == "/api/simulate":
            scenario_id = data.get("scenario_id", "")
            tweaked_cdu = data.get("tweaked_cdu")
            model = data.get("model", "gemma4-2b:latest")
            
            scenario = next((s for s in ALL_SCENARIOS if s["id"] == scenario_id), None)
            if not scenario:
                self.send_json_response({"error": "Scenario not found"}, status=404)
                return
                
            # If a tweaked CDU was supplied in the request, update in-memory session copy
            if tweaked_cdu and "id" in tweaked_cdu:
                SESSION_ACDUS[tweaked_cdu["id"]] = tweaked_cdu

            # Gather active CDUs for this scenario
            active_cdus = [SESSION_ACDUS[cid] for cid in scenario.get("expected_acdu_ids", []) if cid in SESSION_ACDUS]
            
            # 1. Raw Unconstrained Baseline Output
            raw_output = get_cached_raw_output(scenario_id, model=model)
            raw_verification = verify_output(raw_output, scenario)
            
            # 2. Run / Simulate SLM with active aCDUs
            slm_res = simulate_slm_synthesis(scenario, active_cdus, model=model)
            slm_verification = verify_output(slm_res["output"], scenario)
            
            # 3. Before vs After comparison
            prev_run = PREVIOUS_RUNS.get(scenario_id)
            PREVIOUS_RUNS[scenario_id] = {
                "output": slm_res["output"],
                "verification": slm_verification,
                "timestamp": slm_res.get("latency_s")
            }
            
            prompt_assembled = assemble_prompt(scenario, active_cdus)
            
            resp_payload = {
                "scenario_id": scenario_id,
                "model": model,
                "prompt_assembled": prompt_assembled,
                "raw_output": raw_output,
                "raw_verification": raw_verification,
                "slm_output": slm_res["output"],
                "slm_verification": slm_verification,
                "latency_s": slm_res.get("latency_s", 0.0),
                "source": slm_res.get("source", "deterministic"),
                "before_output": prev_run.get("output") if prev_run else None,
                "before_verification": prev_run.get("verification") if prev_run else None
            }
            self.send_json_response(resp_payload)
            return

        elif path == "/api/reset_cdu":
            cdu_id = data.get("id")
            if cdu_id and cdu_id in ALL_ACDUS:
                SESSION_ACDUS[cdu_id] = dict(ALL_ACDUS[cdu_id])
                self.send_json_response({"status": "reset", "cdu": SESSION_ACDUS[cdu_id]})
            else:
                self.send_json_response({"error": "CDU not found"}, status=404)
            return

        elif path == "/api/save_cdu":
            # Persists in-memory tweak permanently to disk (optional)
            cdu = data.get("cdu")
            if cdu and "id" in cdu:
                SESSION_ACDUS[cdu["id"]] = cdu
                ALL_ACDUS[cdu["id"]] = dict(cdu)
                self.send_json_response({"status": "saved", "id": cdu["id"]})
            else:
                self.send_json_response({"error": "Invalid CDU"}, status=400)
            return

        self.send_json_response({"error": "Endpoint not found"}, status=404)

    def send_json_response(self, data: Any, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

def get_html_page() -> str:
    # Read the SPA HTML file
    html_path = Path(__file__).resolve().parent / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>aCDU Simulator</h1>"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the aCDU Clinical Simulator")
    parser.add_argument("--port", type=int, default=8520, help="Port to bind (default: 8520)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface")
    args = parser.parse_args()

    # Re-use socket address to avoid port blocking on restart
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, args.port), SimulatorHandler) as httpd:
        print(f"🚀 aCDU Clinical Simulator running at http://{args.host}:{args.port}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down simulator server.")
