#!/usr/bin/env python3
"""
compile_echis_sqlite.py
=======================
Compiles the 50 Kenya eCHIS Atomic Clinical Decision Units (aCDUs) into a
compact, zero-RAM SQLite FTS5 database asset (<300 KB).

Edge Design Rationale:
- Neural embedding models (e.g. EmbeddingGemma 740M) add 450-700 MB of RAM,
  triggering Android Low Memory Killer (LMK) on 2GB-3GB RAM phones.
- SQLite with Full-Text Search (FTS5) runs with near-zero (<0.5 MB) working RAM,
  executes sub-millisecond keyword/BM25 queries, and guarantees zero cold-start latency.
"""

import os
import json
import sqlite3
import sys

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "kenya_echis_acdu_registry.json")
OUTPUT_DB_PATH = os.path.join(os.path.dirname(__file__), "kenya_echis_acdus.db")

def compile_database(registry_path: str = REGISTRY_PATH, output_db_path: str = OUTPUT_DB_PATH):
    print(f"Loading aCDU Registry from {registry_path}...")
    with open(registry_path, "r", encoding="utf-8") as f:
        acdus = json.load(f)

    if os.path.exists(output_db_path):
        os.remove(output_db_path)

    conn = sqlite3.connect(output_db_path)
    cur = conn.cursor()

    # Enable WAL mode and synchronous normal for high edge read performance
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")

    # 1. Main relational table storing structured fields and raw JSON payload
    cur.execute("""
    CREATE TABLE acdu_records (
        id TEXT PRIMARY KEY,
        domain TEXT NOT NULL,
        topic TEXT NOT NULL,
        gender TEXT,
        min_age_months REAL,
        max_age_months REAL,
        min_gestation_weeks REAL,
        max_gestation_weeks REAL,
        patient_status TEXT,
        prompt_injection_chunk TEXT NOT NULL,
        negative_boundaries_json TEXT NOT NULL,
        mandated_actions_json TEXT NOT NULL,
        full_json TEXT NOT NULL
    );
    """)

    # 2. FTS5 Virtual Table for sub-millisecond BM25 keyword matching
    cur.execute("""
    CREATE VIRTUAL TABLE acdu_fts USING fts5(
        id UNINDEXED,
        topic,
        conditions,
        symptoms,
        danger_signs,
        actions,
        negative_boundaries,
        tokenize = 'porter ascii'
    );
    """)

    # Populate tables
    for acdu in acdus:
        acdu_id = acdu["id"]
        domain = acdu["domain"]
        topic = acdu["topic"]
        cohort = acdu.get("target_cohort", {})
        triggers = acdu.get("trigger_index", {})
        payload = acdu.get("clinical_payload", {})

        gender = cohort.get("gender", "any")
        min_age = cohort.get("min_age_months")
        max_age = cohort.get("max_age_months")
        min_gest = cohort.get("min_gestation_weeks")
        max_gest = cohort.get("max_gestation_weeks")
        patient_status = cohort.get("patient_status", "any")

        prompt_chunk = acdu.get("prompt_injection_chunk", "")
        neg_bounds = json.dumps(payload.get("negative_boundaries", []))
        mandated_actions = json.dumps(payload.get("mandated_chw_actions", []))
        full_json_str = json.dumps(acdu)

        # Insert into relational table
        cur.execute("""
        INSERT INTO acdu_records (
            id, domain, topic, gender, min_age_months, max_age_months,
            min_gestation_weeks, max_gestation_weeks, patient_status,
            prompt_injection_chunk, negative_boundaries_json, mandated_actions_json,
            full_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            acdu_id, domain, topic, gender, min_age, max_age,
            min_gest, max_gest, patient_status,
            prompt_chunk, neg_bounds, mandated_actions,
            full_json_str
        ))

        # Flatten search index tokens
        conditions_str = " ".join(triggers.get("conditions", []))
        symptoms_str = " ".join(triggers.get("symptoms", []))
        danger_signs_str = " ".join(payload.get("danger_signs", []))
        actions_str = " ".join(payload.get("mandated_chw_actions", []))
        negative_str = " ".join(payload.get("negative_boundaries", []))

        cur.execute("""
        INSERT INTO acdu_fts (
            id, topic, conditions, symptoms, danger_signs, actions, negative_boundaries
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            acdu_id, topic, conditions_str, symptoms_str, danger_signs_str, actions_str, negative_str
        ))

    # Create cohort indexes
    cur.execute("CREATE INDEX idx_cohort_domain ON acdu_records(domain);")
    cur.execute("CREATE INDEX idx_cohort_age ON acdu_records(min_age_months, max_age_months);")
    cur.execute("CREATE INDEX idx_cohort_gest ON acdu_records(min_gestation_weeks, max_gestation_weeks);")

    conn.commit()
    conn.close()

    db_size = os.path.getsize(output_db_path)
    print(f"Compilation complete: {len(acdus)} aCDUs indexed into {output_db_path}")
    print(f"Asset File Size: {db_size / 1024:.2f} KB (Target: < 300 KB)")
    return output_db_path

if __name__ == "__main__":
    compile_database()
