"""Connection-per-operation SQLite store; owner checks, expiry, secure deletion."""
import json,sqlite3,time,uuid
from contextlib import contextmanager
from fastapi import HTTPException
from .config import DB_PATH,RETENTION
@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DB_PATH,timeout=15)
    try:
        db.execute('PRAGMA secure_delete=ON')
        db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, owner TEXT NOT NULL, created REAL NOT NULL, data TEXT NOT NULL)')
        db.execute('DELETE FROM sessions WHERE created < ?', (time.time()-RETENTION,))
        yield db
        db.commit()
    finally:db.close()
def create(owner,data):
    i=str(uuid.uuid4())
    with connection() as db:db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(i,owner,time.time(),json.dumps(data)))
    return i
def get(i,owner):
    with connection() as db:r=db.execute('SELECT data FROM sessions WHERE id=? AND owner=?',(i,owner)).fetchone()
    if not r:raise HTTPException(404,'Resume not found or expired.')
    return json.loads(r[0])
def put(i,owner,data):
    with connection() as db:
        c=db.execute('UPDATE sessions SET data=? WHERE id=? AND owner=?',(json.dumps(data),i,owner))
        if not c.rowcount:raise HTTPException(404,'Resume not found or expired.')
def delete(i,owner):
    with connection() as db:db.execute('DELETE FROM sessions WHERE id=? AND owner=?',(i,owner))
