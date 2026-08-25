from __future__ import annotations

import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.synthea_patient import build_patient_clinical_text
from src.medgemma_client import extract
from src.cohort_engine import save_batch_results

_STATE = Path.home() / '.clinicalops_batch_jobs.json'
_LOCK = threading.RLock()
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix='clinicalops-medgemma')
_PROCESS_ID = os.getpid()


def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _load() -> dict:
    try:
        return json.loads(_STATE.read_text()) if _STATE.exists() else {}
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        tmp = _STATE.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=2, default=str))
        tmp.replace(_STATE)
    except Exception:
        pass


def _patch(job_id: str, **updates) -> None:
    with _LOCK:
        data = _load()
        record = data.get(job_id, {})
        record.update(updates)
        record['updated_at'] = _now()
        data[job_id] = record
        _save(data)


def job(job_id: str):
    return _load().get(job_id)


def _mark_stale_records(data: dict) -> dict:
    """Mark jobs from an older Streamlit/Python process as interrupted.

    The JSON registry survives server restarts, while Python worker threads do not.
    Without this check an old Running job can appear to run forever after a restart.
    """
    changed = False
    for jid, rec in data.items():
        if rec.get('status') in ('Queued', 'Running') and rec.get('process_id') not in (None, _PROCESS_ID):
            rec.update(
                status='Interrupted',
                stage='Stopped because the app process restarted',
                error='The Streamlit/Python process that owned this batch is no longer running. Start a new batch.',
                completed_at=_now(),
                current_patient='',
                updated_at=_now(),
            )
            changed = True
    if changed:
        _save(data)
    return data


def active_jobs():
    with _LOCK:
        data = _mark_stale_records(_load())
        return [v for v in data.values() if v.get('status') in ('Queued', 'Running')]


def recent_jobs(limit: int = 8):
    with _LOCK:
        data = _mark_stale_records(_load())
        vals = list(data.values())
    return sorted(vals, key=lambda x: x.get('created_at', ''), reverse=True)[:limit]


def request_cancel(job_id: str) -> None:
    rec = job(job_id)
    if rec and rec.get('status') in ('Queued', 'Running'):
        _patch(job_id, cancel_requested=True, stage='Cancellation requested; finishing current patient')


def start_batch(cohort_id: str, selected: pd.DataFrame, root: str, model: str) -> str:
    # Local MedGemma is intentionally serialized. Do not stack invisible jobs behind
    # a long-running inference; make the current job explicit to the user instead.
    existing = active_jobs()
    if existing:
        current = existing[0]
        raise RuntimeError(
            f"{current.get('batch_id')} is already {current.get('status','running').lower()} "
            f"({current.get('processed',0)}/{current.get('total',0)} patients complete). "
            "Wait for it to finish or request cancellation before starting another batch."
        )

    batch = 'BATCH-' + uuid.uuid4().hex[:8].upper()
    rows = selected[['patient_id']].copy().to_dict('records')
    state = {
        'job_id': batch,
        'batch_id': batch,
        'cohort_id': cohort_id,
        'status': 'Queued',
        'stage': 'Waiting for worker',
        'processed': 0,
        'total': len(rows),
        'failed': 0,
        'current_patient': '',
        'current_index': 0,
        'created_at': _now(),
        'started_at': None,
        'updated_at': _now(),
        'completed_at': None,
        'error': None,
        'cancel_requested': False,
        'process_id': _PROCESS_ID,
    }
    with _LOCK:
        data = _load()
        data[batch] = state
        _save(data)
    _EXECUTOR.submit(_worker, batch, cohort_id, rows, root, model)
    return batch


def _worker(batch: str, cohort_id: str, patients: list[dict], root: str, model: str) -> None:
    _patch(batch, status='Running', stage='Starting batch', started_at=_now())
    out_rows = []
    failed = 0
    try:
        for i, row in enumerate(patients, start=1):
            rec = job(batch) or {}
            if rec.get('cancel_requested'):
                _patch(batch, status='Cancelled', stage='Cancelled by user', current_patient='', completed_at=_now())
                return

            pid = row['patient_id']
            _patch(
                batch,
                current_patient=pid,
                current_index=i,
                stage=f'Preparing patient {i}/{len(patients)}',
            )
            try:
                text, _ = build_patient_clinical_text(pid, root)
                _patch(batch, stage=f'MedGemma inference · patient {i}/{len(patients)}')
                started = time.monotonic()
                out = extract(text, model=model)
                seconds = round(time.monotonic() - started, 1)
                _patch(batch, stage=f'Saving result · patient {i}/{len(patients)}', last_patient_seconds=seconds)
                out_rows.append({
                    'patient_id': pid,
                    'status': 'Complete',
                    'priority': out.priority,
                    'open_loop': out.open_loop,
                    'red_flags': out.red_flags,
                    'missing_information': out.missing_information,
                    'model_notes': out.model_notes,
                    'clinical_context': out.clinical_context,
                    'clinical_question': out.clinical_question,
                    'symptoms': out.symptoms,
                    'ordered_tests': out.ordered_tests,
                    'received_results': [x.model_dump() if hasattr(x, 'model_dump') else x for x in out.received_results],
                    'missing_results': out.missing_results,
                    'clinical_text': text,
                })
            except Exception as exc:
                failed += 1
                out_rows.append({
                    'patient_id': pid,
                    'status': 'Failed',
                    'priority': '',
                    'open_loop': False,
                    'red_flags': [],
                    'missing_information': [],
                    'model_notes': str(exc),
                    'clinical_context': '',
                    'clinical_question': '',
                    'symptoms': [],
                    'ordered_tests': [],
                    'received_results': [],
                    'missing_results': [],
                    'clinical_text': '',
                })
            # Persist progress after every patient. The UI reads this file independently
            # of the worker thread, so navigation does not interrupt progress updates.
            _patch(
                batch,
                processed=i,
                failed=failed,
                current_patient='',
                current_index=i,
                stage=f'{i}/{len(patients)} patients complete',
            )

        _patch(batch, stage='Writing batch results')
        save_batch_results(batch, cohort_id, out_rows)
        _patch(
            batch,
            status='Complete',
            stage='Complete',
            processed=len(patients),
            failed=failed,
            current_patient='',
            completed_at=_now(),
        )
    except Exception as exc:
        _patch(
            batch,
            status='Failed',
            stage='Batch failed',
            error=str(exc),
            current_patient='',
            completed_at=_now(),
        )
