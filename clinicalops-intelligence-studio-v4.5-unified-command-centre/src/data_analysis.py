from __future__ import annotations
from pathlib import Path
import duckdb
import pandas as pd
from src.trial_ops import resolve_synthea_dir, synthea_status


def _q(p: Path) -> str:
    return str(p).replace("'", "''")


def population_summary(synthea_dir: str) -> dict:
    root = resolve_synthea_dir(synthea_dir)
    if not synthea_status(str(root))["ready"]:
        raise FileNotFoundError(str(root))
    con = duckdb.connect()
    p = _q(root / "patients.csv")
    age_expr = "date_diff('year', try_cast(BIRTHDATE as date), current_date)"
    row = con.execute(f"""
        SELECT count(*) n,
               round(avg({age_expr}),1) avg_age,
               median({age_expr}) median_age,
               sum(CASE WHEN upper(GENDER)='F' THEN 1 ELSE 0 END) female,
               sum(CASE WHEN upper(GENDER)='M' THEN 1 ELSE 0 END) male
        FROM read_csv_auto('{p}', header=true, all_varchar=true)
    """).fetchone()
    con.close()
    return {"patients": int(row[0]), "avg_age": float(row[1] or 0), "median_age": float(row[2] or 0),
            "female": int(row[3] or 0), "male": int(row[4] or 0)}


def age_distribution(synthea_dir: str) -> pd.DataFrame:
    root = resolve_synthea_dir(synthea_dir); con = duckdb.connect()
    age = "date_diff('year', try_cast(BIRTHDATE as date), current_date)"
    df = con.execute(f"""
      SELECT CASE
        WHEN {age}<18 THEN '0–17' WHEN {age}<35 THEN '18–34' WHEN {age}<50 THEN '35–49'
        WHEN {age}<65 THEN '50–64' WHEN {age}<80 THEN '65–79' ELSE '80+' END age_band,
        count(*) patients
      FROM read_csv_auto('{_q(root/'patients.csv')}', header=true, all_varchar=true)
      GROUP BY 1 ORDER BY min({age})
    """).df(); con.close(); return df


def top_conditions(synthea_dir: str, n: int = 15) -> pd.DataFrame:
    root = resolve_synthea_dir(synthea_dir); con = duckdb.connect()
    df = con.execute(f"""
      SELECT DESCRIPTION condition, count(DISTINCT PATIENT) patients, count(*) records
      FROM read_csv_auto('{_q(root/'conditions.csv')}', header=true, all_varchar=true)
      WHERE DESCRIPTION IS NOT NULL GROUP BY 1 ORDER BY patients DESC LIMIT {int(n)}
    """).df(); con.close(); return df


def encounter_mix(synthea_dir: str) -> pd.DataFrame:
    root = resolve_synthea_dir(synthea_dir); con = duckdb.connect()
    df = con.execute(f"""
      SELECT coalesce(ENCOUNTERCLASS,'Unknown') encounter_class, count(*) encounters
      FROM read_csv_auto('{_q(root/'encounters.csv')}', header=true, all_varchar=true)
      GROUP BY 1 ORDER BY encounters DESC
    """).df(); con.close(); return df


def encounter_trend(synthea_dir: str, years: int = 5) -> pd.DataFrame:
    root = resolve_synthea_dir(synthea_dir); con = duckdb.connect()
    df = con.execute(f"""
      SELECT date_trunc('month', try_cast(START as timestamp)) AS month_start, count(*) AS encounter_count
      FROM read_csv_auto('{_q(root/'encounters.csv')}', header=true, all_varchar=true)
      WHERE try_cast(START as timestamp) >= current_date - INTERVAL '{int(years)} years'
      GROUP BY 1 ORDER BY 1
    """).df(); con.close(); return df


def data_volume(synthea_dir: str) -> pd.DataFrame:
    root = resolve_synthea_dir(synthea_dir); con = duckdb.connect(); rows=[]
    for fn in ["patients.csv","encounters.csv","conditions.csv","medications.csv","observations.csv","procedures.csv","imaging_studies.csv","claims.csv"]:
        p=root/fn
        if p.exists():
            n=con.execute(f"SELECT count(*) FROM read_csv_auto('{_q(p)}', header=true, all_varchar=true)").fetchone()[0]
            rows.append({"dataset":fn.replace('.csv','').replace('_',' ').title(),"records":int(n)})
    con.close(); return pd.DataFrame(rows).sort_values('records',ascending=False)


def cohort_profile(synthea_dir: str, members: pd.DataFrame, top_n: int = 15) -> dict:
    """Descriptive profile for a saved cohort, grounded in its persisted member IDs."""
    if members is None or members.empty:
        return {"summary": {"patients": 0, "median_age": 0, "female": 0, "male": 0},
                "ages": pd.DataFrame(columns=["age_band","patients"]),
                "conditions": pd.DataFrame(columns=["condition","patients","records"]),
                "mix": pd.DataFrame(columns=["encounter_class","encounters"]),
                "trend": pd.DataFrame(columns=["month_start","encounter_count"])}
    root = resolve_synthea_dir(synthea_dir)
    con = duckdb.connect()
    ids = members[["patient_id"]].drop_duplicates().copy()
    con.register("cohort_ids", ids)
    m = members.copy()
    n = len(m)
    med = float(pd.to_numeric(m["age"], errors="coerce").median() or 0)
    female = int(m["sex"].astype(str).str.upper().eq("F").sum())
    male = int(m["sex"].astype(str).str.upper().eq("M").sum())
    ages = con.execute("""
        SELECT CASE WHEN age<18 THEN '0–17' WHEN age<35 THEN '18–34' WHEN age<50 THEN '35–49'
                    WHEN age<65 THEN '50–64' WHEN age<80 THEN '65–79' ELSE '80+' END age_band,
               count(*) patients
        FROM (SELECT try_cast(age AS INTEGER) age FROM m) GROUP BY 1
        ORDER BY min(age)
    """).df() if False else None
    # Pandas is simpler for the persisted age values and avoids coupling to patients.csv DOB semantics.
    bins=[-1,17,34,49,64,79,1000]; labels=['0–17','18–34','35–49','50–64','65–79','80+']
    age_series=pd.to_numeric(m['age'],errors='coerce')
    cats=pd.cut(age_series,bins=bins,labels=labels)
    ages=cats.value_counts(sort=False).rename_axis('age_band').reset_index(name='patients')
    conditions = con.execute(f"""
        SELECT c.DESCRIPTION condition, count(DISTINCT c.PATIENT) patients, count(*) records
        FROM read_csv_auto('{_q(root/'conditions.csv')}', header=true, all_varchar=true) c
        INNER JOIN cohort_ids i ON cast(c.PATIENT as varchar)=i.patient_id
        WHERE c.DESCRIPTION IS NOT NULL GROUP BY 1 ORDER BY patients DESC LIMIT {int(top_n)}
    """).df()
    mix = con.execute(f"""
        SELECT coalesce(e.ENCOUNTERCLASS,'Unknown') encounter_class, count(*) encounters
        FROM read_csv_auto('{_q(root/'encounters.csv')}', header=true, all_varchar=true) e
        INNER JOIN cohort_ids i ON cast(e.PATIENT as varchar)=i.patient_id
        GROUP BY 1 ORDER BY encounters DESC
    """).df()
    trend = con.execute(f"""
        SELECT date_trunc('month', try_cast(e.START as timestamp)) month_start, count(*) encounter_count
        FROM read_csv_auto('{_q(root/'encounters.csv')}', header=true, all_varchar=true) e
        INNER JOIN cohort_ids i ON cast(e.PATIENT as varchar)=i.patient_id
        WHERE try_cast(e.START as timestamp) >= current_date - INTERVAL '5 years'
        GROUP BY 1 ORDER BY 1
    """).df()
    con.unregister("cohort_ids"); con.close()
    return {"summary":{"patients":n,"median_age":med,"female":female,"male":male},
            "ages":ages,"conditions":conditions,"mix":mix,"trend":trend}
