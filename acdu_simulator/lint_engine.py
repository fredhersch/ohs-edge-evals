#!/usr/bin/env python3
"""Linter and Token Budget Estimator for the aCDU Clinical Simulator.
Provides real-time feedback as the user edits an aCDU in the editor.
"""

import re
from typing import Dict, List, Any

MAX_TOKEN_BUDGET = 180
WARNING_TOKEN_THRESHOLD = 150

ACTIONABLE_NEGATIVE_MARKERS = [
    "never", "do not", "don't", "strictly", "contraindicated", "contraindication",
    "contraindications", "prohibit", "prohibited", "avoid", "stop", "withhold",
    "discontinue", "absolutely no", "must not", "should not", "zero", "forbidden", "refuse"
]

def estimate_tokens(text: str) -> int:
    """Estimates BPE token count for Gemma/Llama models (~3.8 chars per token)."""
    words = len(re.findall(r'\b\w+\b', text))
    punctuation = len(re.findall(r'[^\w\s]', text))
    char_est = len(text) / 3.8
    return int(max(words + (punctuation * 0.5), char_est))

def format_prompt_chunk(cdu: Dict[str, Any]) -> str:
    """Renders the standard prompt chunk format for an aCDU."""
    actions = " ".join(cdu.get("mandated_actions", []))
    negs = " ".join(cdu.get("negative_boundaries", []))
    cid = cdu.get("id", "CDU-DRAFT")
    criteria = cdu.get("entry_criteria", "")
    return (
        f"[{cid}]\n"
        f"CONDITION: {criteria}\n"
        f"GUIDELINE ACTIONS: {actions}\n"
        f"NEGATIVE BOUNDARIES: {negs}"
    )

def lint_cdu(cdu: Dict[str, Any]) -> Dict[str, Any]:
    """Lints an in-memory aCDU dict and returns status, token count, warnings, and errors."""
    issues = []
    chunk = format_prompt_chunk(cdu)
    toks = estimate_tokens(chunk)
    
    # 1. Token Budget
    if toks > MAX_TOKEN_BUDGET:
        issues.append({
            "level": "error",
            "message": f"Token budget exceeded ({toks} tokens > {MAX_TOKEN_BUDGET} token ceiling).",
            "field": "token_budget"
        })
    elif toks > WARNING_TOKEN_THRESHOLD:
        issues.append({
            "level": "warning",
            "message": f"Token budget high ({toks} tokens, approaching {MAX_TOKEN_BUDGET}). Consider concise phrasing.",
            "field": "token_budget"
        })

    # 2. Structural Requirements
    cid = cdu.get("id", "").strip()
    if not cid:
        issues.append({"level": "error", "message": "aCDU ID is required.", "field": "id"})
        
    criteria = cdu.get("entry_criteria", "").strip()
    if len(criteria) < 8:
        issues.append({"level": "warning", "message": "Clinical trigger criteria is very brief.", "field": "entry_criteria"})

    actions = [a for a in cdu.get("mandated_actions", []) if str(a).strip()]
    if not actions:
        issues.append({"level": "error", "message": "At least one mandated clinical action is required.", "field": "mandated_actions"})

    negs = [n for n in cdu.get("negative_boundaries", []) if str(n).strip()]
    if not negs:
        issues.append({"level": "error", "message": "At least one negative boundary (STOP / DO NOT) is required for safety clamping.", "field": "negative_boundaries"})
    else:
        # Check for actionable negative words
        combined_negs = " ".join(negs).lower()
        has_negative_marker = any(m in combined_negs for m in ACTIONABLE_NEGATIVE_MARKERS)
        if not has_negative_marker:
            issues.append({
                "level": "warning",
                "message": "Negative boundaries should include explicit refusal markers (e.g., 'STOP: Do NOT', 'Never', 'Strictly Contraindicated').",
                "field": "negative_boundaries"
            })

    tier = cdu.get("priority_tier", 2)
    if tier not in [1, 2, 3]:
        issues.append({"level": "error", "message": "Priority tier must be 1 (Fatal/Veto), 2 (Organ), or 3 (Symptom).", "field": "priority_tier"})

    has_error = any(i["level"] == "error" for i in issues)
    has_warning = any(i["level"] == "warning" for i in issues)
    
    return {
        "valid": not has_error,
        "token_count": toks,
        "max_tokens": MAX_TOKEN_BUDGET,
        "issues": issues,
        "status": "error" if has_error else ("warning" if has_warning else "clean"),
        "prompt_chunk": chunk
    }

if __name__ == "__main__":
    sample = {
        "id": "CDU-TEST",
        "entry_criteria": "Patient with cough and fever",
        "mandated_actions": ["Give oral paracetamol"],
        "negative_boundaries": ["Do not administer adult dose to child"],
        "priority_tier": 2
    }
    print(lint_cdu(sample))
