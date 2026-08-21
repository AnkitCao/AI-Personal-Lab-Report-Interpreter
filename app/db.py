"""SQLite access for demo-patient screens (Phase 1).

Database: 1. Data Extraction/health_interpreter.db
Queries: Project_Specification.md Section 21
Functions: Section 19.1

Does not read 0. Data Resources (raw MIMIC CSVs).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "1. Data Extraction" / "health_interpreter.db"

# Classroom walkthroughs: outpatient-checkup shape, not ICU extremes.
# Picked from real app_encounters rows with full 4-panel coverage.
CURATED_DEMOS = [
    {
        "subject_id": 17689026,
        "hadm_id": 21978998,
        "scenario": "Patient 1 - All Normal",
        "notes": "Clean annual-checkup walkthrough. No HIGH or LOW results.",
    },
    {
        "subject_id": 10749718,
        "hadm_id": 28366444,
        "scenario": "Patient 2 - Mild A1C",
        "notes": "A1C 6.3% and glucose 122 mg/dL — a typical first-look report.",
    },
    {
        "subject_id": 11201977,
        "hadm_id": 28675357,
        "scenario": "Patient 3 - High Lipids",
        "notes": "A1C, LDL, cholesterol, triglycerides, and glucose above range.",
    },
]

DEMO_ENCOUNTERS_SQL = """
SELECT *
FROM app_encounters
WHERE has_cbc = 1 AND has_metabolic = 1
AND has_lipid = 1 AND has_a1c = 1
ORDER BY abnormal_result_count DESC, biomarker_count DESC;
"""

LAB_RESULTS_SQL = """
SELECT *
FROM app_lab_results
WHERE subject_id = ? AND hadm_id = ?
ORDER BY lab_group, test_name, charttime;
"""

ENCOUNTER_META_SQL = """
SELECT *
FROM app_encounters
WHERE subject_id = ? AND hadm_id = ?;
"""

ABNORMAL_RESULTS_SQL = """
SELECT test_name, lab_group, value_num, value_unit,
ref_range_lower, ref_range_upper, status, charttime, knowledge_source
FROM app_lab_results
WHERE subject_id = ? AND hadm_id = ?
AND status IN ('HIGH', 'LOW', 'ABNORMAL')
ORDER BY lab_group, test_name;
"""


def get_connection() -> sqlite3.Connection:
    """Open a read-only SQLite connection to health_interpreter.db."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Expected '1. Data Extraction/health_interpreter.db' next to the App/ folder."
        )

    uri = DB_PATH.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_demo_encounters(filters: dict | None = None) -> pd.DataFrame:
    """Return app_encounters rows for Screen 1's demo picker.

    Default SQL is the full-panel query from Section 21.
    Optional filters: min_abnormal, max_abnormal, full_panels_only (bool),
    and individual panel flags has_cbc / has_metabolic / has_lipid / has_a1c.
    """
    conn = get_connection()
    try:
        if not filters:
            return pd.read_sql_query(DEMO_ENCOUNTERS_SQL, conn)

        where: list[str] = []
        params: list[object] = []

        full_panels_only = filters.get("full_panels_only", True)
        if full_panels_only:
            where.extend(
                [
                    "has_cbc = 1",
                    "has_metabolic = 1",
                    "has_lipid = 1",
                    "has_a1c = 1",
                ]
            )
        else:
            for col in ("has_cbc", "has_metabolic", "has_lipid", "has_a1c"):
                if filters.get(col) == 1:
                    where.append(f"{col} = 1")

        if filters.get("min_abnormal") is not None:
            where.append("abnormal_result_count >= ?")
            params.append(filters["min_abnormal"])
        if filters.get("max_abnormal") is not None:
            where.append("abnormal_result_count <= ?")
            params.append(filters["max_abnormal"])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"""
            SELECT *
            FROM app_encounters
            {where_sql}
            ORDER BY abnormal_result_count DESC, biomarker_count DESC;
        """
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def get_lab_results(subject_id: int, hadm_id: int) -> pd.DataFrame:
    """Return all app_lab_results rows for one encounter (Screen 2)."""
    conn = get_connection()
    try:
        return pd.read_sql_query(
            LAB_RESULTS_SQL, conn, params=(int(subject_id), int(hadm_id))
        )
    finally:
        conn.close()


def get_abnormal_results(subject_id: int, hadm_id: int) -> pd.DataFrame:
    """HIGH / LOW / ABNORMAL rows for the LLM prompt (Section 21)."""
    conn = get_connection()
    try:
        return pd.read_sql_query(
            ABNORMAL_RESULTS_SQL, conn, params=(int(subject_id), int(hadm_id))
        )
    finally:
        conn.close()


def encounter_keys_for_finding(finding: str) -> set[tuple[int, int]] | None:
    """Encounter keys matching a HIGH/LOW lab pattern (not a diagnosis)."""
    clauses = {
        "High A1C": "test_name = 'Hemoglobin A1c' AND status = 'HIGH'",
        "High glucose": "test_name = 'Glucose' AND status = 'HIGH'",
        "High lipids": "lab_group = 'LIPID' AND status = 'HIGH'",
        "High creatinine": "test_name = 'Creatinine' AND status = 'HIGH'",
        "Low hemoglobin": "test_name = 'Hemoglobin' AND status = 'LOW'",
        "No HIGH / LOW": None,
    }
    if finding not in clauses:
        return None
    conn = get_connection()
    try:
        if finding == "No HIGH / LOW":
            rows = conn.execute(
                """
                SELECT subject_id, hadm_id
                FROM app_encounters
                WHERE abnormal_result_count = 0
                """
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT DISTINCT subject_id, hadm_id
                FROM app_lab_results
                WHERE {clauses[finding]}
                """
            ).fetchall()
        return {(int(r[0]), int(r[1])) for r in rows}
    finally:
        conn.close()


def get_encounter_meta(subject_id: int, hadm_id: int) -> dict | None:
    """Return the single app_encounters row for the sidebar summary."""
    conn = get_connection()
    try:
        row = conn.execute(
            ENCOUNTER_META_SQL, (int(subject_id), int(hadm_id))
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
