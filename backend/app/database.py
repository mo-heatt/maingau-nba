import json
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parents[2]

def path():return Path(os.environ.get('NBA_DB_PATH',str(ROOT/'data/nba.sqlite')))

@contextmanager
def connect():
    path().parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path(),timeout=30)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:yield conn;conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()

def initialize():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS source_records(id INTEGER PRIMARY KEY,source TEXT NOT NULL,customer_id TEXT,payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS source_customer ON source_records(customer_id,source);
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY,customer_id TEXT NOT NULL,decision_id TEXT NOT NULL,status TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS overrides(customer_id TEXT PRIMARY KEY,offer_id TEXT,note TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS drafts(id INTEGER PRIMARY KEY,customer_id TEXT NOT NULL,decision_id TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,generator TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,customer_id TEXT,payload TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        PRAGMA user_version=1;
        ''')
        c.execute('INSERT OR IGNORE INTO settings VALUES (1,1,?)',(json.dumps({'contact_cap_30d':3,'min_dclv_eur':0,'offers_off':[],'channels_off':[],'priorities':{},'tone_mode':'mirror','content_approvals':{}}),))

def audit(c,kind,payload,customer_id=None):
    c.execute('INSERT INTO audit(kind,customer_id,payload) VALUES (?,?,?)',(kind,customer_id,json.dumps(payload,ensure_ascii=False)))
