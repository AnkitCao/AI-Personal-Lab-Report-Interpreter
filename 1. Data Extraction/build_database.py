"""
build_database.py

Builds the final SQLite database health_interpreter.db for the
Streamlit / OpenAI API prototype.

Design (see PROJECT_PLAN.md, Section 4):
- Only 2 final tables are kept:
    - app_lab_results : one row per lab result (core table, everything
      the app reads from)
    - app_encounters   : one row per encounter, precomputed aggregates,
      used only for demo-patient selection
  Two other tables (patient profile, biomarker dictionary) were dropped
  because their columns are already flattened into app_lab_results, and
  diagnoses were dropped because they are a different grain (many rows
  per encounter) that cannot be joined into a lab-result-level table
  without duplicating rows, and the MVP does not feed them to the LLM.
- pandas is only used to load the CSVs and fix source-data issues that
  would otherwise break a plain SQL import (see step 1). The actual
  join / derivation logic is plain SQL (step 2-3), run against SQLite.

Run (from the Data/ folder):
    python build_database.py
"""

import os
import sqlite3
import pandas as pd

# raw CSVs live one level up, in NLP Project/; this script and its output
# (health_interpreter.db) live in NLP Project/Data/
DATA_DIR = ".."
DB_PATH = "health_interpreter.db"

PATIENTS_CSV = f"{DATA_DIR}/patients.csv"
LABEVENTS_CSV = f"{DATA_DIR}/labevents_sample.csv"
ITEMIDS_CSV = f"{DATA_DIR}/labevents_sample_itemids.csv"

# always rebuild from scratch: delete any existing .db file first so a
# stale/older schema (leftover tables from a previous version of this
# script) can never linger in the output
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)


# =========================
# 1. Load CSVs + fix source-data issues
#    (necessary before SQL can join them cleanly; not business logic)
# =========================

print("Reading CSVs ...")

labevents = pd.read_csv(LABEVENTS_CSV, low_memory=False)
itemids = pd.read_csv(ITEMIDS_CSV)
patients = pd.read_csv(PATIENTS_CSV, low_memory=False)

# hadm_id is stored as a float in the source file (e.g. 24120560.0) -> cast to int
labevents["hadm_id"] = labevents["hadm_id"].astype("int64")

# 5 exact duplicate rows exist in the raw sample (see PROJECT_PLAN.md Section 3)
before = len(labevents)
labevents = labevents.drop_duplicates()
print(f"labevents_sample deduplicated: {before} -> {len(labevents)} rows")

# keep only the patients that actually appear in the lab sample (499, not 364K)
sample_subjects = set(labevents["subject_id"].unique())
patients = patients[patients["subject_id"].isin(sample_subjects)].copy()
patients = patients[["subject_id", "gender", "anchor_age", "anchor_year"]]

conn = sqlite3.connect(DB_PATH)
labevents.to_sql("stg_labevents", conn, if_exists="replace", index=False)
itemids.to_sql("stg_itemids", conn, if_exists="replace", index=False)
patients.to_sql("stg_patients", conn, if_exists="replace", index=False)


# =========================
# 2. app_lab_results — the actual JOIN, in SQL
# =========================

print("Building app_lab_results ...")

conn.executescript(
    """
    DROP TABLE IF EXISTS app_lab_results;

    CREATE TABLE app_lab_results AS
    SELECT
        l.subject_id,
        l.hadm_id,
        p.gender,
        p.anchor_age,
        p.anchor_year,
        l.charttime,
        l.itemid,
        i.label AS mimic_test_name,
        -- canonical, cleaner test name for the app / LLM
        CASE
            WHEN LOWER(i.label) LIKE '%hemoglobin a1c%'
              OR LOWER(i.label) LIKE '%glycated hemoglobin%'
              OR LOWER(i.label) LIKE '%glycohemoglobin%'
                THEN 'Hemoglobin A1c'
            WHEN i.label = 'Cholesterol, HDL' THEN 'HDL Cholesterol'
            WHEN i.label = 'Cholesterol, LDL, Calculated' THEN 'LDL Cholesterol - Calculated'
            WHEN i.label = 'Cholesterol, LDL, Measured' THEN 'LDL Cholesterol - Measured'
            WHEN i.label = 'Cholesterol, Total' THEN 'Total Cholesterol'
            WHEN i.label = 'Bilirubin, Total' THEN 'Total Bilirubin'
            WHEN i.label = 'Calcium, Total' THEN 'Total Calcium'
            ELSE i.label
        END AS test_name,
        i.lab_group,
        l.value AS value_text,
        l.valuenum AS value_num,
        l.valueuom AS value_unit,
        l.ref_range_lower,
        l.ref_range_upper,
        l.flag AS mimic_flag,
        -- deterministic status: the database decides the fact, the LLM only explains it
        CASE
            WHEN l.valuenum IS NULL THEN 'UNKNOWN'
            WHEN l.ref_range_lower IS NOT NULL AND l.valuenum < l.ref_range_lower THEN 'LOW'
            WHEN l.ref_range_upper IS NOT NULL AND l.valuenum > l.ref_range_upper THEN 'HIGH'
            WHEN l.ref_range_lower IS NOT NULL OR l.ref_range_upper IS NOT NULL THEN 'NORMAL'
            WHEN LOWER(COALESCE(l.flag, '')) = 'abnormal' THEN 'ABNORMAL'
            ELSE 'UNKNOWN'
        END AS status,
        'Curated Database' AS knowledge_source
    FROM stg_labevents l
    INNER JOIN stg_itemids i ON l.itemid = i.itemid
    LEFT JOIN stg_patients p ON l.subject_id = p.subject_id;
    """
)

# MIMIC left some lipid ranges blank (all Cholesterol Ratio rows; some HDL).
# Fill published adult fallbacks, then recompute status for those rows only.
print("Filling curated fallback ranges for blank lipid rows ...")
conn.executescript(
    """
    UPDATE app_lab_results
    SET ref_range_upper = 5.0
    WHERE test_name = 'Cholesterol Ratio (Total/HDL)'
      AND ref_range_lower IS NULL
      AND ref_range_upper IS NULL;

    UPDATE app_lab_results
    SET ref_range_lower = 41.0,
        ref_range_upper = 999.0
    WHERE test_name = 'HDL Cholesterol'
      AND ref_range_lower IS NULL
      AND ref_range_upper IS NULL;

    UPDATE app_lab_results
    SET status = CASE
        WHEN value_num IS NULL THEN 'UNKNOWN'
        WHEN ref_range_lower IS NOT NULL AND value_num < ref_range_lower THEN 'LOW'
        WHEN ref_range_upper IS NOT NULL AND value_num > ref_range_upper THEN 'HIGH'
        WHEN ref_range_lower IS NOT NULL OR ref_range_upper IS NOT NULL THEN 'NORMAL'
        WHEN LOWER(COALESCE(mimic_flag, '')) = 'abnormal' THEN 'ABNORMAL'
        ELSE 'UNKNOWN'
    END
    WHERE test_name IN ('Cholesterol Ratio (Total/HDL)', 'HDL Cholesterol');
    """
)


# =========================
# 3. app_encounters — aggregated from app_lab_results, in SQL
#    (different grain: one row per encounter, needed for demo-patient
#    selection; can't be merged into app_lab_results without duplicating rows)
# =========================

print("Building app_encounters ...")

conn.executescript(
    """
    DROP TABLE IF EXISTS app_encounters;

    CREATE TABLE app_encounters AS
    SELECT
        subject_id,
        hadm_id,
        MAX(gender) AS gender,
        MAX(anchor_age) AS anchor_age,
        MIN(charttime) AS first_lab_time,
        MAX(charttime) AS last_lab_time,
        COUNT(*) AS lab_record_count,
        COUNT(DISTINCT test_name) AS biomarker_count,
        SUM(CASE WHEN status IN ('HIGH', 'LOW', 'ABNORMAL') THEN 1 ELSE 0 END) AS abnormal_result_count,
        MAX(CASE WHEN lab_group = 'CBC' THEN 1 ELSE 0 END) AS has_cbc,
        MAX(CASE WHEN lab_group = 'METABOLIC' THEN 1 ELSE 0 END) AS has_metabolic,
        MAX(CASE WHEN lab_group = 'LIPID' THEN 1 ELSE 0 END) AS has_lipid,
        MAX(CASE WHEN lab_group = 'A1C' THEN 1 ELSE 0 END) AS has_a1c
    FROM app_lab_results
    GROUP BY subject_id, hadm_id;
    """
)


# =========================
# 4. Indexes + drop staging tables
#    (only the 2 final tables should remain in the .db file)
# =========================

conn.executescript(
    """
    CREATE INDEX IF NOT EXISTS idx_lab_subject ON app_lab_results(subject_id);
    CREATE INDEX IF NOT EXISTS idx_lab_encounter ON app_lab_results(subject_id, hadm_id);
    CREATE INDEX IF NOT EXISTS idx_lab_test ON app_lab_results(test_name);
    CREATE INDEX IF NOT EXISTS idx_encounter_subject ON app_encounters(subject_id);

    DROP TABLE stg_labevents;
    DROP TABLE stg_itemids;
    DROP TABLE stg_patients;
    """
)
conn.commit()


# =========================
# 5. Verify
# =========================

print("\nFinal tables:")
for table in ["app_lab_results", "app_encounters"]:
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table}: {n} rows")

print("\nstatus breakdown:")
for status, n in conn.execute(
    "SELECT status, COUNT(*) FROM app_lab_results GROUP BY status ORDER BY COUNT(*) DESC"
):
    print(f"  {status}: {n}")

conn.close()
print(f"\nDatabase written: {DB_PATH}")
