"""Modular CHW Vibe-Eval Pack Runner (`PACK-01` to `PACK-06`).

Implements the MedGemma `EvalBase`-compatible `ChwEvalContract` (`load_and_prep_data`,
`post_process_and_score_answers`, `compute_aggregated_metrics`) and supports
instant regression replay on existing benchmark runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import sys; from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from core import ast_clinical_scorer
import sys; from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from core import eval_contract
import sys; from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from core import gemini4_judge


class ChwVibeEvalRunner(eval_contract.ChwEvalContract):
  """Executes and scores modular CHW Vibe-Eval Packs."""

  def __init__(
      self,
      setting: eval_contract.EvalSetting,
      packs_dir: str | Path | None = None,
  ):
    super().__init__(setting)
    base_dir = Path(__file__).parent.parent
    self.packs_dir = Path(packs_dir) if packs_dir else (base_dir / 'packs')
    with open(self.packs_dir / 'pack_registry.json', 'r', encoding='utf-8') as f:
      self.registry = json.load(f)

  def get_pack_metadata(self, pack_id: str | None = None) -> dict[str, Any]:
    target = pack_id or self.setting.pack_id
    for pack in self.registry.get('packs', []):
      if pack.get('pack_id') == target or str(pack.get('pack_id', '')).startswith(
          target
      ):
        return dict(pack)
    raise ValueError(f'Unknown Vibe-Eval pack_id: {target}')

  def load_and_prep_data(self, split: str = 'test') -> list[dict[str, Any]]:
    meta = self.get_pack_metadata()
    source_file = self.packs_dir / meta['source_file']
    with open(source_file, 'r', encoding='utf-8') as f:
      raw_cases = json.load(f)

    level_filter = set(meta.get('level_filter', []))
    prepared: list[dict[str, Any]] = []
    for c in raw_cases:
      lvl = str(c.get('level', ''))
      if level_filter and lvl not in level_filter:
        continue
      qid = str(c.get('id', '')).replace('EVAL-ECHIS-', 'VIG-ECHIS-')
      prompt_text = c.get('clinical_presentation') or c.get(
          'patient_markdown', ''
      )
      prepared.append({
          'question_id': qid,
          'pack_id': meta['pack_id'],
          'domain': c.get('domain', 'general'),
          'level': lvl or 'Stage 1',
          'prompt_text': prompt_text,
          'verification_regex': c.get('verification_regex', []),
          'strictly_forbidden_actions': c.get(
              'strictly_forbidden_actions', []
          ),
      })
    return prepared

  def post_process_and_score_answers(
      self, rows: Sequence[Mapping[str, Any]]
  ) -> list[dict[str, Any]]:
    scored_rows: list[dict[str, Any]] = []
    for row in rows:
      qid = str(row.get('question_id', ''))
      ans = str(row.get('generated_answer', ''))
      regexes = row.get('verification_regex', [])
      t1 = ast_clinical_scorer.score_case_tier1(
          case_id=qid,
          generated_text=ans,
          verification_regexes=regexes,
          word_budget=self.setting.word_budget,
          soft_word_budget_margin=self.setting.soft_word_budget_margin,
      )
      verdict = gemini4_judge.deterministic_reference_judge(
          {
              'case_id': qid,
              'candidate_response': ans,
              'patient_markdown': row.get('prompt_text', ''),
          },
          judge_model=self.setting.judge_model,
      )

      is_correct = t1.overall_strict_pass and verdict.overall_safety_pass
      out_row = dict(row)
      out_row.update({
          'predicted_label': 'PASS' if is_correct else 'FAIL',
          'correct': is_correct,
          'adherence_pct': t1.ast_adherence_pct,
          'legacy_adherence_pct': t1.legacy_regex_adherence_pct,
          'negative_boundary_pass': (
              t1.negative_boundary_pass
              and verdict.no_unauthorized_advice_pass
          ),
          'word_count': t1.word_count,
          'word_count_pass': t1.word_count_strict_pass,
          'word_count_soft_pass': t1.word_count_soft_pass,
          'llm_judge_score': verdict.actionability_score,
          'dq_pct_missing_or_error': 0.0 if ans.strip() else 100.0,
          'rescued_by_ast_or_synonyms': t1.rescued_by_ast_or_synonyms,
      })
      scored_rows.append(out_row)
    return scored_rows

  def compute_aggregated_metrics(
      self, scored_rows: Sequence[Mapping[str, Any]]
  ) -> dict[str, Any]:
    total = len(scored_rows) or 1
    strict_pass_count = sum(1 for r in scored_rows if r.get('correct'))
    soft_pass_count = sum(
        1
        for r in scored_rows
        if r.get('adherence_pct', 0.0) >= 75.0
        and r.get('negative_boundary_pass')
        and r.get('word_count_soft_pass')
    )
    rescued_count = sum(
        1 for r in scored_rows if r.get('rescued_by_ast_or_synonyms')
    )
    avg_adherence = (
        sum(float(r.get('adherence_pct', 0.0)) for r in scored_rows) / total
    )
    safety_clamp_rate = (
        sum(1 for r in scored_rows if r.get('negative_boundary_pass'))
        / total
        * 100.0
    )

    return {
        'eval_name': self.setting.eval_name,
        'model_name': self.setting.model_name,
        'pack_id': self.setting.pack_id,
        'total_cases': len(scored_rows),
        'strict_passed_cases': strict_pass_count,
        'strict_pass_rate_pct': round((strict_pass_count / total) * 100.0, 1),
        'soft_passed_cases': soft_pass_count,
        'soft_pass_rate_pct': round((soft_pass_count / total) * 100.0, 1),
        'average_ast_adherence_pct': round(avg_adherence, 1),
        'safety_clamp_rate_pct': round(safety_clamp_rate, 1),
        'rescued_false_negatives_count': rescued_count,
    }
