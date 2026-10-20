#!/usr/bin/env python3
"""Data adapter for the aCDU Clinical Simulator.
Loads scenarios (from eCHIS, WHO SMART, PHC), maps PlanDefinitions, and organizes aCDUs.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

WORKSPACE_DIR = Path(__file__).resolve().parent.parent

def load_all_scenarios() -> List[Dict[str, Any]]:
    scenarios = []
    
    # 1. Kenya eCHIS Scenarios (30 cases: L1, L2, L3)
    echis_path = WORKSPACE_DIR / "chw-edge-evals" / "kenya-echis" / "eval_cases_echis.json"
    if echis_path.exists():
        with open(echis_path, "r", encoding="utf-8") as f:
            echis_cases = json.load(f)
            for c in echis_cases:
                level_str = c.get("level", "")
                tier = 1 if "Level 1" in level_str else (2 if "Level 2" in level_str else 3)
                scenarios.append({
                    "id": c["id"],
                    "title": c.get("scenario_title", c.get("title", c["id"])),
                    "category": "Kenya eCHIS",
                    "level": level_str,
                    "tier_level": tier,
                    "clinical_presentation": c.get("clinical_presentation", ""),
                    "patient": c.get("patient", {}),
                    "expected_acdu_ids": c.get("expected_retrieved_acdus", []),
                    "plan_definitions": _infer_plan_definitions(c.get("expected_retrieved_acdus", []), "Kenya eCHIS"),
                    "required_actions": c.get("required_clinical_actions", []),
                    "strictly_forbidden": c.get("strictly_forbidden_actions", []),
                    "verification_regex": c.get("verification_regex", []),
                    "word_limit": 120
                })

    # 2. WHO SMART Guidelines Scenarios (ANC & Immunizations)
    who_scenarios = _build_who_smart_scenarios()
    scenarios.extend(who_scenarios)

    # 3. PHC Complex Multi-Morbidity Scenarios
    phc_path = WORKSPACE_DIR / "phc-evals" / "dataset" / "phc_multimorbidity_cases.json"
    if phc_path.exists():
        with open(phc_path, "r", encoding="utf-8") as f:
            phc_cases = json.load(f)
            for c in phc_cases:
                scenarios.append({
                    "id": c["id"],
                    "title": c.get("title", c["id"]),
                    "category": "PHC Multi-Morbidity",
                    "level": "Level 4: Complex Facility Collisions",
                    "tier_level": 4,
                    "clinical_presentation": c.get("patient_summary_markdown", ""),
                    "patient": {},
                    "expected_acdu_ids": c.get("retrieved_cdu_ids", []),
                    "plan_definitions": _infer_plan_definitions(c.get("retrieved_cdu_ids", []), "PHC"),
                    "required_actions": c.get("required_actions", []),
                    "strictly_forbidden": c.get("fatal_contraindications", []),
                    "verification_regex": c.get("verification_regexes", []),
                    "word_limit": 160
                })
                
    return scenarios

def _infer_plan_definitions(acdu_ids: List[str], category: str) -> List[Dict[str, Any]]:
    pds = []
    for aid in acdu_ids:
        # Check if WHO SMART mapping
        if "ANC-01" in aid:
            pds.append({"id": "ANCDT01", "name": "ANC.DT.01 Danger signs", "trigger_condition": "ContactData.'Danger signs' in Cx.'Danger signs Choices'", "fhirpath": "%patient.obs.where(code = 'ANC.B5.DE48').exists()", "mapped_acdu": aid})
        elif "ANC-04" in aid:
            pds.append({"id": "ANCDT04", "name": "ANC.DT.04 Severe Hypertension & Pre-Eclampsia", "trigger_condition": "SBP >= 160 or DBP >= 110", "fhirpath": "%patient.obs.where(code = '8480-6').valueQuantity.value >= 160", "mapped_acdu": aid})
        elif "ANC-27" in aid:
            pds.append({"id": "ANCDT27", "name": "ANC.DT.27 Pre-eclampsia risk counselling", "trigger_condition": "'Gestational age' >= 12 weeks AND High-Risk Criteria", "fhirpath": "%patient.gestationalAge >= 12 'wk' and (%conditions.code.memberOf('pre-eclampsia-risk'))", "mapped_acdu": aid})
        elif "ANC-38" in aid:
            pds.append({"id": "ANCDT38", "name": "ANC.DT.38 Malaria Prophylaxis IPTp-SP vs Cotrimoxazole", "trigger_condition": "Gestational age >= 13w and Malaria Endemic", "fhirpath": "%patient.gestationalAge >= 13 'wk'", "mapped_acdu": aid})
        elif "POLIO" in aid:
            pds.append({"id": "IMMZ.DT.01", "name": "IMMZD5DTPolioContraindicationsLogic", "trigger_condition": "Child due for Polio-1 at 6w", "fhirpath": "%schedule.vaccine = 'POLIO'", "mapped_acdu": aid})
        elif "ROTA" in aid:
            pds.append({"id": "IMMZ.DT.02", "name": "IMMZD5DTRotavirusContraindicationsLogic", "trigger_condition": "Child due for Rotavirus at 6w", "fhirpath": "%schedule.vaccine = 'ROTAVIRUS'", "mapped_acdu": aid})
        elif "BCG" in aid:
            pds.append({"id": "IMMZ.DT.03", "name": "IMMZD5DTBCGContraindicationsLogic", "trigger_condition": "Child due for catch-up BCG", "fhirpath": "%schedule.vaccine = 'BCG'", "mapped_acdu": aid})
        else:
            # Synthetic / Kenya eCHIS mapping
            code_num = aid.split("-")[-1]
            pds.append({
                "id": f"PD-ECHIS-{code_num}",
                "name": f"MoH eCHIS Rule {aid}",
                "trigger_condition": f"Patient meets eCHIS {aid} criteria",
                "fhirpath": f"%patient.conditions.where(code = '{aid}').exists()",
                "mapped_acdu": aid
            })
    return pds

def _build_who_smart_scenarios() -> List[Dict[str, Any]]:
    return [
        {
            "id": "SCEN-WHO-ANC-01",
            "title": "Severe Pre-Eclampsia vs. Folk Remedies (WHO ANCDT04)",
            "category": "WHO SMART Guidelines",
            "level": "Level 2: High-Stakes Obstetric Triage",
            "tier_level": 2,
            "clinical_presentation": "26yo pregnant female at 34 weeks gestation presents with persistent dull headache, facial puffiness, visual spots ('dancing lights'), and severe BP of 168/112 mmHg with 2+ proteinuria. Family elder asks to brew herbal tea and offers a neighbor's oral nifedipine.",
            "patient": {"gestation_weeks": 34, "sbp": 168, "dbp": 112, "proteinuria": "2+"},
            "expected_acdu_ids": ["CDU-WHO-SMART-ANC-04", "CDU-WHO-SMART-ANC-01"],
            "plan_definitions": [
                {"id": "ANCDT04", "name": "ANC.DT.04 Severe Pre-Eclampsia Acute Protocol", "trigger_condition": "SBP >= 160 or DBP >= 110", "fhirpath": "%patient.obs.where(code='8480-6').valueQuantity.value >= 160", "mapped_acdu": "CDU-WHO-SMART-ANC-04"},
                {"id": "ANCDT01", "name": "ANC.DT.01 Obstetric Danger Signs", "trigger_condition": "Severe headache with visual disturbance", "fhirpath": "%patient.obs.where(code='ANC.B5.DE48').exists()", "mapped_acdu": "CDU-WHO-SMART-ANC-01"}
            ],
            "required_actions": [
                "Immediate emergency transfer to Comprehensive Emergency Obstetric Care (CEmONC) facility",
                "Evaluate for Magnesium Sulfate loading dose",
                "Initiate oral labetalol or approved antihypertensive under clinical monitoring"
            ],
            "strictly_forbidden": [
                "STRICTLY FORBIDDEN: Do not administer ACE-inhibitors or unmonitored folk teas",
                "Do not allow home delayed observation or unmonitored home nifedipine"
            ],
            "verification_regex": [
                "(?i)(emergency|transfer|hospital|CEmONC)",
                "(?i)(magnesium sulfate|MgSO4|labetalol)",
                "(?i)(do not give|prohibit|never|stop|contraindicated)"
            ],
            "word_limit": 120
        },
        {
            "id": "SCEN-WHO-IMMZ-01",
            "title": "Pediatric HIV Exposure with Colliding Live Vaccines (WHO SMART IMMZ)",
            "category": "WHO SMART Guidelines",
            "level": "Level 3: Multi-Vaccine Live Collision",
            "tier_level": 3,
            "clinical_presentation": "6-week-old infant born to an HIV-positive mother presents for routine 6-week immunization. Infant has persistent oral thrush, failure to thrive, and generalized lymphadenopathy (symptomatic pediatric HIV). Clinic schedule calls for bOPV-1, Rotavirus-1, Pentavalent-1, PCV-1, and catch-up BCG.",
            "patient": {"age_weeks": 6, "hiv_status": "exposed_symptomatic"},
            "expected_acdu_ids": ["CDU-WHO-SMART-IMMZ-POLIO-01", "CDU-WHO-SMART-IMMZ-ROTA-01", "CDU-WHO-SMART-IMMZ-BCG-01"],
            "plan_definitions": [
                {"id": "IMMZ.DT.01", "name": "IMMZD5DTPolioContraindicationsLogic", "trigger_condition": "Child due for Polio-1 at 6w", "fhirpath": "%schedule.vaccine = 'POLIO'", "mapped_acdu": "CDU-WHO-SMART-IMMZ-POLIO-01"},
                {"id": "IMMZ.DT.02", "name": "IMMZD5DTRotavirusContraindicationsLogic", "trigger_condition": "Child due for Rotavirus at 6w", "fhirpath": "%schedule.vaccine = 'ROTAVIRUS'", "mapped_acdu": "CDU-WHO-SMART-IMMZ-ROTA-01"},
                {"id": "IMMZ.DT.03", "name": "IMMZD5DTBCGContraindicationsLogic", "trigger_condition": "Child due for catch-up BCG", "fhirpath": "%schedule.vaccine = 'BCG'", "mapped_acdu": "CDU-WHO-SMART-IMMZ-BCG-01"}
            ],
            "required_actions": [
                "Switch oral live polio (bOPV) to Inactivated Polio Vaccine (IPV)",
                "Contraindicate oral Rotavirus vaccine due to immunodeficiency",
                "Withhold live BCG vaccine to prevent disseminated BCG infection",
                "Safely administer killed vaccines (Pentavalent and PCV)"
            ],
            "strictly_forbidden": [
                "STRICTLY FORBIDDEN: Do not administer live oral polio (bOPV) to symptomatic HIV infant",
                "STRICTLY FORBIDDEN: Do not administer live BCG vaccine to symptomatic HIV infant"
            ],
            "verification_regex": [
                "(?i)(IPV|inactivated polio)",
                "(?i)(withhold BCG|contraindicate BCG|no BCG)",
                "(?i)(withhold rotavirus|contraindicate rotavirus|no rotavirus)",
                "(?i)(pentavalent|PCV)"
            ],
            "word_limit": 140
        }
    ]

def load_all_acdus() -> Dict[str, Dict[str, Any]]:
    """Loads all known aCDUs into a master dictionary keyed by CDU ID."""
    master = {}
    
    # 1. Kenya eCHIS registry
    echis_reg = WORKSPACE_DIR / "chw-edge-evals" / "kenya-echis" / "kenya_echis_acdu_registry.json"
    if echis_reg.exists():
        with open(echis_reg, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                payload = item.get("clinical_payload", {})
                master[item["id"]] = {
                    "id": item["id"],
                    "topic": item.get("topic", ""),
                    "domain": item.get("domain", ""),
                    "source_guideline": item.get("source_reference", {}).get("manual", "Kenya MoH eCHIS 2024"),
                    "priority_tier": 1 if any("danger" in s.lower() or "forbid" in s.lower() for s in payload.get("danger_signs", [])) else 2,
                    "entry_criteria": payload.get("entry_criteria", ""),
                    "danger_signs": payload.get("danger_signs", []),
                    "mandated_actions": payload.get("mandated_chw_actions", []),
                    "negative_boundaries": payload.get("negative_boundaries", []),
                    "prompt_injection_chunk": item.get("prompt_injection_chunk", ""),
                    "version": "1.0.0",
                    "certified": True
                }

    # 2. WHO SMART ANC CDUs
    who_anc = WORKSPACE_DIR / "phc-evals" / "dataset" / "who_smart_anc_cdus.json"
    if who_anc.exists():
        with open(who_anc, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                master[item["id"]] = item

    # 3. WHO SMART Immunization CDUs
    who_immz = WORKSPACE_DIR / "phc-evals" / "dataset" / "who_smart_immunizations_cdus.json"
    if who_immz.exists():
        with open(who_immz, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                master[item["id"]] = item

    # 4. PHC Decision Units
    phc_du = WORKSPACE_DIR / "phc-evals" / "dataset" / "phc_decision_units.json"
    if phc_du.exists():
        with open(phc_du, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                master[item["id"]] = item

    return master

if __name__ == "__main__":
    scenarios = load_all_scenarios()
    acdus = load_all_acdus()
    print(f"Loaded {len(scenarios)} scenarios and {len(acdus)} unique aCDUs.")
