#!/usr/bin/env python3
"""3-Way Tokempic Benchmark:
  1. Original Standard Tokempic (with raw LOINC/SNOMED codes, no tasks view, no observations view, split BP)
  2. Optimized CHW Tokempic (chw-views: with tasks, observations, stripped numeric codes, unified BP, relative age)
  3. Raw HL7 FHIR JSON Bundle
"""

import datetime
import json
import time
import urllib.request
from pathlib import Path


OLLAMA_API_URL = "http://localhost:11434/api/chat"

# Original Tokempic representation (standard Tokempic defaults)
# - Raw LOINC/SNOMED codes included
# - No ## tasks section
# - No ## observations section (dipstick, RDT, MUAC missing)
# - Raw birthDate without relative age (e.g. no '(28y)', no '(16m)')
ORIGINAL_TOKEMPIC_CASES = {
    "case_01": {
        "title": "Fatima Bello (ANC 32w Pre-Eclampsia)",
        "markdown": (
            "## demographics\n"
            "Fatima Bello | 1998-04-12 | female | Koro Village\n\n"
            "## conditions\n"
            "77386006 | Pregnancy 32 weeks | active | 2026-03-01 |\n"
            "237602007 | Pregnancy-induced hypertension | active | 2026-09-15 |\n"
            "24831009 | Malaria falciparum | resolved | 2025-11-10 | 2025-11-20\n\n"
            "## vitals\n"
            "2026-09-15 | 85354-9 | Blood pressure | 8480-6: 126, 8462-4: 82 | N\n"
            "2026-10-14 | 85354-9 | Blood pressure | 8480-6: 148, 8462-4: 96 | H\n\n"
            "## medications\n"
            "310385 | Ferrous Sulfate 200mg | active | 2026-03-05 | 1 tab daily\n"
            "310156 | Folic Acid 5mg | active | 2026-03-05 | 1 tab daily"
        )
    },
    "case_07": {
        "title": "Kofi Mensah (iCCM 16m Faltering MUAC & Overdue MR2)",
        "markdown": (
            "## demographics\n"
            "Kofi Mensah | 2025-06-10 | male | Danfa Village\n\n"
            "## conditions\n"
            "235595009 | Acute gastroenteritis with mild dehydration | resolved | 2026-05-12 | 2026-05-17\n"
            "386507000 | Growth faltering / mild malnutrition | active | 2026-10-01 |\n\n"
            "## vitals\n"
            "2026-08-10 | 29463-7 | Body weight | 8.6 kg |\n"
            "2026-10-15 | 29463-7 | Body weight | 8.4 kg |"
        )
    },
    "case_08": {
        "title": "Zainab Umaru (iCCM 4y Severe Pneumonia)",
        "markdown": (
            "## demographics\n"
            "Zainab Umaru | 2022-08-01 | female | Sabon Gari\n\n"
            "## conditions\n"
            "233604007 | Severe pneumonia | active | 2026-10-18 |\n\n"
            "## vitals\n"
            "2026-10-18 | 9279-1 | Respiratory rate | 46 /min |\n"
            "2026-10-18 | 8310-5 | Body temperature | 38.2 Cel |"
        )
    }
}


def query_ollama(prompt: str, model: str = "gemma2:2b-instruct-q4_K_M"):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0, "seed": 42},
    }
    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - start

    eval_count = data.get("eval_count", 0)
    eval_duration_ns = data.get("eval_duration", 0)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    tok_per_sec = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns else 0.0

    return {
        "content": data.get("message", {}).get("content", "").strip(),
        "latency_s": round(elapsed, 3),
        "output_tokens": eval_count,
        "prompt_tokens": prompt_eval_count,
        "tok_per_sec": round(tok_per_sec, 1),
    }


def main():
    prompt_template = (
        "You are an offline assistant helping a Community Health Worker (CHW) review a patient's record before a household visit.\n"
        "Rules:\n"
        "1. Use ONLY the facts in the Patient Record below. Never invent vitals, dates, conditions, or medications.\n"
        "2. Clearly separate ACTIVE problems and OPEN/OVERDUE tasks from RESOLVED/COMPLETED history.\n"
        "3. Keep the summary under 120 words using exactly 3 bullet sections: **Patient & Context:**, **Recent Vitals & Findings:**, **Open Tasks & Due Items:**\n\n"
        "--- PATIENT RECORD ---\n"
        "{record}\n"
        "---"
    )

    results = {}
    print("=" * 80)
    print(" RUNNING 3-WAY EMPIRICAL COMPARISON: ORIGINAL TOKEMPIC")
    print("=" * 80)

    for cid, cdata in ORIGINAL_TOKEMPIC_CASES.items():
        print(f"\nRunning Original Tokempic on {cid}: {cdata['title']}...")
        p = prompt_template.format(record=cdata["markdown"])
        res = query_ollama(p)
        print(f"  -> Tokens: {res['prompt_tokens']} | Latency: {res['latency_s']}s")
        print(f"  -> Output:\n{res['content']}\n")
        results[cid] = {
            "title": cdata["title"],
            "prompt_tokens": res["prompt_tokens"],
            "latency_s": res["latency_s"],
            "chars": len(cdata["markdown"]),
            "output": res["content"]
        }

    with open("tokempic_3way_comparison_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Saved 3-way results to tokempic_3way_comparison_results.json")


if __name__ == "__main__":
    main()
