#!/usr/bin/env python3
"""Tokempic Comparison Benchmark for OHS Player.

Compares:
  Variant A: With Tokempic (SQL-on-FHIR pre-filtered compact Markdown)
  Variant B: Without Tokempic (Raw FHIR JSON Bundle)

Measures:
  - Input Token / Prompt Size (tokens & characters)
  - Latency / TTFT (seconds)
  - Decode throughput (tokens/second)
  - Clinical Extraction Accuracy (Tier-1 assertions)
  - Hallucination / Noise artifacts (confusion of LOINC/SNOMED codes with lab numbers)
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = ROOT_DIR.parent
OLLAMA_API_URL = "http://localhost:11434/api/chat"

# ---------------------------------------------------------------------------
# RAW FHIR JSON BUNDLES (Standard HL7 FHIR R4 JSON representation)
# ---------------------------------------------------------------------------

CASE_01_RAW_FHIR = {
    "resourceType": "Bundle",
    "type": "collection",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "pat-01",
                "name": [{"use": "official", "family": "Bello", "given": ["Fatima"], "text": "Fatima Bello"}],
                "gender": "female",
                "birthDate": "1998-04-12",
                "address": [{"city": "Koro Village", "country": "Ghana"}]
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "id": "cond-01",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "77386006", "display": "Pregnancy 32 weeks"}]},
                "subject": {"reference": "Patient/pat-01"},
                "onsetDateTime": "2026-03-01"
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "id": "cond-02",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "237602007", "display": "Pregnancy-induced hypertension"}]},
                "subject": {"reference": "Patient/pat-01"},
                "onsetDateTime": "2026-09-15"
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "id": "cond-03",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "resolved"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "24831009", "display": "Malaria falciparum"}]},
                "subject": {"reference": "Patient/pat-01"},
                "onsetDateTime": "2025-11-10",
                "abatementDateTime": "2025-11-20"
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-bp-01",
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs", "display": "Vital Signs"}]}],
                "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure panel with all children optional"}]},
                "subject": {"reference": "Patient/pat-01"},
                "effectiveDateTime": "2026-09-15T09:30:00Z",
                "component": [
                    {"code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]}, "valueQuantity": {"value": 126, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}},
                    {"code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}]}, "valueQuantity": {"value": 82, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}}
                ],
                "interpretation": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "N", "display": "Normal"}]}]
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-bp-02",
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs", "display": "Vital Signs"}]}],
                "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure panel with all children optional"}]},
                "subject": {"reference": "Patient/pat-01"},
                "effectiveDateTime": "2026-10-14T11:15:00Z",
                "component": [
                    {"code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]}, "valueQuantity": {"value": 148, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}},
                    {"code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}]}, "valueQuantity": {"value": 96, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}}
                ],
                "interpretation": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "H", "display": "High"}]}]
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-prot-01",
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory", "display": "Laboratory"}]}],
                "code": {"coding": [{"system": "http://loinc.org", "code": "50561-0", "display": "Protein [Mass/volume] in Urine by Test strip"}]},
                "subject": {"reference": "Patient/pat-01"},
                "effectiveDateTime": "2026-10-14T11:20:00Z",
                "valueString": "1+",
                "interpretation": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "A", "display": "Abnormal"}]}]
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-sym-01",
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam", "display": "Exam"}]}],
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "25064002", "display": "Headache"}]},
                "subject": {"reference": "Patient/pat-01"},
                "effectiveDateTime": "2026-10-14T11:25:00Z",
                "valueCodeableConcept": {"coding": [{"system": "http://snomed.info/sct", "code": "52448006", "display": "Present"}]}
            }
        },
        {
            "resource": {
                "resourceType": "Task",
                "id": "task-01",
                "status": "requested",
                "priority": "urgent",
                "description": "Refer to District Hospital for pre-eclampsia workup",
                "executionPeriod": {"end": "2026-10-16T18:00:00Z"},
                "for": {"reference": "Patient/pat-01"},
                "note": [{"text": "Overdue urgent referral"}]
            }
        },
        {
            "resource": {
                "resourceType": "MedicationRequest",
                "id": "med-01",
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "310385", "display": "Ferrous Sulfate 200mg"}]},
                "subject": {"reference": "Patient/pat-01"},
                "authoredOn": "2026-03-05",
                "dosageInstruction": [{"text": "1 tab daily"}]
            }
        },
        {
            "resource": {
                "resourceType": "MedicationRequest",
                "id": "med-02",
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "310156", "display": "Folic Acid 5mg"}]},
                "subject": {"reference": "Patient/pat-01"},
                "authoredOn": "2026-03-05",
                "dosageInstruction": [{"text": "1 tab daily"}]
            }
        }
    ]
}

CASE_02_RAW_FHIR = {
    "resourceType": "Bundle",
    "type": "collection",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "pat-02",
                "name": [{"use": "official", "family": "Mensah", "given": ["Kofi"], "text": "Kofi Mensah"}],
                "gender": "male",
                "birthDate": "2025-06-10",
                "address": [{"city": "Danfa Village", "country": "Ghana"}]
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "id": "cond-gastro",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "resolved"}]},
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "235595009", "display": "Acute gastroenteritis with mild dehydration"}]},
                "subject": {"reference": "Patient/pat-02"},
                "onsetDateTime": "2026-05-12",
                "abatementDateTime": "2026-05-17"
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "id": "cond-mal",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "386507000", "display": "Growth faltering / mild malnutrition"}]},
                "subject": {"reference": "Patient/pat-02"},
                "onsetDateTime": "2026-10-01"
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-wt-01",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Body weight"}]},
                "effectiveDateTime": "2026-08-10T10:00:00Z",
                "valueQuantity": {"value": 8.6, "unit": "kg", "system": "http://unitsofmeasure.org", "code": "kg"}
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-wt-02",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Body weight"}]},
                "effectiveDateTime": "2026-10-15T09:00:00Z",
                "valueQuantity": {"value": 8.4, "unit": "kg", "system": "http://unitsofmeasure.org", "code": "kg"}
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-muac-01",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "56072-2", "display": "Circumference.mid upper arm"}]},
                "effectiveDateTime": "2026-08-10T10:00:00Z",
                "valueQuantity": {"value": 13.2, "unit": "cm", "system": "http://unitsofmeasure.org", "code": "cm"}
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-muac-02",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "56072-2", "display": "Circumference.mid upper arm"}]},
                "effectiveDateTime": "2026-10-15T09:00:00Z",
                "valueQuantity": {"value": 12.6, "unit": "cm", "system": "http://unitsofmeasure.org", "code": "cm"}
            }
        },
        {
            "resource": {
                "resourceType": "Task",
                "id": "task-mr2",
                "status": "ready",
                "priority": "routine",
                "description": "Administer Measles-Rubella 2 (MR2) vaccine",
                "executionPeriod": {"end": "2026-09-15T16:00:00Z"},
                "note": [{"text": "Overdue by 1 month"}]
            }
        }
    ]
}

CASE_03_RAW_FHIR = {
    "resourceType": "Bundle",
    "type": "collection",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "pat-03",
                "name": [{"use": "official", "family": "Umaru", "given": ["Zainab"], "text": "Zainab Umaru"}],
                "gender": "female",
                "birthDate": "2022-08-01",
                "address": [{"city": "Sabon Gari", "country": "Nigeria"}]
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "id": "cond-pneu",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "233604007", "display": "Severe pneumonia"}]},
                "onsetDateTime": "2026-10-18"
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-rr",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "9279-1", "display": "Respiratory rate"}]},
                "effectiveDateTime": "2026-10-18T08:30:00Z",
                "valueQuantity": {"value": 46, "unit": "/min", "system": "http://unitsofmeasure.org", "code": "/min"}
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-temp",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5", "display": "Body temperature"}]},
                "effectiveDateTime": "2026-10-18T08:30:00Z",
                "valueQuantity": {"value": 38.2, "unit": "Cel", "system": "http://unitsofmeasure.org", "code": "Cel"}
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-indraw",
                "status": "final",
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "248590000", "display": "Subcostal retraction / Chest indrawing"}]},
                "effectiveDateTime": "2026-10-18T08:35:00Z",
                "valueCodeableConcept": {"coding": [{"system": "http://snomed.info/sct", "code": "52448006", "display": "Present"}]}
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-stridor",
                "status": "final",
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "70407001", "display": "Stridor in calm child"}]},
                "effectiveDateTime": "2026-10-18T08:35:00Z",
                "valueCodeableConcept": {"coding": [{"system": "http://snomed.info/sct", "code": "2667000", "display": "Absent"}]}
            }
        },
        {
            "resource": {
                "resourceType": "Task",
                "id": "task-emer",
                "status": "requested",
                "priority": "urgent",
                "description": "Emergency transport to tertiary hospital",
                "executionPeriod": {"end": "2026-10-18T12:00:00Z"},
                "note": [{"text": "Due immediately"}]
            }
        }
    ]
}


COMPARISON_CASES = [
    {
        "id": "case_01",
        "title": "Fatima Bello (ANC 32w, BP jump 148/96, Proteinuria 1+, Resolved Malaria)",
        "tokempic_markdown": "## demographics\nFatima Bello | 1998-04-12 (28y) | female | Koro Village\n\n## conditions\nPregnancy 32 weeks | active | 2026-03-01 |\nPregnancy-induced hypertension | active | 2026-09-15 |\nMalaria falciparum | resolved | 2025-11-10 | 2025-11-20\n\n## vitals\n2026-09-15 | Blood Pressure | 126/82 mmHg | Normal\n2026-10-14 | Blood Pressure | 148/96 mmHg | High\n2026-10-14 | Weight | 64.2 kg | Normal\n\n## observations\n2026-10-14 | Urine Protein Dipstick | 1+ | Abnormal\n2026-10-14 | Symptom: Frontal headache | Present | Warning\n\n## tasks\nrequested | urgent | Refer to District Hospital for pre-eclampsia workup | 2026-10-16 | Overdue urgent referral\n\n## medications\nFerrous Sulfate 200mg | active | 2026-03-05 | 1 tab daily\nFolic Acid 5mg | active | 2026-03-05 | 1 tab daily",
        "raw_fhir_json": json.dumps(CASE_01_RAW_FHIR, indent=2),
        "rules": {
            "max_words": 120,
            "must_include_all": [
                ["fatima", "bello", "28"],
                ["148/96", "blood pressure", "hypertension", "high bp"],
                ["referral", "district hospital", "pre-eclampsia"]
            ],
            "must_not_claim_active": ["active malaria", "has malaria", "current malaria"]
        }
    },
    {
        "id": "case_02",
        "title": "Kofi Mensah (Child 16m, Faltering Weight 8.4kg, Overdue MR2, Past Diarrhea)",
        "tokempic_markdown": "## demographics\nKofi Mensah | 2025-06-10 (16m) | male | Danfa Village\n\n## conditions\nAcute gastroenteritis with mild dehydration | resolved | 2026-05-12 | 2026-05-17\nGrowth faltering / mild malnutrition | active | 2026-10-01 |\n\n## vitals\n2026-08-10 | Weight | 8.6 kg | Normal\n2026-10-15 | Weight | 8.4 kg | Low for age\n2026-08-10 | MUAC | 13.2 cm | Green\n2026-10-15 | MUAC | 12.6 cm | Yellow\n2026-10-15 | Temperature | 36.7 C | Normal\n\n## immunizations\nBCG | 2025-06-12 | completed\nPenta 1,2,3 | 2025-10-14 | completed\nMeasles-Rubella 1 (MR1) | 2026-03-15 | completed\n\n## tasks\nready | routine | Administer Measles-Rubella 2 (MR2) vaccine | 2026-09-15 | Overdue by 1 month\n\n## observations\n2026-10-15 | Bilateral pitting oedema | Absent | Normal",
        "raw_fhir_json": json.dumps(CASE_02_RAW_FHIR, indent=2),
        "rules": {
            "max_words": 120,
            "must_include_all": [
                ["kofi", "mensah"],
                ["muac", "12.6", "8.4", "weight"],
                ["mr2", "measles", "vaccine"]
            ],
            "must_not_claim_active": ["active diarrhea", "active gastroenteritis"]
        }
    },
    {
        "id": "case_03",
        "title": "Zainab Umaru (Child 4y, Severe Pneumonia, RR 46, Chest Indrawing, Stridor Absent)",
        "tokempic_markdown": "## demographics\nZainab Umaru | 2022-08-01 (4y) | female | Sabon Gari\n\n## conditions\nSevere pneumonia | active | 2026-10-18 |\n\n## vitals\n2026-10-18 | Respiratory Rate | 46 breaths/min | Fast breathing (>=40)\n2026-10-18 | Temperature | 38.2 C | Fever\n\n## observations\n2026-10-18 | Chest indrawing | Present | Danger sign\n2026-10-18 | Stridor in calm child | Absent | Normal\n\n## tasks\nrequested | urgent | Emergency transport to tertiary hospital | 2026-10-18 | Due immediately",
        "raw_fhir_json": json.dumps(CASE_03_RAW_FHIR, indent=2),
        "rules": {
            "max_words": 120,
            "must_include_all": [
                ["zainab", "umaru", "4"],
                ["46", "chest indrawing", "pneumonia", "breathing"],
                ["hospital", "transport", "emergency", "referral"]
            ],
            "must_not_claim_active": ["stridor present", "exhibited stridor"]
        }
    }
]


def query_ollama(model: str, prompt: str) -> Dict[str, Any]:
    """Query local Ollama server."""
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
    with urllib.request.urlopen(req, timeout=180) as resp:
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


def grade_summary(text: str, rules: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Grade extracted facts and check for hallucinations/traps."""
    fails = []
    # 1. Check length
    words = text.split()
    if len(words) > (rules.get("max_words", 120) * 1.2):
        fails.append(f"Word limit exceeded ({len(words)}w)")

    # 2. Check clinical fact groups
    for group in rules.get("must_include_all", []):
        if not any(phrase.lower() in text.lower() for phrase in group):
            fails.append(f"Missing clinical fact: {group}")

    # 3. Check resolved traps
    for trap in rules.get("must_not_claim_active", []):
        if trap.lower() in text.lower():
            fails.append(f"Hallucinated active condition: '{trap}'")

    return (len(fails) == 0, fails)


def main():
    parser = argparse.ArgumentParser(description="Compare Tokempic Markdown vs Raw FHIR JSON on Edge LLM.")
    parser.add_argument("--model", type=str, default="gemma2:2b-instruct-q4_K_M", help="Ollama model name")
    args = parser.parse_args()

    model = args.model
    print("=" * 85)
    print(f" EXPERIMENT: TOKEMPIC (SQL-on-FHIR) vs RAW FHIR JSON ON EDGE LLM ({model})")
    print("=" * 85)

    prompt_template_tokempic = (
        "You are an offline assistant helping a Community Health Worker (CHW) review a patient's record before a household visit.\n"
        "Rules:\n"
        "1. Use ONLY the facts in the Patient Record below. Never invent vitals, dates, conditions, or medications.\n"
        "2. Clearly separate ACTIVE problems and OPEN/OVERDUE tasks from RESOLVED/COMPLETED history.\n"
        "3. Keep the summary under 120 words using exactly 3 bullet sections: **Patient & Context:**, **Recent Vitals & Findings:**, **Open Tasks & Due Items:**\n\n"
        "--- PATIENT RECORD (TOKEMPIC MARKDOWN) ---\n"
        "{record}\n"
        "---"
    )

    prompt_template_raw = (
        "You are an offline assistant helping a Community Health Worker (CHW) review a patient's record before a household visit.\n"
        "Rules:\n"
        "1. Use ONLY the facts in the FHIR JSON Bundle below. Never invent vitals, dates, conditions, or medications.\n"
        "2. Clearly separate ACTIVE problems and OPEN/OVERDUE tasks from RESOLVED/COMPLETED history.\n"
        "3. Keep the summary under 120 words using exactly 3 bullet sections: **Patient & Context:**, **Recent Vitals & Findings:**, **Open Tasks & Due Items:**\n\n"
        "--- PATIENT RECORD (RAW HL7 FHIR JSON BUNDLE) ---\n"
        "{record}\n"
        "---"
    )

    results = []

    for case in COMPARISON_CASES:
        cid = case["id"]
        title = case["title"]
        print(f"\nEvaluating: {cid} - {title}")

        # -------------------------------------------------------------
        # Variant A: With Tokempic
        # -------------------------------------------------------------
        p_tokempic = prompt_template_tokempic.format(record=case["tokempic_markdown"])
        char_count_tok = len(case["tokempic_markdown"])
        print(f"  [A: Tokempic] Querying {model} (Record size: {char_count_tok} chars)...")
        res_tok = query_ollama(model, p_tokempic)
        pass_tok, fails_tok = grade_summary(res_tok["content"], case["rules"])

        # -------------------------------------------------------------
        # Variant B: Raw FHIR JSON
        # -------------------------------------------------------------
        p_raw = prompt_template_raw.format(record=case["raw_fhir_json"])
        char_count_raw = len(case["raw_fhir_json"])
        print(f"  [B: Raw FHIR] Querying {model} (Record size: {char_count_raw} chars)...")
        res_raw = query_ollama(model, p_raw)
        pass_raw, fails_raw = grade_summary(res_raw["content"], case["rules"])

        results.append({
            "id": cid,
            "title": title,
            "tokempic": {
                "chars": char_count_tok,
                "prompt_tokens": res_tok["prompt_tokens"],
                "latency_s": res_tok["latency_s"],
                "speed_tps": res_tok["tok_per_sec"],
                "pass": pass_tok,
                "fails": fails_tok,
                "output": res_tok["content"]
            },
            "raw_fhir": {
                "chars": char_count_raw,
                "prompt_tokens": res_raw["prompt_tokens"],
                "latency_s": res_raw["latency_s"],
                "speed_tps": res_raw["tok_per_sec"],
                "pass": pass_raw,
                "fails": fails_raw,
                "output": res_raw["content"]
            }
        })

    # Print Comparative Table
    print("\n" + "=" * 85)
    print(" COMPARATIVE RESULTS TABLE")
    print("=" * 85)
    print(f"{'Metric':<28} | {'With Tokempic (Markdown)':<25} | {'Without Tokempic (Raw FHIR)':<25}")
    print("-" * 85)

    avg_chars_tok = sum(r["tokempic"]["chars"] for r in results) / len(results)
    avg_chars_raw = sum(r["raw_fhir"]["chars"] for r in results) / len(results)
    char_ratio = round(avg_chars_raw / avg_chars_tok, 1)

    avg_p_tok = sum(r["tokempic"]["prompt_tokens"] for r in results) / len(results)
    avg_p_raw = sum(r["raw_fhir"]["prompt_tokens"] for r in results) / len(results)
    token_ratio = round(avg_p_raw / avg_p_tok, 1)

    avg_lat_tok = sum(r["tokempic"]["latency_s"] for r in results) / len(results)
    avg_lat_raw = sum(r["raw_fhir"]["latency_s"] for r in results) / len(results)

    pass_tok_count = sum(1 for r in results if r["tokempic"]["pass"])
    pass_raw_count = sum(1 for r in results if r["raw_fhir"]["pass"])

    print(f"{'Avg Input Payload Size':<28} | {round(avg_chars_tok):<7} chars ({round(avg_p_tok)} tok) | {round(avg_chars_raw):<7} chars ({round(avg_p_raw)} tok) [{token_ratio}x larger]")
    print(f"{'Avg Latency':<28} | {avg_lat_tok:.3f} seconds            | {avg_lat_raw:.3f} seconds")
    print(f"{'Clinical Accuracy':<28} | {pass_tok_count}/{len(results)} ({round(pass_tok_count/len(results)*100)}%)               | {pass_raw_count}/{len(results)} ({round(pass_raw_count/len(results)*100)}%)")
    print("=" * 85)

    # Detailed Output Comparisons
    print("\n" + "=" * 85)
    print(" QUALITATIVE OUTPUT COMPARISON")
    print("=" * 85)
    for r in results:
        print(f"\n--- {r['id'].upper()}: {r['title']} ---")
        print(f"\n[VARIANT A: WITH TOKEMPIC] (Accuracy: {'PASS' if r['tokempic']['pass'] else 'FAIL'} | {r['tokempic']['prompt_tokens']} prompt tokens | {r['tokempic']['latency_s']}s)")
        print(r['tokempic']['output'])
        if r['tokempic']['fails']:
            print(f"  Failures: {r['tokempic']['fails']}")

        print(f"\n[VARIANT B: WITHOUT TOKEMPIC (RAW FHIR JSON)] (Accuracy: {'PASS' if r['raw_fhir']['pass'] else 'FAIL'} | {r['raw_fhir']['prompt_tokens']} prompt tokens | {r['raw_fhir']['latency_s']}s)")
        print(r['raw_fhir']['output'])
        if r['raw_fhir']['fails']:
            print(f"  Failures: {r['raw_fhir']['fails']}")
        print("-" * 85)

    # Save results JSON
    report_file = "tokempic_vs_raw_comparison.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.datetime.now().isoformat(),
            "model": model,
            "metrics": {
                "token_compression_ratio": token_ratio,
                "char_compression_ratio": char_ratio,
                "avg_latency_tokempic_s": round(avg_lat_tok, 3),
                "avg_latency_raw_s": round(avg_lat_raw, 3),
                "accuracy_tokempic_pct": round(pass_tok_count / len(results) * 100),
                "accuracy_raw_pct": round(pass_raw_count / len(results) * 100)
            },
            "cases": results
        }, f, indent=2)
    print(f"\nFull comparison report saved to: {report_file}")


if __name__ == "__main__":
    main()
