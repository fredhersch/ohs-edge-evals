# CHW & FHW Edge SLM Evaluation Framework — Implementation Tracker

**Package Location:** [`//depot/google3/experimental/users/fredhersch/chw_edge_evals/`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/)  
**Architecture Plan:** [`docs/slm_chw_evals_framework_plan.md`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/docs/slm_chw_evals_framework_plan.md)  
**Tech Lead Handoff Target:** Ali Afshar (`afshar@google.com`, Director, Engineering — Core GDI)  
**Last Updated:** 2026-10-21

> [!IMPORTANT]
> **Phase 1 Status: COMPLETE & VERIFIED (`blaze test` Passing)**
> All Phase 1 deliverables have been implemented, audited against [`baseline_gemma4_2b_run.json`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/packs/baseline_gemma4_2b_run.json), and verified via `/google/bin/releases/arca9-local-blaze-cli/blaze-for-agents test //experimental/users/fredhersch/chw_edge_evals:chw_edge_evals_test`.

## 1. Phase-by-Phase Execution Roadmap & Status

| Phase | Milestone / Deliverable | Target Files in `chw_edge_evals/` | Status | Empirical Verification / Gate |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1.1** | **Google3 Package & MedGemma `EvalBase` Adapter** | [`BUILD`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/BUILD), [`README.md`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/README.md), [`core/eval_contract.py`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/core/eval_contract.py) | **DONE** | Implements `load_and_prep_data`, `post_process_and_score_answers`, `compute_aggregated_metrics` + exports `test_results.tsv` & `test_metrics.json`. |
| **Phase 1.2** | **SQL-on-FHIR Views + Markdown Template Renderer** *(Replaces `Tokempic`)* | [`core/sql_on_fhir_renderer.py`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/core/sql_on_fhir_renderer.py), [`packs/sql_on_fhir_views/`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/packs/sql_on_fhir_views/) | **DONE** | Projects HL7 FHIR R4 bundles via SQL-on-FHIR views into compact Markdown templates (~$3.1\times$ token compression, relative age, unified BP, active vs. resolved separation). |
| **Phase 1.3** | **Upgraded Tier-1 Clinical AST & Synonym Scorer** | [`core/ast_clinical_scorer.py`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/core/ast_clinical_scorer.py) | **DONE** | Rescues all **4/4 false-negative cases** (`VIG-ECHIS-L2-005`, `L2-009`, `L3-001`, `L3-004`) on `Gemma 4 2B`: strict pass rate rises from **80.0% (24/30)** $\to$ **93.3% (28/30)** (**96.7% / 29/30** with 2-word soft budget margin), while keeping genuine vaccine omission `VIG-ECHIS-L1-006` flagged. |
| **Phase 1.4** | **Zero-RAM SQLite FTS5 `aCDU` Gatekeeper & Deontic Resolver** | [`core/acdu_retriever.py`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/core/acdu_retriever.py), [`runners/run_acdu_systematic_ablations.py`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/runners/run_acdu_systematic_ablations.py) | **DONE** | Supports 5-axis systematic ablations (`-Cohort C`, `-Negative Set N`, `-Deontic Resolver`, `-Compression M`, `+Swahili Synonym Trigger Map` achieving **100% Swahili query recall**). |
| **Phase 1.5** | **Tier-2 Gemini 4 Judge & 100-Case Judge Calibration Set** | [`core/gemini4_judge.py`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/core/gemini4_judge.py), [`gold/build_judge_calibration.py`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/gold/build_judge_calibration.py), [`gold/judge_calibration_100.json`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/gold/judge_calibration_100.json) | **DONE** | Curated **100-case calibration set** (50 seeded clinical faults + 50 real SLM outputs). Verified **100% sensitivity** ($\ge 98\%$ gate) and **$\kappa = 1.0$** ($\ge 0.85$ gate). |
| **Phase 1.6** | **Modular Vibe-Eval Pack Registry & Runner (`PACK-01`..`PACK-03`)** | [`packs/pack_registry.json`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/packs/pack_registry.json), [`runners/run_vibe_evals.py`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/runners/run_vibe_evals.py) | **DONE** | `PACK-01` (20 cases), `PACK-02` (20 cases), `PACK-03` (10 cases) ready and tested via `ChwVibeEvalRunner`. |
| **Phase 2.1** | **Gemini 4 Contextual Synthesis for `PACK-04`..`PACK-06`** | [`synthesis/locales/kenya_echis.yaml`](file:///google/src/cloud/fredhersch/slm_chw_evals_plan/google3/experimental/users/fredhersch/chw_edge_evals/synthesis/locales/kenya_echis.yaml), `synthesis/synthesize_contextual_cases.py` | **NEXT** | Generate 15 cases each for `PACK-04` (Household Risk-Stacking $k=2..6$), `PACK-05` (Visit Planning & Stockouts), and `PACK-06` (CHW Micro-Learning). |
| **Phase 2.2** | **Full 5-Experiment `aCDU` Matrix Sweep Across SLM Variations** | `runners/run_acdu_systematic_ablations.py` | **NEXT** | Benchmark `Gemma 4 2B`, `MedGemma 2.0 E4B / 1GB`, and `MedGemma2-LR` across Exp 1–Exp 5. |
| **Phase 3.1** | **Stage 1 Gold Benchmark Dual-Clinician Audit (\$50k OpEx)** | `gold/` | **PLANNED** | 500 Gemini-4 candidates audited by 2 independent LRE clinicians (PATH) + Senior Adjudicator $\to$ lock **350 Certified Stage 1 Gold Cases** + **500 ORPO pairs**. |
| **Phase 3.2** | **Stage 2 Vision Dataset Catalog & Stage 3 Audio Partner Evals (P2)** | `packs/pack_registry.json` (`PACK-07`, `PACK-08`) | **PLANNED (P1/P2)** | Catalog open/partner RDT & LCD OCR sets (`PACK-07`); contract with **PATH / Digital Umuganda** + **Google Research** for Kinyarwanda/Swahili audio evals (`PACK-08`). |

## 2. Phase 1 Empirical Verification Results

### A. Gemma 4 2B Audit: Flat Regex vs. Upgraded Clinical AST Scorer (`PACK-02` + `PACK-03`)

| Case ID | Scenario | Legacy Flat Regex Result | Upgraded AST + Synonym Scorer Result | Root Cause Fixed |
| :--- | :--- | :--- | :--- | :--- |
| **`VIG-ECHIS-L2-005`** | Neonatal Sepsis & Hypothermia | **FAIL** (`50.0%`) | **PASS** (`100.0%`) | Normalized *"Do not **administer** oral antibiotics"* $\equiv$ *"do not **give** oral"* + recognized KMC/NBU neonatal sepsis triad. |
| **`VIG-ECHIS-L2-009`** | Severe Puerperal Sepsis | **FAIL** (`50.0%`) | **PASS** (`100.0%`) | Propagated Markdown `**DO NOT:**` section header to child bullet (`* Douche, wash inside vagina...`) + singular/plural `IV antibiotic(s)`. |
| **`VIG-ECHIS-L3-001`** | Oxytocic Herbs (`Kaloba`) in Labor | **FAIL** (`66.7%`) | **PASS** (`100.0%`) | Normalized *"Firmly **refuse** to administer or allow"* $\equiv$ *"do not allow / forbid"*. |
| **`VIG-ECHIS-L3-004`** | Home Nifedipine in Pre-Eclampsia | **FAIL** (`66.7%`) | **PASS** (`100.0%`) | Normalized *"Refuse home **administration** of nifedipine"* $\equiv$ *"do not administer"*. |
| **`VIG-ECHIS-L3-010`** | Cholera Linens in Community Stream | **FAIL** (131/130 words) | **PASS (Soft)** / **FAIL (Strict)** | 1-word budget overshoot (`131` vs. `130` words) captured cleanly by separate `strict` vs. `soft` (+2w margin) metrics. |
| **`VIG-ECHIS-L1-006`** | 6-Week Infant Immunizations | **FAIL** (`50.0%`) | **FAIL** (`50.0%` — *True Omission*) | Model listed `Penta 1` and `OPV 1` but genuinely omitted `PCV 1` and `Rota 1`—correctly remains flagged as a failure. |

### B. Blaze Test Verification Summary

- **Target:** `//experimental/users/fredhersch/chw_edge_evals:chw_edge_evals_test`
- **Status:** **PASSED (5/5 tests green, exit code 0)**
  1. `test_ast_scorer_rescues_four_gemma4_2b_false_negatives` — Verified 24/30 (`80.0%`) $\to$ 28/30 (`93.3%` strict) / 29/30 (`96.7%` soft).
  2. `test_sql_on_fhir_markdown_template_rendering` — Verified SQL-on-FHIR view projection + Markdown template formatting.
  3. `test_acdu_systematic_ablations_and_swahili_recall` — Verified pre-prompt deontic conflict pruning and 100% Swahili vernacular query recall.
  4. `test_judge_calibration_100_curation_and_meta_eval` — Verified 100-case calibration set curation (`50` seeded faults + `50` real completions, sensitivity `100%`, $\kappa = 1.0$).
  5. `test_vibe_eval_runner_and_medgemma_artifact_export` — Verified `ChwVibeEvalRunner` and MedGemma `test_results.tsv` / `test_metrics.json` export.
