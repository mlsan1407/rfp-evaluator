"""SQLite configuration and complete immutable run snapshots."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from core import check_criteria

DEFAULT_DB = Path(__file__).parent / 'data' / 'rfp.sqlite3'
SEED = [
    (1, 'Technical Capability', 'Architecture, integrations, scalability and technical fit', 30, 10, 1),
    (2, 'Implementation Plan', 'Timeline, milestones, staffing and risk plan', 20, 10, 1),
    (3, 'Commercial Value', 'Pricing clarity, total cost and assumptions', 20, 10, 1),
    (4, 'Security & Compliance', 'Controls, certifications, privacy and auditability', 20, 10, 1),
    (5, 'Support & Experience', 'Support model, similar projects and references', 10, 10, 1),
]


@contextmanager
def connect(path=DEFAULT_DB):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        with con:
            yield con
    finally:
        con.close()


def init_db(path=DEFAULT_DB):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS evaluation_criteria (
          criterion_id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
          weight REAL NOT NULL, max_score REAL NOT NULL, is_active INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS rfp_runs (
          rfp_run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
          result_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS supplier_results (
          rfp_run_id TEXT NOT NULL REFERENCES rfp_runs(rfp_run_id), supplier_name TEXT NOT NULL,
          submission_date TEXT NOT NULL, experience_rating REAL NOT NULL,
          absolute_score REAL NOT NULL, ppi REAL NOT NULL, final_rank INTEGER NOT NULL,
          result_json TEXT NOT NULL, PRIMARY KEY(rfp_run_id, supplier_name));
        ''')
        if not db.execute('SELECT 1 FROM evaluation_criteria LIMIT 1').fetchone():
            db.executemany('INSERT INTO evaluation_criteria VALUES (?,?,?,?,?,?)', SEED)


def get_criteria(path=DEFAULT_DB, active_only=True):
    with connect(path) as db:
        rows = [dict(r) for r in db.execute('SELECT * FROM evaluation_criteria ORDER BY criterion_id')]
    return check_criteria(rows) if active_only else rows


def save_criteria(rows, path=DEFAULT_DB):
    check_criteria(rows)
    with connect(path) as db:
        db.executemany('UPDATE evaluation_criteria SET name=:name, description=:description, '
                       'weight=:weight, max_score=:max_score, is_active=:is_active '
                       'WHERE criterion_id=:criterion_id', rows)


def save_run(run, path=DEFAULT_DB):
    with connect(path) as db:
        db.execute('INSERT INTO rfp_runs VALUES (?,?,?,?)',
                   (run['rfp_run_id'], run['created_at'], run['status'], json.dumps(run, allow_nan=False)))
        for s in run['suppliers']:
            db.execute('INSERT INTO supplier_results VALUES (?,?,?,?,?,?,?,?)',
                       (run['rfp_run_id'], s['supplier_name'], s['submission_date'],
                        s['experience_rating'], s['absolute_score'], s['ppi'], s['final_rank'], json.dumps(s)))


def list_runs(path=DEFAULT_DB):
    with connect(path) as db:
        return [dict(r) for r in db.execute('SELECT rfp_run_id,created_at,status FROM rfp_runs ORDER BY created_at DESC')]


def load_run(run_id, path=DEFAULT_DB):
    with connect(path) as db:
        row = db.execute('SELECT result_json FROM rfp_runs WHERE rfp_run_id=?', (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


if __name__ == '__main__':
    init_db()
    print(f'Database ready: {DEFAULT_DB}')
