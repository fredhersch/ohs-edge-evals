"""Unit and regression tests for CHW & FHW Edge SLM Evaluation Framework."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import sys; from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from core import acdu_retriever
import sys; from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from core import ast_clinical_scorer
import sys; from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from core import eval_contract
import sys; from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from core import gemini4_judge
import sys; from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from core import sql_on_fhir_renderer
from gold import build_judge_calibration
from runners import run_acdu_systematic_ablations
from runners import run_vibe_evals


PACKAGE_ROOT = Path(__file__).parent.parent
PACKS_DIR = PACKAGE_ROOT / 'packs'


class ChwEdgeEvalsPhase1Test(unittest.TestCase):

  def test_ast_scorer_rescues_four_gemma4_2b_false_negatives(self):
    with open(
        PACKS_DIR / 'baseline_gemma4_2b_run.json', 'r', encoding='utf-8'
    ) as f:
      run_payload = json.load(f)
    with open(PACKS_DIR / 'eval_cases_echis.json', 'r', encoding='utf-8') as f:
      seed_cases = json.load(f)

    audit = ast_clinical_scorer.audit_benchmark_run(
        run_payload=run_payload,
        seed_cases=seed_cases,
        soft_word_budget_margin=2,
    )

    self.assertEqual(audit['total_cases'], 30)
    self.assertEqual(audit['legacy_passed_cases'], 24)
    self.assertEqual(
        sorted(audit['rescued_false_negative_ids']),
        [
            'VIG-ECHIS-L2-005',
            'VIG-ECHIS-L2-009',
            'VIG-ECHIS-L3-001',
            'VIG-ECHIS-L3-004',
        ],
    )
    # 24 original passes + 4 rescued false negatives = 28 strict passes (93.3%)
    self.assertEqual(audit['ast_strict_passed_cases'], 28)
    self.assertAlmostEqual(audit['ast_strict_pass_rate_pct'], 93.3, places=1)
    # With 2-word soft budget margin, VIG-ECHIS-L3-010 (131/130 words) also passes -> 29/30 (96.7%)
    self.assertEqual(audit['ast_soft_passed_cases'], 29)
    self.assertAlmostEqual(audit['ast_soft_pass_rate_pct'], 96.7, places=1)
    # Genuine clinical omission (VIG-ECHIS-L1-006 missing PCV-1/Rota-1 vaccines) remains flagged
    self.assertIn('VIG-ECHIS-L1-006', audit['remaining_strict_failure_ids'])

  def test_sql_on_fhir_markdown_template_rendering(self):
    renderer = sql_on_fhir_renderer.SqlOnFhirMarkdownRenderer(
        PACKS_DIR / 'sql_on_fhir_views'
    )
    sample_bundle = {
        'resourceType': 'Bundle',
        'type': 'collection',
        'entry': [
            {
                'resource': {
                    'resourceType': 'Patient',
                    'id': 'pat-fatima',
                    'name': [{'given': ['Fatima'], 'family': 'Bello'}],
                    'gender': 'female',
                    'birthDate': '1998-04-10',
                }
            },
            {
                'resource': {
                    'resourceType': 'Condition',
                    'code': {'text': 'Uncomplicated Malaria'},
                    'clinicalStatus': {'coding': [{'code': 'resolved'}]},
                    'recordedDate': '2025-05-12',
                }
            },
            {
                'resource': {
                    'resourceType': 'Observation',
                    'code': {'coding': [{'code': '85354-9'}]},
                    'effectiveDateTime': '2026-10-18',
                    'component': [
                        {
                            'code': {'coding': [{'code': '8480-6'}]},
                            'valueQuantity': {'value': 148},
                        },
                        {
                            'code': {'coding': [{'code': '8462-4'}]},
                            'valueQuantity': {'value': 96},
                        },
                    ],
                }
            },
            {
                'resource': {
                    'resourceType': 'Task',
                    'description': 'Urgent ANC Pre-Eclampsia Hospital Referral',
                    'status': 'requested',
                    'priority': 'urgent',
                    'restriction': {'period': {'end': '2026-10-19'}},
                }
            },
        ],
    }

    md = renderer.render_markdown(sample_bundle)
    self.assertIn('### Patient: Fatima Bello (28y, female)', md)
    self.assertIn('*RESOLVED / PAST*: Uncomplicated Malaria', md)
    self.assertIn('148/96 mmHg', md)
    self.assertIn('Urgent ANC Pre-Eclampsia Hospital Referral', md)

  def test_acdu_systematic_ablations_and_swahili_recall(self):
    ablation_summary = (
        run_acdu_systematic_ablations.evaluate_acdu_retrieval_and_deontic_ablations(
            PACKS_DIR
        )
    )
    self.assertEqual(ablation_summary['total_echis_cases'], 30)
    self.assertGreater(
        ablation_summary['deontic_resolver_pruned_conflicts_count'], 0
    )
    self.assertEqual(
        ablation_summary['swahili_vernacular_recall_expanded_pct'], 100.0
    )
    self.assertLess(
        ablation_summary['swahili_vernacular_recall_unexpanded_pct'],
        ablation_summary['swahili_vernacular_recall_expanded_pct'],
    )

  def test_judge_calibration_100_curation_and_meta_eval(self):
    with tempfile.TemporaryDirectory() as tmpdir:
      out_file = Path(tmpdir) / 'judge_calibration_100.json'
      cal_items = build_judge_calibration.build_judge_calibration_100(
          packs_dir=PACKS_DIR, output_path=out_file
      )
      self.assertEqual(len(cal_items), 100)
      metrics = gemini4_judge.evaluate_judge_on_calibration_set(cal_items)
      self.assertEqual(metrics['total_calibration_cases'], 100)
      self.assertEqual(metrics['seeded_fault_cases'], 50)
      self.assertGreaterEqual(metrics['seeded_fault_sensitivity_pct'], 98.0)
      self.assertGreaterEqual(metrics['cohens_kappa'], 0.85)
      self.assertTrue(metrics['meets_release_gate'])

  def test_vibe_eval_runner_and_medgemma_artifact_export(self):
    setting = eval_contract.EvalSetting(
        eval_name='ChwAcduSafetyClamps',
        model_name='gemma4-2b:latest',
        pack_id='PACK-03-ADVERSARIAL-SAFETY-CLAMPS',
    )
    runner = run_vibe_evals.ChwVibeEvalRunner(setting, packs_dir=PACKS_DIR)
    rows = runner.load_and_prep_data()
    self.assertEqual(len(rows), 10)

    with open(
        PACKS_DIR / 'baseline_gemma4_2b_run.json', 'r', encoding='utf-8'
    ) as f:
      run_data = json.load(f)
    ans_by_id = {
        r['vignette_id']: r['generated_text']
        for r in run_data.get('case_results', [])
    }
    for row in rows:
      row['generated_answer'] = ans_by_id.get(row['question_id'], '')

    scored = runner.post_process_and_score_answers(rows)
    agg = runner.compute_aggregated_metrics(scored)
    self.assertEqual(agg['total_cases'], 10)
    self.assertEqual(agg['soft_passed_cases'], 10)
    self.assertGreaterEqual(agg['rescued_false_negatives_count'], 1)

    with tempfile.TemporaryDirectory() as tmpdir:
      exported = runner.export_medgemma_eval_artifacts(scored, agg, tmpdir)
      self.assertTrue(Path(exported['results_tsv']).exists())
      self.assertTrue(Path(exported['metrics_json']).exists())
      self.assertTrue(Path(exported['settings_json']).exists())


if __name__ == '__main__':
  unittest.main()
