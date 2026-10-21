"""Zero-RAM SQLite FTS5 Box-1 Gatekeeper & Systematic aCDU Ablation Engine.

Implements the Two-Box `aCDU` retrieval and pre-prompt deontic conflict
resolution architecture:
  N_total = U_{i=1}^k N_i
  R_safe  = (U_{i=1}^k R_i) \\ Conflict(R, N_total)

Supports the 5-Experiment systematic ablation switches defined in Section 3 of
`docs/slm_chw_evals_framework_plan.md`:
- `conditioning_regime`: `zero_shot` | `naive_pdf_rag` | `hierarchical_rag` | `with_cdus`
- `include_cohort_filter` (Toggle Cohort C)
- `include_negative_set` (Toggle Negative Set N)
- `enable_deontic_resolver` (Toggle Pre-Prompt Deontic Conflict Resolution)
- `compress_tokens` (Toggle <=180-token compressed M vs. verbose guideline text)
- `expand_vernacular_synonyms` (Enrich trigger index T with Swahili/colloquial phrases)
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping, Sequence


_SWAHILI_COLLOQUIAL_TRIGGER_MAP: dict[str, str] = {
    'mtoto anahema haraka': 'fast breathing pneumonia cough tachypnea amoxicillin',
    'kifua inapiga': 'chest indrawing severe pneumonia danger sign',
    'homa kali': 'high fever malaria mRDT chills artemether',
    'kuhara maji kama mchele': 'rice water diarrhea cholera outbreak dehydration cebs',
    'kifafa': 'convulsions seizures general danger sign rectal artesunate',
    'kichwa kuuma': 'severe frontal headache pre-eclampsia hypertension bp',
    'damu kutoka ukeni': 'vaginal bleeding antepartum hemorrhage placenta previa',
    'kaloba': 'traditional herbs oxytocic labor uterine rupture',
}


@dataclasses.dataclass
class AcduAblationConfig:
  """Configuration switches for systematic aCDU ablation experiments."""

  conditioning_regime: str = 'with_cdus'
  top_k: int = 3
  include_cohort_filter: bool = True
  include_negative_set: bool = True
  enable_deontic_resolver: bool = True
  compress_tokens: bool = True
  expand_vernacular_synonyms: bool = True


def _extract_required_actions(item: Mapping[str, Any]) -> list[str]:
  payload = item.get('clinical_payload', {})
  actions = payload.get('mandated_chw_actions') or item.get(
      'required_actions', []
  )
  return [str(a) for a in actions]


def _extract_forbidden_actions(item: Mapping[str, Any]) -> list[str]:
  payload = item.get('clinical_payload', {})
  forbidden = payload.get('negative_boundaries') or item.get(
      'forbidden_actions', []
  )
  return [str(n) for n in forbidden]


def _extract_triggers_text(item: Mapping[str, Any]) -> str:
  t_idx = item.get('trigger_index', {})
  parts: list[str] = []
  if isinstance(t_idx, Mapping):
    for key in ('conditions', 'symptoms', 'vital_thresholds'):
      parts.extend(str(x) for x in t_idx.get(key, []))
  parts.extend(str(x) for x in item.get('clinical_triggers', []))
  payload = item.get('clinical_payload', {})
  if isinstance(payload, Mapping):
    parts.append(str(payload.get('entry_criteria', '')))
    parts.extend(str(x) for x in payload.get('danger_signs', []))
  return ' '.join(parts)


class ZeroRamAcduGatekeeper:
  """In-memory / SQLite FTS5 deterministic clinical decision unit retriever."""

  def __init__(self, registry_path: str | Path | None = None):
    if registry_path is None:
      registry_path = (
          Path(__file__).parent.parent
          / 'packs'
          / 'kenya_echis_acdu_registry.json'
      )
    self.registry_path = Path(registry_path)
    with open(self.registry_path, 'r', encoding='utf-8') as f:
      self.registry: list[dict[str, Any]] = json.load(f)
    self.by_id: dict[str, dict[str, Any]] = {
        str(item['id']): item for item in self.registry
    }
    self.conn = self._build_fts5_index()

  def _build_fts5_index(self) -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    cur.execute(
        'CREATE VIRTUAL TABLE acdu_fts USING fts5('
        'id UNINDEXED, title, module, triggers, required_actions, '
        'forbidden_actions, prompt_chunk)'
    )
    for item in self.registry:
      title = str(item.get('topic') or item.get('title') or '')
      module = str(item.get('domain') or item.get('module') or '')
      triggers_str = _extract_triggers_text(item)
      req_str = ' '.join(_extract_required_actions(item))
      forb_str = ' '.join(_extract_forbidden_actions(item))
      chunk = str(
          item.get('prompt_injection_chunk')
          or item.get('compressed_prompt_chunk')
          or ''
      )
      cur.execute(
          'INSERT INTO acdu_fts VALUES (?, ?, ?, ?, ?, ?, ?)',
          (item.get('id', ''), title, module, triggers_str, req_str, forb_str, chunk),
      )
    conn.commit()
    return conn

  def _cohort_matches(
      self, acdu: Mapping[str, Any], patient: Mapping[str, Any]
  ) -> bool:
    cohort = acdu.get('target_cohort') or acdu.get('cohort') or {}
    p_status = str(patient.get('patient_status', '')).lower()
    raw_allowed = cohort.get('patient_status')
    if isinstance(raw_allowed, str):
      allowed_statuses = [raw_allowed.lower()]
    elif isinstance(raw_allowed, Sequence):
      allowed_statuses = [str(s).lower() for s in raw_allowed]
    else:
      allowed_statuses = []

    if (
        allowed_statuses
        and 'all' not in allowed_statuses
        and p_status
        and p_status not in allowed_statuses
    ):
      return False

    age_months = patient.get('age_months')
    if age_months is not None:
      min_age = cohort.get('min_age_months')
      max_age = cohort.get('max_age_months')
      if min_age is not None and float(age_months) < float(min_age):
        return False
      if max_age is not None and float(age_months) > float(max_age):
        return False
    return True

  def retrieve(
      self,
      query_text: str,
      patient: Mapping[str, Any] | None = None,
      config: AcduAblationConfig | None = None,
  ) -> list[dict[str, Any]]:
    """Retrieves top-k matching aCDUs using SQLite FTS5 + optional cohort filter."""
    cfg = config or AcduAblationConfig()
    expanded_query = query_text
    if cfg.expand_vernacular_synonyms:
      lower_q = query_text.lower()
      for phrase, canonical in _SWAHILI_COLLOQUIAL_TRIGGER_MAP.items():
        if phrase in lower_q:
          expanded_query = f'{expanded_query} {canonical}'

    tokens = [
        t
        for t in re.findall(r'[A-Za-z0-9]{3,}', expanded_query.lower())
        if t
        not in {
            'the',
            'and',
            'for',
            'with',
            'has',
            'had',
            'his',
            'her',
            'she',
            'what',
            'should',
            'chp',
            'child',
            'woman',
            'patient',
        }
    ]
    if not tokens:
      return []

    fts_expr = ' OR '.join(dict.fromkeys(tokens))
    cur = self.conn.cursor()
    rows = cur.execute(
        'SELECT id, bm25(acdu_fts) AS score FROM acdu_fts '
        'WHERE acdu_fts MATCH ? ORDER BY score LIMIT 15',
        (fts_expr,),
    ).fetchall()

    results: list[dict[str, Any]] = []
    for acdu_id, _ in rows:
      acdu = self.by_id.get(str(acdu_id))
      if not acdu:
        continue
      if (
          cfg.include_cohort_filter
          and patient
          and not self._cohort_matches(acdu, patient)
      ):
        continue
      results.append(acdu)
      if len(results) >= cfg.top_k:
        break
    return results

  def resolve_deontic_bundle(
      self,
      acdus: Sequence[Mapping[str, Any]],
      config: AcduAblationConfig | None = None,
  ) -> dict[str, Any]:
    """Computes N_total and prunes conflicting oral/outpatient actions from R_safe."""
    cfg = config or AcduAblationConfig()
    all_required: list[str] = []
    all_forbidden: list[str] = []

    for unit in acdus:
      for r in _extract_required_actions(unit):
        if r not in all_required:
          all_required.append(r)
      if cfg.include_negative_set:
        for n in _extract_forbidden_actions(unit):
          if n not in all_forbidden:
            all_forbidden.append(n)

    if not cfg.enable_deontic_resolver or not all_forbidden:
      return {
          'acdu_ids': [u.get('id') for u in acdus],
          'r_safe': all_required,
          'n_total': all_forbidden,
          'pruned_conflicts': [],
      }

    # Pre-prompt deontic conflict resolution:
    # If any active emergency unit forbids oral medication/fluids or home
    # outpatient antibiotic treatment, prune conflicting routine oral dosing.
    forbids_oral_administration = any(
        re.search(
            r'(?i)(?:do not|never) (?:give|administer) oral|no oral|unable to drink|convulsing|unconscious',
            n,
        )
        for n in all_forbidden
    )
    forbids_outpatient_amox = any(
        re.search(
            r'(?i)do not treat as uncomplicated outpatient|home amoxicillin', n
        )
        for n in all_forbidden
    )

    r_safe: list[str] = []
    pruned: list[str] = []
    for action in all_required:
      is_routine_oral_tab = bool(
          re.search(
              r'(?i)\b(tablet|dispersible|dissolve|take with milk|oral amoxicillin|amoxicillin|coartem|artemether)\b',
              action,
          )
          and not re.search(r'(?i)\b(rectal|suppository|ras)\b', action)
      )
      if (
          forbids_oral_administration or forbids_outpatient_amox
      ) and is_routine_oral_tab:
        pruned.append(action)
      else:
        r_safe.append(action)

    return {
        'acdu_ids': [u.get('id') for u in acdus],
        'r_safe': r_safe,
        'n_total': all_forbidden,
        'pruned_conflicts': pruned,
    }

  def format_conditioning_context(
      self,
      acdus: Sequence[Mapping[str, Any]],
      config: AcduAblationConfig | None = None,
  ) -> str:
    """Formats the retrieved clinical context according to the ablation regime."""
    cfg = config or AcduAblationConfig()
    if cfg.conditioning_regime == 'zero_shot' or not acdus:
      return ''

    if cfg.conditioning_regime == 'naive_pdf_rag':
      chunks = []
      for u in acdus:
        title = u.get('topic') or u.get('title') or ''
        actions_prose = '. '.join(_extract_required_actions(u))
        chunks.append(f'Excerpt ({title}): {actions_prose}.')
      return '\n\n'.join(chunks)

    if cfg.conditioning_regime == 'hierarchical_rag':
      chunks = []
      for u in acdus:
        module = str(u.get('domain') or u.get('module') or '').upper()
        title = u.get('topic') or u.get('title') or ''
        header = f"[{module} | {u.get('id')}] {title}"
        actions = '\n'.join(f'- {a}' for a in _extract_required_actions(u))
        chunks.append(f'{header}\n{actions}')
      return '\n\n'.join(chunks)

    resolved = self.resolve_deontic_bundle(acdus, cfg)
    lines = ['### CERTIFIED KENYA eCHIS aCDU PROTOCOL CONSTRAINTS']
    lines.append(
        'Active aCDU IDs: ' + ', '.join(str(i) for i in resolved['acdu_ids'])
    )
    lines.append('\n**MANDATED CLINICAL ACTIONS (R_safe):**')
    for r in resolved['r_safe']:
      lines.append(f'- {r}')

    if cfg.include_negative_set and resolved['n_total']:
      lines.append(
          '\n**STRICTLY FORBIDDEN ACTIONS (N_total — NEVER VIOLATE):**'
      )
      for n in resolved['n_total']:
        lines.append(f'- {n}')

    if not cfg.compress_tokens:
      lines.append('\n**EXTENDED GUIDELINE COMMENTARY:**')
      for u in acdus:
        chunk = (
            u.get('prompt_injection_chunk')
            or u.get('compressed_prompt_chunk')
            or ''
        )
        lines.append(f'- {chunk}')

    return '\n'.join(lines)
