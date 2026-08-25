from __future__ import annotations
import json, uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional
import duckdb, pandas as pd
from src.trial_ops import resolve_synthea_dir, synthea_status

COHORT_DB = 'data/cohorts.duckdb'

def _q(p: Path): return str(p).replace("'", "''")

def _age_expr():
    return "date_diff('year', try_cast(BIRTHDATE as date), current_date) - CASE WHEN (month(current_date), day(current_date)) < (month(try_cast(BIRTHDATE as date)), day(try_cast(BIRTHDATE as date))) THEN 1 ELSE 0 END"

def filter_population(
    synthea_dir: str,
    age_min=0,
    age_max=120,
    sex='Any',
    condition='',
    exclude_condition='',
    recent_years=10,
    limit=None,
    recent_days=None,
    as_of_date=None,
    include_conditions=None,
    exclude_conditions=None,
    include_logic='AND',
    exclude_logic='OR',
    observation_description='',
    observation_operator='>=',
    observation_value=None,
):
    """Filter Synthea patients.

    `include_conditions` and `exclude_conditions` accept multiple diagnosis descriptions.
    Inclusion logic can be AND (patient must have every selected condition) or OR.
    Exclusion logic defaults to OR (exclude a patient if any selected exclusion is present).
    The legacy single condition arguments are retained for backwards compatibility.
    """
    root = resolve_synthea_dir(synthea_dir)
    if not synthea_status(str(root))['ready']:
        raise FileNotFoundError(str(root))

    includes = [str(x).strip() for x in (include_conditions or []) if str(x).strip() and str(x) != 'Any']
    excludes = [str(x).strip() for x in (exclude_conditions or []) if str(x).strip() and str(x) != 'Any']
    if not includes and condition and condition != 'Any':
        includes = [str(condition).strip()]
    if not excludes and exclude_condition and exclude_condition != 'Any':
        excludes = [str(exclude_condition).strip()]

    con = duckdb.connect()
    age = _age_expr()
    wh = [f"{age} BETWEEN ? AND ?"]
    params = [int(age_min), int(age_max)]

    if sex != 'Any':
        wh.append("upper(GENDER)=?")
        params.append(sex.upper()[0])

    condition_csv = _q(root / 'conditions.csv')
    include_terms = []
    for selected in includes:
        include_terms.append(
            f"EXISTS (SELECT 1 FROM read_csv_auto('{condition_csv}', header=true, all_varchar=true) c "
            "WHERE c.PATIENT=p.Id AND lower(c.DESCRIPTION) LIKE ?)"
        )
        params.append('%' + selected.lower() + '%')
    if include_terms:
        joiner = ' AND ' if str(include_logic).upper() == 'AND' else ' OR '
        wh.append('(' + joiner.join(include_terms) + ')')

    exclude_terms = []
    for selected in excludes:
        exclude_terms.append(
            f"EXISTS (SELECT 1 FROM read_csv_auto('{condition_csv}', header=true, all_varchar=true) c "
            "WHERE c.PATIENT=p.Id AND lower(c.DESCRIPTION) LIKE ?)"
        )
        params.append('%' + selected.lower() + '%')
    if exclude_terms:
        joiner = ' AND ' if str(exclude_logic).upper() == 'AND' else ' OR '
        wh.append('NOT (' + joiner.join(exclude_terms) + ')')

    if observation_description and observation_value is not None:
        op = observation_operator if observation_operator in ('>','>=','<','<=','=') else '>='
        obs_csv = _q(root / 'observations.csv')
        wh.append(
            f"EXISTS (SELECT 1 FROM read_csv_auto('{obs_csv}', header=true, all_varchar=true) o "
            f"WHERE o.PATIENT=p.Id AND lower(o.DESCRIPTION)=? AND try_cast(o.VALUE as double) {op} ?)"
        )
        params.extend([str(observation_description).lower(), float(observation_value)])

    if recent_days is not None and int(recent_days) > 0:
        anchor = str(as_of_date) if as_of_date else None
        if anchor:
            wh.append(
                f"EXISTS (SELECT 1 FROM read_csv_auto('{_q(root/'encounters.csv')}', header=true, all_varchar=true) e "
                f"WHERE e.PATIENT=p.Id AND CAST(try_cast(e.START as timestamp) AS DATE) "
                f"BETWEEN CAST(? AS DATE) - INTERVAL '{int(recent_days)} days' AND CAST(? AS DATE))"
            )
            params.extend([anchor, anchor])
        else:
            wh.append(
                f"EXISTS (SELECT 1 FROM read_csv_auto('{_q(root/'encounters.csv')}', header=true, all_varchar=true) e "
                f"WHERE e.PATIENT=p.Id AND CAST(try_cast(e.START as timestamp) AS DATE) "
                f"BETWEEN current_date - INTERVAL '{int(recent_days)} days' AND current_date)"
            )
    elif recent_years and int(recent_years) > 0:
        anchor = str(as_of_date) if as_of_date else None
        if anchor:
            wh.append(
                f"EXISTS (SELECT 1 FROM read_csv_auto('{_q(root/'encounters.csv')}', header=true, all_varchar=true) e "
                f"WHERE e.PATIENT=p.Id AND CAST(try_cast(e.START as timestamp) AS DATE) "
                f"BETWEEN CAST(? AS DATE) - INTERVAL '{int(recent_years)} years' AND CAST(? AS DATE))"
            )
            params.extend([anchor, anchor])
        else:
            wh.append(
                f"EXISTS (SELECT 1 FROM read_csv_auto('{_q(root/'encounters.csv')}', header=true, all_varchar=true) e "
                f"WHERE e.PATIENT=p.Id AND try_cast(e.START as timestamp) >= current_date - INTERVAL '{int(recent_years)} years')"
            )

    lim = f" LIMIT {int(limit)}" if limit else ''
    sql = f"""SELECT cast(Id as varchar) patient_id, {age} age, cast(GENDER as varchar) sex,
                     cast(CITY as varchar) city, cast(STATE as varchar) state
              FROM read_csv_auto('{_q(root/'patients.csv')}', header=true, all_varchar=true) p
              WHERE {' AND '.join(wh)} ORDER BY patient_id {lim}"""
    df = con.execute(sql, params).df()
    con.close()
    return df

def condition_options(synthea_dir: str, n=250):
    root=resolve_synthea_dir(synthea_dir); con=duckdb.connect()
    df=con.execute(f"SELECT DESCRIPTION, count(*) n FROM read_csv_auto('{_q(root/'conditions.csv')}', header=true, all_varchar=true) GROUP BY 1 ORDER BY n DESC LIMIT {int(n)}").df(); con.close()
    return ['Any']+df['DESCRIPTION'].dropna().astype(str).tolist()


def observation_catalog(synthea_dir: str, n=120):
    """Numeric observations suitable for a simple protocol threshold criterion."""
    root=resolve_synthea_dir(synthea_dir); con=duckdb.connect()
    df=con.execute(f"""
        SELECT DESCRIPTION, mode(UNITS) units, count(*) n
        FROM read_csv_auto('{_q(root/'observations.csv')}', header=true, all_varchar=true)
        WHERE DESCRIPTION IS NOT NULL AND try_cast(VALUE as double) IS NOT NULL
        GROUP BY 1 ORDER BY n DESC LIMIT {int(n)}
    """).df(); con.close()
    return df


CONDITION_CATEGORY_RULES = [
    ("Cardiovascular", ["hypertension", "heart", "cardiac", "coronary", "myocard", "angina", "atrial", "arrhythm", "stroke", "cerebrovascular", "vascular", "aortic", "cholesterol", "hyperlipid"]),
    ("Endocrine & metabolic", ["diabetes", "glyc", "thyroid", "obesity", "metabolic", "hypergly", "hypogly", "adrenal", "pituitary", "vitamin", "gout"]),
    ("Respiratory", ["asthma", "copd", "bronch", "pneum", "respir", "pulmonary", "emphysema", "apnea", "lung"]),
    ("Renal & urinary", ["kidney", "renal", "neph", "urinary", "bladder", "cystitis", "ureter", "dialysis"]),
    ("Gastrointestinal & hepatology", ["gastro", "intestinal", "colon", "bowel", "crohn", "colitis", "liver", "hepatic", "hepatitis", "reflux", "gerd", "ulcer", "pancrea", "gallbladder", "constipation", "diarrhea"]),
    ("Neurology", ["migraine", "seizure", "epilep", "dement", "alzheimer", "parkinson", "neurop", "multiple sclerosis", "headache", "neurolog"]),
    ("Mental & behavioral health", ["depress", "anxiety", "bipolar", "schizo", "panic", "mental", "behavior", "substance", "alcohol", "opioid", "tobacco", "stress"]),
    ("Musculoskeletal & pain", ["arthritis", "osteo", "fracture", "sprain", "back pain", "joint", "musculoskeletal", "osteoporosis", "tendon", "pain"]),
    ("Infectious disease", ["infection", "viral", "bacterial", "covid", "influenza", "flu", "tuberculosis", "hiv", "sepsis", "pharyngitis", "sinusitis"]),
    ("Oncology & hematology", ["cancer", "malignant", "neoplasm", "carcinoma", "leukemia", "lymphoma", "anemia", "hemat", "thromb", "bleeding"]),
    ("Reproductive & pregnancy", ["pregnan", "gestat", "contracept", "menstrual", "uter", "ovarian", "prostate", "erectile", "infertil", "labor", "delivery"]),
    ("ENT & ophthalmology", ["otitis", "ear", "hearing", "eye", "vision", "cataract", "glaucoma", "rhinitis", "tonsil", "sinus", "pharyng"]),
    ("Dermatology & allergy", ["dermat", "eczema", "rash", "skin", "allerg", "urticaria", "psoriasis", "acne"]),
    ("Care, preventive & administrative", ["review due", "screening", "check-up", "checkup", "preventive", "wellness", "medication review", "encounter for", "history of"]),
]

def _condition_category(description: str) -> str:
    text = (description or "").lower()
    for category, keywords in CONDITION_CATEGORY_RULES:
        if any(k in text for k in keywords):
            return category
    return "Other conditions"

def condition_catalog(synthea_dir: str, n=800):
    """Return grouped Synthea condition descriptions with prevalence counts.

    The grouping is deliberately deterministic and UI-oriented: users pick a broad clinical
    area, then choose one or more observed Synthea diagnoses inside that area.
    """
    root = resolve_synthea_dir(synthea_dir)
    con = duckdb.connect()
    df = con.execute(
        f"SELECT DESCRIPTION, count(*) n FROM read_csv_auto('{_q(root/'conditions.csv')}', header=true, all_varchar=true) "
        f"WHERE DESCRIPTION IS NOT NULL GROUP BY 1 ORDER BY n DESC LIMIT {int(n)}"
    ).df()
    con.close()
    catalog = {}
    for row in df.itertuples(index=False):
        desc = str(row.DESCRIPTION)
        cat = _condition_category(desc)
        catalog.setdefault(cat, []).append({"description": desc, "count": int(row.n)})
    preferred = [x[0] for x in CONDITION_CATEGORY_RULES] + ["Other conditions"]
    return {k: catalog[k] for k in preferred if k in catalog}

def ensure_db(db_path=COHORT_DB):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(db_path)
    con.execute("""CREATE TABLE IF NOT EXISTS cohorts(
        cohort_id VARCHAR PRIMARY KEY, name VARCHAR, created_at TIMESTAMP,
        criteria_json VARCHAR, patient_count INTEGER)""")
    con.execute("""CREATE TABLE IF NOT EXISTS cohort_members(
        cohort_id VARCHAR, patient_id VARCHAR, age INTEGER, sex VARCHAR, city VARCHAR, state VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS medgemma_batch_results(
        batch_id VARCHAR, cohort_id VARCHAR, patient_id VARCHAR, processed_at TIMESTAMP,
        status VARCHAR, priority VARCHAR, open_loop BOOLEAN, red_flags VARCHAR,
        missing_information VARCHAR, model_notes VARCHAR)""")
    for col, typ in [
        ('clinical_context','VARCHAR'), ('clinical_question','VARCHAR'), ('symptoms','VARCHAR'),
        ('ordered_tests','VARCHAR'), ('received_results','VARCHAR'), ('missing_results','VARCHAR'),
        ('clinical_text','VARCHAR')]:
        try:
            con.execute(f"ALTER TABLE medgemma_batch_results ADD COLUMN {col} {typ}")
        except Exception:
            pass
    con.execute("""CREATE TABLE IF NOT EXISTS clinician_reviews(
        review_id VARCHAR PRIMARY KEY, batch_id VARCHAR, cohort_id VARCHAR, patient_id VARCHAR,
        reviewed_at TIMESTAMP, reviewer_decision VARCHAR, reviewer_notes VARCHAR,
        medgemma_priority VARCHAR, open_loop BOOLEAN)""")
    return con

def save_cohort(name, criteria, members: pd.DataFrame, db_path=COHORT_DB):
    con=ensure_db(db_path); cid='COH-'+uuid.uuid4().hex[:8].upper()
    con.execute('INSERT INTO cohorts VALUES (?,?,?,?,?)',[cid,name,datetime.now(),json.dumps(criteria),len(members)])
    if len(members):
        tmp=members.copy(); tmp.insert(0,'cohort_id',cid); con.register('tmp_members',tmp)
        con.execute('INSERT INTO cohort_members SELECT * FROM tmp_members'); con.unregister('tmp_members')
    con.close(); return cid

def list_cohorts(db_path=COHORT_DB):
    con=ensure_db(db_path); df=con.execute('SELECT * FROM cohorts ORDER BY created_at DESC').df(); con.close(); return df

def cohort_members(cohort_id, db_path=COHORT_DB):
    con=ensure_db(db_path); df=con.execute('SELECT patient_id,age,sex,city,state FROM cohort_members WHERE cohort_id=? ORDER BY patient_id',[cohort_id]).df(); con.close(); return df

def save_batch_results(batch_id, cohort_id, rows, db_path=COHORT_DB):
    con=ensure_db(db_path)
    sql="""INSERT INTO medgemma_batch_results (
        batch_id, cohort_id, patient_id, processed_at, status, priority, open_loop,
        red_flags, missing_information, model_notes, clinical_context, clinical_question,
        symptoms, ordered_tests, received_results, missing_results, clinical_text
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    for r in rows:
        con.execute(sql,[
            batch_id, cohort_id, r['patient_id'], datetime.now(), r['status'], r.get('priority',''),
            r.get('open_loop',False), json.dumps(r.get('red_flags',[])), json.dumps(r.get('missing_information',[])),
            r.get('model_notes',''), r.get('clinical_context',''), r.get('clinical_question',''),
            json.dumps(r.get('symptoms',[])), json.dumps(r.get('ordered_tests',[])),
            json.dumps(r.get('received_results',[])), json.dumps(r.get('missing_results',[])), r.get('clinical_text','')])
    con.close()

def list_batch_results(db_path=COHORT_DB):
    con=ensure_db(db_path)
    df=con.execute("""SELECT batch_id, cohort_id, patient_id, processed_at, status, priority,
        open_loop, red_flags, missing_information, model_notes, clinical_context, clinical_question,
        symptoms, ordered_tests, received_results, missing_results, clinical_text
        FROM medgemma_batch_results ORDER BY processed_at DESC""").df()
    con.close(); return df

def save_clinician_review(batch_id, cohort_id, patient_id, decision, notes, medgemma_priority, open_loop, db_path=COHORT_DB):
    con=ensure_db(db_path); rid='REV-'+uuid.uuid4().hex[:10].upper()
    con.execute('INSERT INTO clinician_reviews VALUES (?,?,?,?,?,?,?,?,?)',[
        rid,batch_id,cohort_id,patient_id,datetime.now(),decision,notes,medgemma_priority,bool(open_loop)])
    con.close(); return rid

def list_clinician_reviews(db_path=COHORT_DB):
    con=ensure_db(db_path); df=con.execute('SELECT * FROM clinician_reviews ORDER BY reviewed_at DESC').df(); con.close(); return df
