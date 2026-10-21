"""Systematic 5-Axis aCDU Evaluation & Ablation Runner.

Executes controlled ablation experiments defined in Section 3 of
`docs/slm_chw_evals_framework_plan.md`:
- Exp 1: Conditioning Regimes (`zero_shot` vs. `naive_pdf_rag` vs.
  `hierarchical_rag` vs. `with_cdus`)
- Exp 2: 7-Tuple Component Ablation (`-Cohort C`, `-Negative Set N`,
  `-Deontic Resolver`, `-Token Compression M`)
- Exp 3: Zero-RAM SQLite FTS5 Retrieval on Textbook vs. Colloquial/Swahili Queries
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import sys; from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from core import acdu_retriever


def evaluate_acdu_retrieval_and_deontic_ablations(
    packs_dir: str | Path | None = None,
) -> dict[str, Any]:
  """Runs systematic Box-1 retrieval, cohort pruning, and deontic resolution ablations."""
  base_dir = Path(__file__).parent.parent
  p_dir = Path(packs_dir) if packs_dir else (base_dir / 'packs')

  gatekeeper = acdu_retriever.ZeroRamAcduGatekeeper(
      p_dir / 'kenya_echis_acdu_registry.json'
  )
  with open(p_dir / 'eval_cases_echis.json', 'r', encoding='utf-8') as f:
    cases = json.load(f)

  # 1. Compare Retrieval With Cohort Filter vs. Without Cohort Filter
  hits_with_cohort = 0
  hits_without_cohort = 0
  for case in cases:
    expected_ids = set(case.get('expected_retrieved_acdus', []))
    presentation = str(case.get('clinical_presentation', ''))
    patient = case.get('patient', {})

    ret_with = gatekeeper.retrieve(
        presentation,
        patient=patient,
        config=acdu_retriever.AcduAblationConfig(
            top_k=3, include_cohort_filter=True
        ),
    )
    ret_without = gatekeeper.retrieve(
        presentation,
        patient=patient,
        config=acdu_retriever.AcduAblationConfig(
            top_k=3, include_cohort_filter=False
        ),
    )
    if expected_ids & {u['id'] for u in ret_with}:
      hits_with_cohort += 1
    if expected_ids & {u['id'] for u in ret_without}:
      hits_without_cohort += 1

  # 2. Evaluate Deontic Conflict Resolver on Multi-Morbidity Collision Cases
  # (e.g., Severe Malaria with Convulsions + Fast Breathing Pneumonia)
  collision_units = [
      gatekeeper.by_id['KENYA-ECHIS-ICCM-03'],  # Severe Malaria (forbids oral AL)
      gatekeeper.by_id['KENYA-ECHIS-ICCM-04'],  # Fast Breathing (requires oral Amox DT)
  ]
  resolved_on = gatekeeper.resolve_deontic_bundle(
      collision_units,
      acdu_retriever.AcduAblationConfig(enable_deontic_resolver=True),
  )
  resolved_off = gatekeeper.resolve_deontic_bundle(
      collision_units,
      acdu_retriever.AcduAblationConfig(enable_deontic_resolver=False),
  )

  # 3. Evaluate Colloquial / Swahili Trigger Expansion Recall
  swahili_queries = [
      (
          'Mtoto anahema haraka na kifua inapiga tangu jana',
          {'age_months': 14, 'patient_status': 'infant_or_child'},
          'KENYA-ECHIS-ICCM-04',
      ),
      (
          'Watu wanne wana kuhara maji kama mchele kijijini',
          {'patient_status': 'community_member'},
          'KENYA-ECHIS-CEBS-02',
      ),
      (
          'Mama mjamzito ana kichwa kuuma sana na BP 168/112',
          {'gestation_weeks': 34, 'patient_status': 'pregnant'},
          'KENYA-ECHIS-MNH-02',
      ),
  ]
  swahili_hits_expanded = 0
  swahili_hits_unexpanded = 0
  for q_text, pat, target_id in swahili_queries:
    r_exp = gatekeeper.retrieve(
        q_text,
        patient=pat,
        config=acdu_retriever.AcduAblationConfig(
            top_k=3, expand_vernacular_synonyms=True
        ),
    )
    r_raw = gatekeeper.retrieve(
        q_text,
        patient=pat,
        config=acdu_retriever.AcduAblationConfig(
            top_k=3, expand_vernacular_synonyms=False
        ),
    )
    if target_id in {u['id'] for u in r_exp}:
      swahili_hits_expanded += 1
    if target_id in {u['id'] for u in r_raw}:
      swahili_hits_unexpanded += 1

  total_cases = len(cases) or 1
  return {
      'total_echis_cases': len(cases),
      'top3_recall_with_cohort_filter_pct': round(
          (hits_with_cohort / total_cases) * 100.0, 1
      ),
      'top3_recall_without_cohort_filter_pct': round(
          (hits_without_cohort / total_cases) * 100.0, 1
      ),
      'deontic_resolver_pruned_conflicts_count': len(
          resolved_on['pruned_conflicts']
      ),
      'deontic_resolver_pruned_actions': resolved_on['pruned_conflicts'],
      'unpruned_action_count_when_disabled': len(resolved_off['r_safe']),
      'pruned_action_count_when_enabled': len(resolved_on['r_safe']),
      'swahili_vernacular_recall_expanded_pct': round(
          (swahili_hits_expanded / len(swahili_queries)) * 100.0, 1
      ),
      'swahili_vernacular_recall_unexpanded_pct': round(
          (swahili_hits_unexpanded / len(swahili_queries)) * 100.0, 1
      ),
  }
