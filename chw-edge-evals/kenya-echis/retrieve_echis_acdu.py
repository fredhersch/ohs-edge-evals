#!/usr/bin/env python3
"""
retrieve_echis_acdu.py
======================
Zero-RAM On-Device Clinical Protocol Retriever for Kenya eCHIS.

Executes sub-millisecond BM25 keyword matching with deterministic cohort
filtering over the pre-indexed SQLite FTS5 database asset (`kenya_echis_acdus.db`).

Usage:
    from retrieve_echis_acdu import retrieve_acdus
    results = retrieve_acdus(
        query="fast breathing chest indrawing fever",
        age_months=14,
        gender="male",
        top_k=2
    )
"""

import os
import json
import sqlite3
import time
import re
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "kenya_echis_acdus.db")

def retrieve_acdus(
    query: str,
    age_months: Optional[float] = None,
    gestation_weeks: Optional[float] = None,
    gender: Optional[str] = None,
    patient_status: Optional[str] = None,
    domain_filter: Optional[str] = None,
    top_k: int = 2,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Retrieves the most clinically relevant aCDUs for a given patient encounter.
    
    Args:
        query: Free text or keywords describing symptoms/signs/conditions.
        age_months: Patient age in months (for pediatric/growth/immunization filtering).
        gestation_weeks: Gestational age in weeks (for pregnancy/ANC filtering).
        gender: "male", "female", or "other".
        patient_status: e.g. "pregnant", "postpartum", "newborn", "adolescent", etc.
        domain_filter: Optional domain constraint, e.g. "02_mnh", "03_iccm".
        top_k: Number of aCDUs to return (default: 2, ensuring prompt fits within 500 tokens).
        db_path: Path to the SQLite FTS5 database.

    Returns:
        Dict containing:
            - matches: List of retrieved aCDU dicts (with metadata, prompt chunk, negative bounds)
            - latency_ms: Query execution time in milliseconds
            - query: Sanitized query string used
    """
    t_start = time.perf_counter()

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}. Run compile_echis_sqlite.py first.")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Extract clean alphanumeric words and filter standard English stopwords
    stopwords = {
        'has', 'of', 'and', 'is', 'at', 'too', 'to', 'the', 'for', 'with', 'from',
        'her', 'his', 'this', 'that', 'per', 'day', 'days', 'have', 'had', 'been',
        'who', 'what', 'when', 'which', 'was', 'were', 'also', 'she', 'him', 'them'
    }
    tokens = [w.lower() for w in re.findall(r'\b[a-zA-Z0-9]{3,}\b', query) if w.lower() not in stopwords]
    if not tokens:
        tokens = ["malaria"] # Fallback token

    # FTS5 syntax: MATCH 'token1 OR token2 OR ...'
    fts_match_expr = " OR ".join(tokens)

    # Cohort filtering SQL clauses
    cohort_clauses = []
    cohort_params = []

    if domain_filter:
        cohort_clauses.append("r.domain = ?")
        cohort_params.append(domain_filter)

    if gender:
        g = gender.lower()
        if g in ("male", "female"):
            cohort_clauses.append("(r.gender IS NULL OR r.gender IN ('all', 'any', 'both', 'neonate') OR r.gender = ?)")
            cohort_params.append(g)

    if age_months is not None:
        cohort_clauses.append("""(
            (r.min_age_months IS NULL AND r.max_age_months IS NULL) OR
            (r.min_age_months <= ? AND r.max_age_months >= ?) OR
            (r.min_age_months <= ? AND r.max_age_months IS NULL) OR
            (r.min_age_months IS NULL AND r.max_age_months >= ?)
        )""")
        cohort_params.extend([age_months, age_months, age_months, age_months])
        # If age is under 5 years (< 60m), exclude adult/maternal gestation protocols unless specifically pregnant
        if age_months < 60 and not gestation_weeks:
            cohort_clauses.append("(r.min_gestation_weeks IS NULL AND (r.domain != '02_mnh' OR r.patient_status IN ('newborn', 'sick_newborn', 'infant', 'infant_or_child')))")

    if gestation_weeks is not None:
        cohort_clauses.append("""(
            (r.min_gestation_weeks IS NULL AND r.max_gestation_weeks IS NULL) OR
            (r.min_gestation_weeks <= ? AND r.max_gestation_weeks >= ?) OR
            (r.min_gestation_weeks <= ? AND r.max_gestation_weeks IS NULL) OR
            (r.min_gestation_weeks IS NULL AND r.max_gestation_weeks >= ?)
        )""")
        cohort_params.extend([gestation_weeks, gestation_weeks, gestation_weeks, gestation_weeks])

    if patient_status:
        cohort_clauses.append("(r.patient_status IS NULL OR r.patient_status IN ('all', 'any', 'community_member') OR r.patient_status LIKE ?)")
        cohort_params.append(f"%{patient_status.lower()}%")

    where_cohort = (" AND " + " AND ".join(cohort_clauses)) if cohort_clauses else ""

    # FTS5 query with BM25 ranking (lower score = higher relevance in SQLite bm25())
    # Column weights: topic=3.0, conditions=5.0, symptoms=4.0, danger_signs=4.0, actions=1.0, negative_boundaries=1.0
    sql = f"""
    SELECT 
        r.id,
        r.domain,
        r.topic,
        r.prompt_injection_chunk,
        r.negative_boundaries_json,
        r.mandated_actions_json,
        r.full_json,
        bm25(acdu_fts, 3.0, 5.0, 4.0, 4.0, 1.0, 1.0) AS rank_score
    FROM acdu_fts f
    JOIN acdu_records r ON f.id = r.id
    WHERE acdu_fts MATCH ?
    {where_cohort}
    ORDER BY rank_score ASC
    LIMIT ?;
    """

    params = [fts_match_expr] + cohort_params + [top_k]
    cur.execute(sql, params)
    rows = cur.fetchall()

    matches = []
    for row in rows:
        acdu_id, domain, topic, prompt_chunk, neg_bounds_raw, actions_raw, full_json_raw, rank = row
        matches.append({
            "id": acdu_id,
            "domain": domain,
            "topic": topic,
            "rank_score": rank,
            "prompt_injection_chunk": prompt_chunk,
            "negative_boundaries": json.loads(neg_bounds_raw),
            "mandated_actions": json.loads(actions_raw),
            "full_acdu": json.loads(full_json_raw)
        })

    conn.close()
    t_end = time.perf_counter()
    latency_ms = (t_end - t_start) * 1000.0

    return {
        "query": fts_match_expr,
        "matches": matches,
        "match_count": len(matches),
        "latency_ms": round(latency_ms, 3)
    }

if __name__ == "__main__":
    print("Testing zero-RAM edge aCDU retrieval...")
    test_cases = [
        {"query": "fever chills positive mrdt uncomplicated", "age_months": 36, "gender": "female"},
        {"query": "fast breathing cough chest indrawing", "age_months": 18, "gender": "male"},
        {"query": "severe headache blurred vision high blood pressure", "gestation_weeks": 32, "gender": "female", "patient_status": "pregnant"},
        {"query": "watery diarrhea sunken eyes cholera dehydration", "age_months": 48, "gender": "male"}
    ]

    for tc in test_cases:
        res = retrieve_acdus(
            query=tc["query"],
            age_months=tc.get("age_months"),
            gestation_weeks=tc.get("gestation_weeks"),
            gender=tc.get("gender"),
            patient_status=tc.get("patient_status"),
            top_k=2
        )
        print(f"\n--- Query: '{tc['query']}' (Age: {tc.get('age_months')}m, Gest: {tc.get('gestation_weeks')}w) ---")
        print(f"Latency: {res['latency_ms']} ms | Matches: {res['match_count']}")
        for m in res["matches"]:
            print(f"  -> [{m['id']}] {m['topic']} (BM25 score: {m['rank_score']:.4f})")
            print(f"     Negative Boundaries: {m['negative_boundaries'][:2]}")
