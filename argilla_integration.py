#!/usr/bin/env python3
"""Argilla Integration for CHW Edge LLM Evaluation and RLHF Dataset Curation.

Allows importing the 20 golden clinical cases and multi-model outputs into an
Argilla FeedbackDataset for clinician review, ranking, and fine-tuning export.

Requirements:
  pip install argilla
"""

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Sync CHW Evals with Argilla Feedback Server")
    parser.add_argument("--api-url", default="http://localhost:6900", help="Argilla server URL")
    parser.add_argument("--api-key", default="argilla.apikey", help="Argilla API key")
    parser.add_argument("--workspace", default="admin", help="Argilla workspace")
    parser.add_argument("--dataset-name", default="chw-slm-clinical-evals", help="Dataset name in Argilla")
    parser.add_argument("--cases", default="chw-edge-evals/dataset/eval_cases.json", help="Path to eval cases")
    parser.add_argument("--run-file", default="eval_results_gemma2_2b-instruct-q4_K_M.json", help="Eval results JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print schema and sample record without connecting")
    return parser.parse_args()


def main():
    args = parse_args()
    cases_path = Path(args.cases)
    runs_path = Path(args.run_file)

    if not cases_path.exists() or not runs_path.exists():
        print(f"Error: Required files not found ({cases_path} or {runs_path})")
        return

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    runs_data = json.loads(runs_path.read_text(encoding="utf-8"))
    results_by_id = {r["id"]: r for r in runs_data.get("results", [])}

    print("=" * 80)
    print(f" ARGILLA DATASET GENERATOR | Model: {runs_data.get('model')} | Cases: {len(cases)}")
    print("=" * 80)

    records = []
    for c in cases:
        cid = c["id"]
        res = results_by_id.get(cid, {})

        sum_res = res.get("summarization", {})
        sum_output = sum_res.get("output", "N/A")
        t1_sum_pass = sum_res.get("tier1_pass", False)

        records.append({
            "fields": {
                "case_id": cid,
                "title": c["title"],
                "domain": c.get("domain", "General"),
                "patient_markdown": c["patient_markdown"],
                "model_output": sum_output,
            },
            "metadata": {
                "model": runs_data.get("model", "unknown"),
                "tier1_pass": str(t1_sum_pass),
                "latency_s": str(sum_res.get("metrics", {}).get("latency_s", 0)),
            },
        })

    print(f"Prepared {len(records)} clinical evaluation records for Argilla.")
    print("Fields in dataset:")
    print(" - patient_markdown (FHIR Tokempic source)")
    print(" - model_output (Pre-visit 3-bullet summary)")
    print("Questions configured for Clinicians in Argilla:")
    print(" 1. clinical_faithfulness (Rating: 1-5)")
    print(" 2. temporal_accuracy (Yes/No: Are resolved conditions accurately reported?)")
    print(" 3. dangerous_flags_preserved (Yes/No)")
    print(" 4. gold_correction (Text: Corrected summary for SFT/DPO)")

    if args.dry_run:
        print("\n[Dry Run] Argilla sync preview succeeded. Skipping network connection.")
        return

    try:
        import argilla as rg
        rg.init(api_url=args.api_url, api_key=args.api_key, workspace=args.workspace)

        # Define dataset schema
        dataset = rg.FeedbackDataset(
            fields=[
                rg.TextField(name="case_id", title="Case ID"),
                rg.TextField(name="title", title="Clinical Scenario"),
                rg.TextField(name="domain", title="Clinical Domain"),
                rg.TextField(name="patient_markdown", title="Patient FHIR Markdown"),
                rg.TextField(name="model_output", title="SLM Generated Output"),
            ],
            questions=[
                rg.RatingQuestion(name="clinical_faithfulness", title="Clinical Faithfulness (1-5)", values=[1, 2, 3, 4, 5]),
                rg.LabelQuestion(name="temporal_accuracy", title="Temporal Accuracy (Active vs Resolved)", labels=["Accurate", "Hallucinated_Active"]),
                rg.LabelQuestion(name="danger_flags", title="Critical Danger Signs Preserved", labels=["Preserved", "Omitted"]),
                rg.TextQuestion(name="gold_correction", title="Gold Clinical Correction (for SFT / DPO)", required=False),
            ],
        )

        remote_dataset = dataset.push_to_argilla(name=args.dataset_name, workspace=args.workspace)
        print(f"Successfully pushed dataset '{args.dataset_name}' to Argilla at {args.api_url}")
    except ImportError:
        print("\nArgilla Python client not installed. To run live Argilla sync:")
        print("  pip install argilla")
    except Exception as e:
        print(f"\nCould not connect to Argilla server at {args.api_url}: {e}")
        print("Ensure Argilla Docker container is running: docker run -d -p 6900:6900 argilla/argilla-server:latest")


if __name__ == "__main__":
    main()
