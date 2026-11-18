import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get('DRIFTSENTINEL_DATA_DIR', ROOT / 'localdata')).resolve()


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    return prefix + '_' + uuid4().hex[:12]


@contextmanager
def connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA_DIR / 'workspace.db', timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    (DATA_DIR / 'datasets').mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS datasets (id TEXT PRIMARY KEY, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (id TEXT PRIMARY KEY, document TEXT NOT NULL);
        ''')
    for experiment in all_items('experiments'):
        if experiment['status'] in ('queued', 'running'):
            experiment.update(status='failed', error='服务在实验完成前停止，请重新运行。')
            put('experiments', experiment)


def put(table, document):
    if table not in ('datasets', 'models', 'experiments', 'settings'):
        raise ValueError('Invalid table')
    with connection() as db:
        db.execute(f'INSERT OR REPLACE INTO {table} (id, document) VALUES (?, ?)',
                   (document['id'], json.dumps(document, ensure_ascii=False, allow_nan=False)))
    return document


def get(table, item_id):
    with connection() as db:
        row = db.execute(f'SELECT document FROM {table} WHERE id=?', (item_id,)).fetchone()
    return json.loads(row['document']) if row else None


def all_items(table):
    with connection() as db:
        rows = db.execute(f'SELECT document FROM {table} ORDER BY rowid DESC').fetchall()
    return [json.loads(row['document']) for row in rows]


def delete(table, item_id):
    with connection() as db:
        db.execute(f'DELETE FROM {table} WHERE id=?', (item_id,))
