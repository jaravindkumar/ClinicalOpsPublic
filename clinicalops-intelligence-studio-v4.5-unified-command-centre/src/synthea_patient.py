from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from src.trial_ops import resolve_synthea_dir, synthea_status


def _q(path: Path) -> str:
    return str(path).replace("'", "''")


def load_patient_index(synthea_dir: Optional[str] = None) -> pd.DataFrame:
    """Load only the lightweight patient table for patient selection."""
    root = resolve_synthea_dir(synthea_dir)
    status = synthea_status(str(root))
    if not status["ready"]:
        raise FileNotFoundError(f"Synthea CSV directory is not ready: {status}")
    path = root / "patients.csv"
    con = duckdb.connect()
    df = con.execute(
        f"""
        SELECT CAST(Id AS VARCHAR) patient_id,
               coalesce(CAST(FIRST AS VARCHAR),'') first_name,
               coalesce(CAST(LAST AS VARCHAR),'') last_name,
               TRY_CAST(BIRTHDATE AS DATE) birthdate,
               CAST(GENDER AS VARCHAR) gender,
               CAST(RACE AS VARCHAR) race,
               CAST(ETHNICITY AS VARCHAR) ethnicity,
               CAST(CITY AS VARCHAR) city,
               CAST(STATE AS VARCHAR) state
        FROM read_csv_auto('{_q(path)}', header=true, all_varchar=true)
        ORDER BY last_name, first_name, patient_id
        """
    ).df()
    con.close()
    today = date.today()
    if not df.empty:
        df["age"] = df["birthdate"].apply(
            lambda d: today.year - d.year - ((today.month, today.day) < (d.month, d.day)) if pd.notna(d) else None
        )
        df["display"] = df.apply(
            lambda r: f"{r['first_name']} {r['last_name']} · age {int(r['age']) if pd.notna(r['age']) else '?'} · {r['gender']} · {r['patient_id'][:8]}", axis=1
        )
    return df


def _recent_rows(con, path: Path, patient_id: str, select_sql: str, order_col: str, limit: int = 8) -> pd.DataFrame:
    return con.execute(
        f"""
        SELECT {select_sql}
        FROM read_csv_auto('{_q(path)}', header=true, all_varchar=true)
        WHERE CAST(PATIENT AS VARCHAR) = ?
        ORDER BY TRY_CAST({order_col} AS TIMESTAMP) DESC NULLS LAST
        LIMIT {int(limit)}
        """,
        [patient_id],
    ).df()


def build_patient_clinical_text(patient_id: str, synthea_dir: Optional[str] = None) -> tuple[str, dict]:
    """Create a compact clinical narrative from one real Synthea synthetic patient.

    The text is generated from the CSV rows; no LLM is used here.
    """
    root = resolve_synthea_dir(synthea_dir)
    status = synthea_status(str(root))
    if not status["ready"]:
        raise FileNotFoundError(f"Synthea CSV directory is not ready: {status}")

    con = duckdb.connect()
    patient = con.execute(
        f"""
        SELECT CAST(Id AS VARCHAR) patient_id,
               coalesce(CAST(FIRST AS VARCHAR),'') first_name,
               coalesce(CAST(LAST AS VARCHAR),'') last_name,
               TRY_CAST(BIRTHDATE AS DATE) birthdate,
               CAST(GENDER AS VARCHAR) gender,
               CAST(RACE AS VARCHAR) race,
               CAST(ETHNICITY AS VARCHAR) ethnicity,
               CAST(CITY AS VARCHAR) city,
               CAST(STATE AS VARCHAR) state
        FROM read_csv_auto('{_q(root / 'patients.csv')}', header=true, all_varchar=true)
        WHERE CAST(Id AS VARCHAR) = ?
        LIMIT 1
        """,
        [patient_id],
    ).df()
    if patient.empty:
        con.close()
        raise ValueError(f"Patient {patient_id} not found")

    conditions = _recent_rows(con, root / "conditions.csv", patient_id,
                              "START, STOP, DESCRIPTION, CODE", "START", 10)
    encounters = _recent_rows(con, root / "encounters.csv", patient_id,
                              "START, STOP, ENCOUNTERCLASS, DESCRIPTION, REASONDESCRIPTION", "START", 8)

    observations = pd.DataFrame()
    if (root / "observations.csv").exists():
        observations = _recent_rows(con, root / "observations.csv", patient_id,
                                    "DATE, CATEGORY, DESCRIPTION, VALUE, UNITS", "DATE", 12)
    medications = pd.DataFrame()
    if (root / "medications.csv").exists():
        medications = _recent_rows(con, root / "medications.csv", patient_id,
                                   "START, STOP, DESCRIPTION, REASONDESCRIPTION", "START", 8)
    procedures = pd.DataFrame()
    if (root / "procedures.csv").exists():
        procedures = _recent_rows(con, root / "procedures.csv", patient_id,
                                  "START, STOP, DESCRIPTION, REASONDESCRIPTION", "START", 8)
    con.close()

    p = patient.iloc[0]
    age = None
    if pd.notna(p.birthdate):
        today = date.today()
        age = today.year - p.birthdate.year - ((today.month, today.day) < (p.birthdate.month, p.birthdate.day))

    lines = [
        "Synthea synthetic EHR patient summary.",
        f"Patient ID: {patient_id}.",
        f"Demographics: {age if age is not None else 'unknown'} years old, gender {p.gender}, race {p.race}, ethnicity {p.ethnicity}; location {p.city}, {p.state}.",
    ]

    def add_section(title: str, df: pd.DataFrame, formatter):
        if df.empty:
            return
        lines.append(f"{title}:")
        for _, row in df.iterrows():
            lines.append("- " + formatter(row))

    add_section("Recent/recorded conditions", conditions,
                lambda r: f"{r.get('DESCRIPTION','')} (start {r.get('START','')}, stop {r.get('STOP','') or 'ongoing/unknown'})")
    add_section("Recent encounters", encounters,
                lambda r: f"{r.get('START','')}: {r.get('ENCOUNTERCLASS','')} - {r.get('DESCRIPTION','')}; reason {r.get('REASONDESCRIPTION','') or 'not recorded'}")
    add_section("Recent observations", observations,
                lambda r: f"{r.get('DATE','')}: {r.get('DESCRIPTION','')} = {r.get('VALUE','')} {r.get('UNITS','')}")
    add_section("Recent medications", medications,
                lambda r: f"{r.get('START','')}: {r.get('DESCRIPTION','')}; reason {r.get('REASONDESCRIPTION','') or 'not recorded'}")
    add_section("Recent procedures", procedures,
                lambda r: f"{r.get('START','')}: {r.get('DESCRIPTION','')}; reason {r.get('REASONDESCRIPTION','') or 'not recorded'}")

    text = "\n".join(lines)
    metadata = {
        "patient": patient.to_dict(orient="records")[0],
        "condition_rows": len(conditions),
        "encounter_rows": len(encounters),
        "observation_rows": len(observations),
        "medication_rows": len(medications),
        "procedure_rows": len(procedures),
    }
    return text, metadata

def get_patient_snapshot(patient_id: str, synthea_dir: Optional[str] = None) -> dict:
    """Return structured Synthea patient details for human review. No LLM is used."""
    root = resolve_synthea_dir(synthea_dir)
    if not synthea_status(str(root))["ready"]:
        raise FileNotFoundError(str(root))
    con = duckdb.connect()
    patient = con.execute(
        f"""SELECT CAST(Id AS VARCHAR) patient_id, TRY_CAST(BIRTHDATE AS DATE) birthdate,
                   CAST(GENDER AS VARCHAR) sex, CAST(RACE AS VARCHAR) race,
                   CAST(ETHNICITY AS VARCHAR) ethnicity, CAST(CITY AS VARCHAR) city, CAST(STATE AS VARCHAR) state
            FROM read_csv_auto('{_q(root / 'patients.csv')}', header=true, all_varchar=true)
            WHERE CAST(Id AS VARCHAR)=? LIMIT 1""", [patient_id]).df()
    if patient.empty:
        con.close(); raise ValueError(f"Patient {patient_id} not found")
    p = patient.iloc[0]
    today = date.today()
    age = today.year-p.birthdate.year-((today.month,today.day)<(p.birthdate.month,p.birthdate.day)) if pd.notna(p.birthdate) else None
    conditions = _recent_rows(con, root/'conditions.csv', patient_id, 'START, STOP, DESCRIPTION', 'START', 8)
    encounters = _recent_rows(con, root/'encounters.csv', patient_id, 'START, ENCOUNTERCLASS, DESCRIPTION, REASONDESCRIPTION', 'START', 6)
    observations = _recent_rows(con, root/'observations.csv', patient_id, 'DATE, DESCRIPTION, VALUE, UNITS', 'DATE', 10) if (root/'observations.csv').exists() else pd.DataFrame()
    medications = _recent_rows(con, root/'medications.csv', patient_id, 'START, STOP, DESCRIPTION, REASONDESCRIPTION', 'START', 6) if (root/'medications.csv').exists() else pd.DataFrame()
    procedures = _recent_rows(con, root/'procedures.csv', patient_id, 'START, DESCRIPTION, REASONDESCRIPTION', 'START', 6) if (root/'procedures.csv').exists() else pd.DataFrame()
    con.close()
    return {
        'demographics': {'patient_id':patient_id,'age':age,'sex':p.sex,'race':p.race,'ethnicity':p.ethnicity,'city':p.city,'state':p.state},
        'conditions':conditions, 'encounters':encounters, 'observations':observations,
        'medications':medications, 'procedures':procedures
    }
