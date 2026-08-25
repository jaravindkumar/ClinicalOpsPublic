from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import duckdb
import pandas as pd
import numpy as np

DEFAULT_SYNTHEA_DIR = "/Volumes/Aravind_HardDisc/Clinical Ops/synthea/output/csv"
DEFAULT_DB_PATH = "data/clinicalops_v08.duckdb"

SITE_BLUEPRINT = [
    ("UK-001", "London Central", "United Kingdom"),
    ("UK-002", "Manchester", "United Kingdom"),
    ("UK-003", "Birmingham", "United Kingdom"),
    ("UK-004", "Cambridge", "United Kingdom"),
    ("UK-005", "Leeds", "United Kingdom"),
    ("UK-006", "Liverpool", "United Kingdom"),
    ("UK-007", "Bristol", "United Kingdom"),
    ("UK-008", "Newcastle", "United Kingdom"),
    ("UK-009", "Oxford", "United Kingdom"),
    ("UK-010", "Nottingham", "United Kingdom"),
    ("UK-011", "Glasgow", "United Kingdom"),
    ("UK-012", "Edinburgh", "United Kingdom"),
    ("UK-013", "Cardiff", "United Kingdom"),
    ("UK-014", "Belfast", "United Kingdom"),
    ("UK-015", "Sheffield", "United Kingdom"),
]

VISIT_NAMES = ["Screening", "Baseline", "Week 4", "Week 8", "Week 12", "Week 18", "Week 26", "Week 39", "Week 52"]
VISIT_DAYS = [0, 7, 35, 63, 91, 133, 189, 280, 371]


def _stable_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def resolve_synthea_dir(path: Optional[str] = None) -> Path:
    candidate = Path(path or os.getenv("SYNTHEA_CSV_DIR", DEFAULT_SYNTHEA_DIR)).expanduser()
    return candidate


def synthea_status(path: Optional[str] = None) -> Dict[str, object]:
    root = resolve_synthea_dir(path)
    required = ["patients.csv", "conditions.csv", "encounters.csv"]
    found = {name: (root / name).exists() for name in required}
    return {
        "path": str(root),
        "exists": root.exists(),
        "required_files": found,
        "ready": root.exists() and all(found.values()),
    }


def get_connection(db_path: str = DEFAULT_DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(db_path)


def _q(path: Path) -> str:
    return str(path).replace("'", "''")


def build_trial(
    synthea_dir: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    target_enrollment: int = 500,
    seed: int = 42,
    force: bool = False,
    candidate_patient_ids: Optional[List[str]] = None,
    cohort_name: Optional[str] = None,
) -> Dict[str, object]:
    """Build a deterministic synthetic trial-operations layer over Synthea CSVs.

    The source EHR remains immutable. Only a bounded trial cohort and operational events
    are materialized into DuckDB, so source population can scale to hundreds of thousands.
    """
    root = resolve_synthea_dir(synthea_dir)
    status = synthea_status(str(root))
    if not status["ready"]:
        raise FileNotFoundError(f"Synthea CSV directory is not ready: {status}")

    con = get_connection(db_path)
    if not force:
        existing = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='trial_metadata'").fetchone()[0]
        if existing:
            row = con.execute("SELECT value FROM trial_metadata WHERE key='build_complete'").fetchone()
            if row and row[0] == "true":
                return get_study_summary(con=con)

    con.execute("DROP TABLE IF EXISTS trial_metadata")
    con.execute("DROP TABLE IF EXISTS sites")
    con.execute("DROP TABLE IF EXISTS subjects")
    con.execute("DROP TABLE IF EXISTS subject_visits")
    con.execute("DROP TABLE IF EXISTS queries")
    con.execute("DROP TABLE IF EXISTS protocol_deviations")
    con.execute("DROP TABLE IF EXISTS adverse_events")
    con.execute("DROP TABLE IF EXISTS site_weekly_metrics")
    con.execute("DROP TABLE IF EXISTS site_risk_scores")

    patients = root / "patients.csv"
    conditions = root / "conditions.csv"
    encounters = root / "encounters.csv"

    # Candidate cohort: age 40-75, enriched for diabetes; fallback allows age-eligible patients.
    candidate_sql = f"""
    WITH p AS (
      SELECT
        CAST(Id AS VARCHAR) AS patient_id,
        TRY_CAST(BIRTHDATE AS DATE) AS birthdate,
        CAST(FIRST AS VARCHAR) AS first_name,
        CAST(LAST AS VARCHAR) AS last_name,
        CAST(GENDER AS VARCHAR) AS gender,
        CAST(RACE AS VARCHAR) AS race,
        CAST(ETHNICITY AS VARCHAR) AS ethnicity,
        TRY_CAST(HEALTHCARE_EXPENSES AS DOUBLE) AS healthcare_expenses,
        date_diff('year', TRY_CAST(BIRTHDATE AS DATE), current_date) AS age
      FROM read_csv_auto('{_q(patients)}', header=true, all_varchar=true)
    ), cond AS (
      SELECT CAST(PATIENT AS VARCHAR) patient_id,
             count(*) condition_count,
             max(CASE WHEN lower(CAST(DESCRIPTION AS VARCHAR)) LIKE '%diabet%' THEN 1 ELSE 0 END) diabetes_flag
      FROM read_csv_auto('{_q(conditions)}', header=true, all_varchar=true)
      GROUP BY 1
    ), enc AS (
      SELECT CAST(PATIENT AS VARCHAR) patient_id, count(*) encounter_count
      FROM read_csv_auto('{_q(encounters)}', header=true, all_varchar=true)
      GROUP BY 1
    )
    SELECT p.*,
           coalesce(cond.condition_count,0) condition_count,
           coalesce(cond.diabetes_flag,0) diabetes_flag,
           coalesce(enc.encounter_count,0) encounter_count
    FROM p
    LEFT JOIN cond USING(patient_id)
    LEFT JOIN enc USING(patient_id)
    WHERE age BETWEEN 40 AND 75
    ORDER BY diabetes_flag DESC, condition_count DESC, encounter_count DESC, patient_id
    """
    candidates = con.execute(candidate_sql).df()
    if candidate_patient_ids:
        allowed = set(str(x) for x in candidate_patient_ids)
        candidates = candidates[candidates["patient_id"].astype(str).isin(allowed)].copy()
    if candidates.empty:
        raise RuntimeError("No age-eligible Synthea patients were found.")

    rng = np.random.default_rng(seed)
    # Screening pool slightly larger than target so screen failures are visible.
    screen_n = min(len(candidates), max(target_enrollment + 120, int(target_enrollment * 1.35)))
    # Preserve diabetes enrichment while randomising within a strong candidate pool.
    pool = candidates.head(min(len(candidates), screen_n * 2)).copy()
    pool = pool.iloc[rng.permutation(len(pool))].head(screen_n).reset_index(drop=True)

    # Deterministic screen failure: higher comorbidity slightly raises failure probability.
    comorb = np.clip(pool["condition_count"].fillna(0).to_numpy(dtype=float) / 70.0, 0, 1)
    screen_fail_p = np.clip(0.14 + 0.12 * comorb - 0.05 * pool["diabetes_flag"].to_numpy(dtype=float), 0.08, 0.35)
    screen_failed = rng.random(len(pool)) < screen_fail_p
    eligible_idx = np.where(~screen_failed)[0]
    if len(eligible_idx) > target_enrollment:
        enrolled_idx = eligible_idx[:target_enrollment]
    else:
        enrolled_idx = eligible_idx

    enrolled_set = set(enrolled_idx.tolist())
    pool["screen_status"] = ["Enrolled" if i in enrolled_set else "Screen Failure" for i in range(len(pool))]
    pool["subject_id"] = [f"SUBJ-{i+1:05d}" for i in range(len(pool))]

    # Site capacities vary; assignment is intentionally imbalanced to enable useful benchmarking.
    site_weights = np.array([1.05, .72, .93, .82, .88, 1.10, .96, .78, .68, .90, 1.00, .84, .75, .94, .80])
    site_weights = site_weights / site_weights.sum()
    assignments = rng.choice(len(SITE_BLUEPRINT), size=len(pool), p=site_weights)
    pool["site_id"] = [SITE_BLUEPRINT[i][0] for i in assignments]
    pool["site_name"] = [SITE_BLUEPRINT[i][1] for i in assignments]
    pool["country"] = [SITE_BLUEPRINT[i][2] for i in assignments]

    start = date.today() - timedelta(days=220)
    screen_offsets = rng.integers(0, 170, size=len(pool))
    pool["screen_date"] = [start + timedelta(days=int(x)) for x in screen_offsets]
    pool["randomization_date"] = [
        (d + timedelta(days=int(rng.integers(3, 11)))) if status == "Enrolled" else pd.NaT
        for d, status in zip(pool["screen_date"], pool["screen_status"])
    ]

    # Site-level latent profiles create coherent operational behaviour rather than unrelated random flags.
    site_rows = []
    for idx, (site_id, site_name, country) in enumerate(SITE_BLUEPRINT):
        srng = np.random.default_rng(seed + idx * 97)
        quality = float(np.clip(srng.normal(0.72, 0.13), 0.35, 0.95))
        recruitment = float(np.clip(srng.normal(0.76, 0.17), 0.30, 1.15))
        data_discipline = float(np.clip(srng.normal(0.74, 0.14), 0.35, 0.97))
        safety_discipline = float(np.clip(srng.normal(0.82, 0.09), 0.50, 0.98))
        site_rows.append({
            "site_id": site_id, "site_name": site_name, "country": country,
            "quality_factor": quality, "recruitment_factor": recruitment,
            "data_discipline": data_discipline, "safety_discipline": safety_discipline,
            "target_enrollment": int(round(target_enrollment * site_weights[idx])),
        })
    sites_df = pd.DataFrame(site_rows)

    today = date.today()
    visits = []
    query_rows = []
    deviation_rows = []
    ae_rows = []
    qid = did = aeid = 1

    enrolled = pool[pool["screen_status"] == "Enrolled"].copy()
    site_map = sites_df.set_index("site_id").to_dict("index")

    for _, subj in enrolled.iterrows():
        profile = site_map[subj["site_id"]]
        subj_rng = np.random.default_rng(seed + _stable_seed(subj["subject_id"]))
        rand_date = pd.Timestamp(subj["randomization_date"]).date()
        complexity = float(np.clip((subj["condition_count"] or 0) / 60.0, 0, 1))
        encounter_intensity = float(np.clip((subj["encounter_count"] or 0) / 120.0, 0, 1))

        for visit_num, (visit_name, day_offset) in enumerate(zip(VISIT_NAMES, VISIT_DAYS), start=1):
            scheduled = rand_date + timedelta(days=day_offset)
            if scheduled > today:
                status_v = "Upcoming"
                actual = pd.NaT
                lateness = 0
            else:
                miss_p = np.clip(0.015 + (1-profile["quality_factor"]) * 0.22 + complexity * 0.025, 0.01, 0.28)
                missed = subj_rng.random() < miss_p
                if missed:
                    status_v = "Missed"
                    actual = pd.NaT
                    lateness = max(1, (today - scheduled).days)
                else:
                    late_scale = 1.5 + (1-profile["quality_factor"]) * 10
                    late_days = int(max(0, round(subj_rng.normal(late_scale, 2.4)))) if subj_rng.random() < (0.08 + (1-profile["quality_factor"]) * .28) else 0
                    actual_date = scheduled + timedelta(days=late_days)
                    actual = actual_date
                    lateness = late_days
                    status_v = "Completed late" if late_days > 3 else "Completed"

                # Data queries are tied to site data discipline and clinical complexity.
                q_p = np.clip(0.05 + (1-profile["data_discipline"]) * .35 + complexity * .07, .03, .45)
                if status_v != "Missed" and subj_rng.random() < q_p:
                    opened = scheduled + timedelta(days=max(0, int(subj_rng.integers(0, 4))))
                    unresolved_p = np.clip((1-profile["data_discipline"]) * .65 + .08, .05, .65)
                    unresolved = subj_rng.random() < unresolved_p
                    if unresolved:
                        resolved = pd.NaT
                        qstatus = "Open"
                        age_days = max(0, (today-opened).days)
                    else:
                        age_days = int(max(1, round(subj_rng.normal(2 + (1-profile["data_discipline"])*7, 1.8))))
                        resolved = opened + timedelta(days=age_days)
                        qstatus = "Resolved"
                    query_rows.append({
                        "query_id": f"Q-{qid:06d}", "subject_id": subj["subject_id"], "site_id": subj["site_id"],
                        "visit_name": visit_name, "opened_date": opened, "resolved_date": resolved,
                        "status": qstatus, "age_days": age_days,
                        "category": subj_rng.choice(["Missing data", "Inconsistent data", "Lab value", "Source clarification"], p=[.4,.25,.2,.15])
                    })
                    qid += 1

                dev_p = np.clip(0.012 + (1-profile["quality_factor"]) * .15 + complexity * .03, .01, .22)
                if status_v in ("Missed", "Completed late") and subj_rng.random() < min(.75, dev_p * 3):
                    deviation_rows.append({
                        "deviation_id": f"PD-{did:05d}", "subject_id": subj["subject_id"], "site_id": subj["site_id"],
                        "event_date": scheduled, "visit_name": visit_name,
                        "severity": subj_rng.choice(["Minor", "Important"], p=[.78,.22]),
                        "category": "Visit window" if status_v == "Completed late" else "Missed protocol visit"
                    })
                    did += 1

            visits.append({
                "subject_id": subj["subject_id"], "site_id": subj["site_id"], "visit_num": visit_num,
                "visit_name": visit_name, "scheduled_date": scheduled, "actual_date": actual,
                "status": status_v, "lateness_days": lateness
            })

        # AEs are grounded to complexity/encounter intensity; delayed reporting is site-driven.
        ae_count = subj_rng.poisson(0.25 + 0.55*complexity + 0.20*encounter_intensity)
        for _ae in range(min(ae_count, 3)):
            event_date = rand_date + timedelta(days=int(subj_rng.integers(10, min(330, max(11, (today-rand_date).days+1))))) if rand_date < today-timedelta(days=10) else rand_date
            delay = int(max(0, round(subj_rng.normal((1-profile["safety_discipline"])*7, 1.7))))
            ae_rows.append({
                "ae_id": f"AE-{aeid:05d}", "subject_id": subj["subject_id"], "site_id": subj["site_id"],
                "event_date": event_date, "report_delay_days": delay,
                "serious": bool(subj_rng.random() < .08), "status": "Open" if subj_rng.random() < .12 else "Closed"
            })
            aeid += 1

    subjects_cols = ["subject_id","patient_id","site_id","site_name","country","screen_status","screen_date","randomization_date","age","gender","race","ethnicity","condition_count","diabetes_flag","encounter_count"]
    subjects_df = pool[subjects_cols].copy()
    visits_df = pd.DataFrame(visits)
    queries_df = pd.DataFrame(query_rows, columns=["query_id","subject_id","site_id","visit_name","opened_date","resolved_date","status","age_days","category"])
    dev_df = pd.DataFrame(deviation_rows, columns=["deviation_id","subject_id","site_id","event_date","visit_name","severity","category"])
    ae_df = pd.DataFrame(ae_rows, columns=["ae_id","subject_id","site_id","event_date","report_delay_days","serious","status"])

    for name, df in [("sites",sites_df),("subjects",subjects_df),("subject_visits",visits_df),("queries",queries_df),("protocol_deviations",dev_df),("adverse_events",ae_df)]:
        con.register(f"_{name}", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _{name}")
        con.unregister(f"_{name}")

    _build_metrics(con)

    metadata = {
        "study_id": "COPS-DM-301",
        "study_name": "Phase III Type 2 Diabetes Operations Simulation",
        "phase": "III",
        "indication": "Type 2 Diabetes",
        "target_enrollment": str(target_enrollment),
        "site_count": str(len(SITE_BLUEPRINT)),
        "source": str(root),
        "build_date": str(today),
        "build_complete": "true",
        "seed": str(seed),
        "source_cohort": str(cohort_name or "Default diabetes-enriched candidate pool"),
    }
    md = pd.DataFrame(list(metadata.items()), columns=["key","value"])
    con.register("_md", md)
    con.execute("CREATE TABLE trial_metadata AS SELECT * FROM _md")
    con.unregister("_md")
    summary = get_study_summary(con=con)
    con.close()
    return summary


def _build_metrics(con) -> None:
    con.execute("""
    CREATE OR REPLACE TABLE site_risk_scores AS
    WITH subj AS (
      SELECT site_id,
             count(*) FILTER (WHERE screen_status='Enrolled') enrolled,
             count(*) screened,
             100.0 * count(*) FILTER (WHERE screen_status='Screen Failure') / nullif(count(*),0) screen_failure_rate
      FROM subjects GROUP BY 1
    ), vis AS (
      SELECT site_id,
             count(*) FILTER (WHERE status='Missed') missed_visits,
             count(*) FILTER (WHERE status IN ('Completed','Completed late','Missed')) due_visits,
             count(*) FILTER (WHERE status='Completed late') late_visits,
             count(*) FILTER (WHERE status='Missed' AND scheduled_date < current_date) overdue_visits
      FROM subject_visits GROUP BY 1
    ), q AS (
      SELECT site_id,
             count(*) FILTER (WHERE status='Open') open_queries,
             avg(age_days) FILTER (WHERE status='Open') avg_open_query_age,
             count(*) total_queries
      FROM queries GROUP BY 1
    ), d AS (
      SELECT site_id,
             count(*) deviations,
             count(*) FILTER (WHERE severity='Important') important_deviations
      FROM protocol_deviations GROUP BY 1
    ), ae AS (
      SELECT site_id,
             count(*) adverse_events,
             avg(report_delay_days) avg_ae_report_delay,
             count(*) FILTER (WHERE status='Open') open_aes
      FROM adverse_events GROUP BY 1
    )
    SELECT s.site_id, s.site_name, s.country, s.target_enrollment,
           coalesce(subj.enrolled,0) enrolled,
           coalesce(subj.screened,0) screened,
           coalesce(subj.screen_failure_rate,0) screen_failure_rate,
           coalesce(vis.overdue_visits,0) overdue_visits,
           coalesce(vis.missed_visits,0) missed_visits,
           coalesce(vis.late_visits,0) late_visits,
           100.0*coalesce(vis.missed_visits,0)/nullif(vis.due_visits,0) missed_visit_rate,
           coalesce(q.open_queries,0) open_queries,
           coalesce(q.avg_open_query_age,0) avg_open_query_age,
           coalesce(q.total_queries,0) total_queries,
           coalesce(d.deviations,0) deviations,
           coalesce(d.important_deviations,0) important_deviations,
           coalesce(ae.adverse_events,0) adverse_events,
           coalesce(ae.avg_ae_report_delay,0) avg_ae_report_delay,
           coalesce(ae.open_aes,0) open_aes,
           least(100, greatest(0, 100*(1.0 - coalesce(subj.enrolled,0)/nullif(s.target_enrollment,0)))) enrollment_risk,
           least(100, coalesce(100.0*vis.missed_visits/nullif(vis.due_visits,0),0)*5.5 + least(coalesce(vis.overdue_visits,0)*2.0,35)) visit_risk,
           least(100, coalesce(q.open_queries,0)*1.2 + coalesce(q.avg_open_query_age,0)*5.0) query_risk,
           least(100, coalesce(d.deviations,0)*7.0 + coalesce(d.important_deviations,0)*10.0) deviation_risk,
           least(100, coalesce(ae.avg_ae_report_delay,0)*12.0 + coalesce(ae.open_aes,0)*5.0) safety_risk
    FROM sites s
    LEFT JOIN subj USING(site_id)
    LEFT JOIN vis USING(site_id)
    LEFT JOIN q USING(site_id)
    LEFT JOIN d USING(site_id)
    LEFT JOIN ae USING(site_id)
    """)
    con.execute("""
      ALTER TABLE site_risk_scores ADD COLUMN risk_score DOUBLE;
    """)
    con.execute("""
      UPDATE site_risk_scores SET risk_score = round(
          coalesce(enrollment_risk,0)*0.20 + coalesce(visit_risk,0)*0.25 + coalesce(query_risk,0)*0.20 +
          coalesce(deviation_risk,0)*0.20 + coalesce(safety_risk,0)*0.15, 1
      )
    """)
    con.execute("""
      ALTER TABLE site_risk_scores ADD COLUMN risk_band VARCHAR;
    """)
    con.execute("""
      UPDATE site_risk_scores SET risk_band = CASE WHEN risk_score>=70 THEN 'High' WHEN risk_score>=45 THEN 'Medium' ELSE 'Low' END
    """)

    # 8 weekly snapshots used for trend intelligence. Current score is the anchor; prior values
    # are deterministic site-specific trajectories, not independent random dashboard numbers.
    current = con.execute("SELECT * FROM site_risk_scores").df()
    rows = []
    today = date.today()
    for _, r in current.iterrows():
        rng = np.random.default_rng(_stable_seed(r["site_id"]))
        slope = rng.uniform(-2.2, 4.8)
        for weeks_ago in range(7, -1, -1):
            week_date = today - timedelta(days=7*weeks_ago)
            historical = float(np.clip(r["risk_score"] - slope*weeks_ago + rng.normal(0, 1.6), 0, 100))
            if weeks_ago == 0:
                historical = float(r["risk_score"])
            rows.append({"site_id":r["site_id"], "week_date":week_date, "risk_score":round(historical,1)})
    weekly = pd.DataFrame(rows)
    con.register("_weekly", weekly)
    con.execute("CREATE OR REPLACE TABLE site_weekly_metrics AS SELECT * FROM _weekly")
    con.unregister("_weekly")


def ensure_trial(synthea_dir: Optional[str] = None, db_path: str = DEFAULT_DB_PATH) -> bool:
    try:
        con = get_connection(db_path)
        exists = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='trial_metadata'").fetchone()[0] > 0
        con.close()
        if exists:
            return True
        if synthea_status(synthea_dir)["ready"]:
            build_trial(synthea_dir=synthea_dir, db_path=db_path)
            return True
    except Exception:
        return False
    return False


def get_study_summary(db_path: str = DEFAULT_DB_PATH, con=None) -> Dict[str, object]:
    own = con is None
    con = con or get_connection(db_path)
    meta = {}
    try:
        meta = dict(con.execute("SELECT key,value FROM trial_metadata").fetchall())
    except Exception:
        meta = {"study_id":"COPS-DM-301","study_name":"Trial not built"}
    row = con.execute("""
      SELECT
        sum(enrolled) enrolled,
        sum(screened) screened,
        sum(target_enrollment) AS target_enrollment_total,
        sum(overdue_visits) overdue_visits,
        sum(open_queries) open_queries,
        sum(deviations) deviations,
        sum(open_aes) open_aes,
        count(*) FILTER (WHERE risk_band='High') high_risk_sites,
        round(avg(risk_score),1) avg_risk
      FROM site_risk_scores
    """).fetchone()
    result = {
        **meta,
        "enrolled": int(row[0] or 0), "screened": int(row[1] or 0), "target": int(row[2] or 0),
        "overdue_visits": int(row[3] or 0), "open_queries": int(row[4] or 0),
        "deviations": int(row[5] or 0), "open_aes": int(row[6] or 0),
        "high_risk_sites": int(row[7] or 0), "avg_risk": float(row[8] or 0),
    }
    if own:
        con.close()
    return result


def get_site_scores(db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    con = get_connection(db_path)
    df = con.execute("SELECT * FROM site_risk_scores ORDER BY risk_score DESC").df()
    con.close()
    return df


def get_site_detail(site_id: str, db_path: str = DEFAULT_DB_PATH) -> Tuple[Dict[str, object], pd.DataFrame, pd.DataFrame]:
    con = get_connection(db_path)
    row = con.execute("SELECT * FROM site_risk_scores WHERE site_id=?", [site_id]).df()
    if row.empty:
        con.close(); raise KeyError(site_id)
    trend = con.execute("SELECT week_date,risk_score FROM site_weekly_metrics WHERE site_id=? ORDER BY week_date", [site_id]).df()
    subjects = con.execute("""
        SELECT s.subject_id, s.age, s.gender, s.condition_count, s.encounter_count,
               count(*) FILTER (WHERE v.status='Missed') missed_visits,
               count(*) FILTER (WHERE v.status='Completed late') late_visits,
               (SELECT count(*) FROM queries q WHERE q.subject_id=s.subject_id AND q.status='Open') open_queries,
               (SELECT count(*) FROM protocol_deviations d WHERE d.subject_id=s.subject_id) deviations
        FROM subjects s LEFT JOIN subject_visits v USING(subject_id)
        WHERE s.site_id=? AND s.screen_status='Enrolled'
        GROUP BY s.subject_id,s.age,s.gender,s.condition_count,s.encounter_count
        ORDER BY missed_visits DESC, open_queries DESC, deviations DESC
        LIMIT 50
    """, [site_id]).df()
    con.close()
    return row.iloc[0].to_dict(), trend, subjects


def get_attention_items(db_path: str = DEFAULT_DB_PATH, limit: int = 5) -> List[Dict[str, object]]:
    df = get_site_scores(db_path).head(limit)
    items = []
    for _, r in df.iterrows():
        drivers = {
            "Enrollment": r["enrollment_risk"], "Visit compliance": r["visit_risk"], "Data quality": r["query_risk"],
            "Protocol compliance": r["deviation_risk"], "Safety": r["safety_risk"]
        }
        top = sorted(drivers.items(), key=lambda kv: kv[1], reverse=True)[:2]
        items.append({
            "site_id": r["site_id"], "site_name": r["site_name"], "country": r["country"],
            "risk_score": float(r["risk_score"]), "risk_band": r["risk_band"],
            "drivers": top, "overdue_visits": int(r["overdue_visits"]), "open_queries": int(r["open_queries"]),
            "deviations": int(r["deviations"]),
        })
    return items


def build_grounded_context(question: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, object]:
    summary = get_study_summary(db_path)
    sites = get_site_scores(db_path)
    top_sites = sites.head(8).to_dict("records")
    return {
        "question": question,
        "study_summary": summary,
        "highest_risk_sites": top_sites,
        "guardrail": "Use only the supplied metrics. Do not invent clinical facts, diagnoses, or operational events.",
    }


def get_study_weekly_risk(db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    con=get_connection(db_path)
    df=con.execute("SELECT week_date, round(avg(risk_score),1) avg_risk, max(risk_score) max_risk FROM site_weekly_metrics GROUP BY 1 ORDER BY 1").df()
    con.close(); return df

def get_country_summary(db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    con=get_connection(db_path)
    df=con.execute("""SELECT country, count(*) sites, sum(enrolled) enrolled, sum(target_enrollment) AS target_total,
        round(avg(risk_score),1) avg_risk, sum(open_queries) open_queries, sum(overdue_visits) overdue_visits
        FROM site_risk_scores GROUP BY 1 ORDER BY avg_risk DESC""").df()
    con.close(); return df
