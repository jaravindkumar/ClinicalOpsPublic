import sqlite3, json
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "clinicalops_audit.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        case_id TEXT,
        original_input TEXT,
        extraction_json TEXT,
        triggers_json TEXT,
        recommended_priority TEXT,
        reviewer_decision TEXT,
        reviewer_notes TEXT
    )""")
    conn.commit(); conn.close()

def insert_audit(case_id, original_input, extraction, triggers, recommended_priority, reviewer_decision, reviewer_notes):
    init_db()
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("""INSERT INTO audit_log (timestamp, case_id, original_input, extraction_json, triggers_json, recommended_priority, reviewer_decision, reviewer_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.utcnow().isoformat(), case_id, original_input, extraction.model_dump_json(indent=2), json.dumps([t.model_dump() for t in triggers], indent=2), recommended_priority, reviewer_decision, reviewer_notes))
    conn.commit(); conn.close()

def read_audit():
    init_db()
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT timestamp, case_id, recommended_priority, reviewer_decision, reviewer_notes FROM audit_log ORDER BY id DESC")
    rows = cur.fetchall(); conn.close(); return rows
