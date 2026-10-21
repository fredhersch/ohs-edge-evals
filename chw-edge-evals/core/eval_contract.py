"""MedGemma EvalBase-compatible evaluation contract for CHW & FHW Edge SLMs.

Mirrors the 3-method contract of
`//third_party/health_foundations/medgemma/internal/evals/lib/eval_base.py`
(`load_and_prep_data`, `post_process_and_score_answers`,
`compute_aggregated_metrics`) and writes identical output files
(`test_results.tsv`, `test_metrics.json`, `test_settings.json`) so that GDI
evaluations can run independently today and plug into `medgemma/internal/evals`
later with zero refactoring.
"""

from __future__ import annotations

import abc
import csv
import dataclasses
import datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclasses.dataclass
class EvalSetting:
  """Configuration settings for an evaluation run."""

  eval_name: str
  model_name: str
  pack_id: str
  conditioning_regime: str = 'with_cdus'
  word_budget: int = 130
  soft_word_budget_margin: int = 2
  judge_model: str = 'gemini-4'
  split: str = 'test'


class ChwEvalContract(abc.ABC):
  """Abstract base contract compatible with MedGemma Internal Evals."""

  def __init__(self, setting: EvalSetting):
    self.setting = setting

  @abc.abstractmethod
  def load_and_prep_data(self, split: str = 'test') -> list[dict[str, Any]]:
    """Loads evaluation rows with required `question_id` and `prompt_text`."""

  @abc.abstractmethod
  def post_process_and_score_answers(
      self, rows: Sequence[Mapping[str, Any]]
  ) -> list[dict[str, Any]]:
    """Scores generated answers (`generated_answer`) and attaches per-row metrics."""

  @abc.abstractmethod
  def compute_aggregated_metrics(
      self, scored_rows: Sequence[Mapping[str, Any]]
  ) -> dict[str, Any]:
    """Aggregates row-level results into a summary metrics dictionary."""

  def export_medgemma_eval_artifacts(
      self,
      scored_rows: Sequence[Mapping[str, Any]],
      aggregated_metrics: Mapping[str, Any],
      output_dir: str | Path,
  ) -> dict[str, str]:
    """Exports `test_results.tsv`, `test_metrics.json`, and `test_settings.json`."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    results_tsv_path = out_path / f'{self.setting.split}_results.tsv'
    metrics_json_path = out_path / f'{self.setting.split}_metrics.json'
    settings_json_path = out_path / f'{self.setting.split}_settings.json'

    fieldnames = [
        'question_id',
        'pack_id',
        'domain',
        'level',
        'generated_answer',
        'predicted_label',
        'correct',
        'adherence_pct',
        'negative_boundary_pass',
        'word_count',
        'word_count_pass',
        'llm_judge_score',
        'dq_pct_missing_or_error',
    ]

    with open(results_tsv_path, 'w', encoding='utf-8', newline='') as f:
      writer = csv.DictWriter(
          f, fieldnames=fieldnames, delimiter='\t', extrasaction='ignore'
      )
      writer.writeheader()
      for row in scored_rows:
        writer.writerow(row)

    with open(metrics_json_path, 'w', encoding='utf-8') as f:
      json.dump(dict(aggregated_metrics), f, indent=2, sort_keys=True)

    settings_payload = dataclasses.asdict(self.setting)
    settings_payload['exported_at_utc'] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()
    with open(settings_json_path, 'w', encoding='utf-8') as f:
      json.dump(settings_payload, f, indent=2, sort_keys=True)

    return {
        'results_tsv': str(results_tsv_path),
        'metrics_json': str(metrics_json_path),
        'settings_json': str(settings_json_path),
    }
