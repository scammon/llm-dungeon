"""Save persistence.

A "save" is a named MetaSave (the roguelite meta-progression). The in-progress
run (floors/player/combat) IS also persisted in a `run` JSONB column, so a cold
start resumes the run where it left off instead of resetting to camp. Meta
always persists; run persists only while a run is in progress.

Two interchangeable backends behind one interface:
  * PostgresStore  - the real Dailey DB (DATABASE_URL or DB_* vars).
  * MemoryStore    - in-process dict; used when no DB is configured so the app
                     still runs for local dev / smoke tests.

The store is chosen once at import via get_store().
"""
import os
import json
import uuid
import time
import threading
from datetime import datetime, timezone

from meta import MetaSave, DEFAULTS


def _now():
    return datetime.now(timezone.utc)


def _default_meta():
    return MetaSave().to_dict()


class SaveRow:
    """A lightweight, JSON-friendly view of a save (no full meta)."""
    def __init__(self, id, name, meta, created_at, updated_at, run=None):
        self.id = id
        self.name = name
        self.meta = meta
        self.created_at = created_at
        self.updated_at = updated_at
        self.run = run

    def summary(self):
        m = self.meta
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "essence": m.get("essence", 0),
            "runs": m.get("runs", 0),
            "deaths": m.get("deaths", 0),
            "best_depth": m.get("best_depth", 0),
            "spells": len(m.get("grimoire", [])),
            "lore": len(m.get("codex", {})),
        }


# ===========================================================================
# Postgres backend
# ===========================================================================
class PostgresStore:
    def __init__(self, dsn):
        import psycopg
        import psycopg.rows
        self._psycopg = psycopg
        self.dsn = dsn
        self._lock = threading.Lock()

    def _connect(self):
        import psycopg.rows
        conn = self._psycopg.connect(self.dsn, autocommit=True)
        # Return dict-like rows so _row() can index by column name.
        conn.row_factory = psycopg.rows.dict_row
        return conn

    def init(self):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS saves (
                    id          UUID PRIMARY KEY,
                    name        TEXT NOT NULL UNIQUE,
                    meta        JSONB NOT NULL,
                    run         JSONB,
                    created_at  TIMESTAMPTZ NOT NULL,
                    updated_at  TIMESTAMPTZ NOT NULL
                )
            """)
            # migrate pre-existing tables that lack the run column
            cur.execute("ALTER TABLE saves ADD COLUMN IF NOT EXISTS run JSONB")

    def _row(self, cur, r):
        meta = r["meta"]
        if isinstance(meta, (str, bytes)):
            meta = json.loads(meta)
        run = r["run"]
        if isinstance(run, (str, bytes)):
            run = json.loads(run)
        return SaveRow(str(r["id"]), r["name"], meta,
                        r["created_at"].isoformat(), r["updated_at"].isoformat(), run)

    def list(self):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, name, meta, run, created_at, updated_at "
                        "FROM saves ORDER BY updated_at DESC")
            return [self._row(cur, r) for r in cur.fetchall()]

    def get(self, save_id):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, name, meta, run, created_at, updated_at "
                        "FROM saves WHERE id = %s", (save_id,))
            r = cur.fetchone()
            return self._row(cur, r) if r else None

    def create(self, name):
        from psycopg.types.json import Jsonb
        sid = str(uuid.uuid4())
        now = _now()
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO saves (id, name, meta, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (sid, name, Jsonb(_default_meta()), now, now))
            return SaveRow(sid, name, _default_meta(), now.isoformat(), now.isoformat())
        except Exception as e:
            if "unique" in str(e).lower():
                raise DuplicateName(name)
            raise

    def delete(self, save_id):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM saves WHERE id = %s", (save_id,))
            return cur.rowcount > 0

    def update_meta(self, save_id, meta):
        from psycopg.types.json import Jsonb
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE saves SET meta = %s, updated_at = %s WHERE id = %s",
                        (Jsonb(meta), _now(), save_id))
            return cur.rowcount > 0

    def update_run(self, save_id, run):
        from psycopg.types.json import Jsonb
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE saves SET run = %s, updated_at = %s WHERE id = %s",
                        (Jsonb(run) if run is not None else None, _now(), save_id))
            return cur.rowcount > 0


class DuplicateName(Exception):
    def __init__(self, name):
        self.name = name
        super().__init__(f"A save named '{name}' already exists.")


# ===========================================================================
# In-memory backend (local dev / no DB configured)
# ===========================================================================
class MemoryStore:
    def __init__(self):
        self._rows = {}
        self._lock = threading.Lock()

    def init(self):
        pass

    def list(self):
        with self._lock:
            rows = list(self._rows.values())
        rows.sort(key=lambda r: r.updated_at, reverse=True)
        return rows

    def get(self, save_id):
        with self._lock:
            return self._rows.get(save_id)

    def create(self, name):
        with self._lock:
            for r in self._rows.values():
                if r.name == name:
                    raise DuplicateName(name)
            sid = str(uuid.uuid4())
            now = _now().isoformat()
            row = SaveRow(sid, name, _default_meta(), now, now)
            self._rows[sid] = row
            return row

    def delete(self, save_id):
        with self._lock:
            return self._rows.pop(save_id, None) is not None

    def update_meta(self, save_id, meta):
        with self._lock:
            row = self._rows.get(save_id)
            if not row:
                return False
            row.meta = meta
            row.updated_at = _now().isoformat()
            return True

    def update_run(self, save_id, run):
        with self._lock:
            row = self._rows.get(save_id)
            if not row:
                return False
            row.run = run
            row.updated_at = _now().isoformat()
            return True


# ===========================================================================
# Selection
# ===========================================================================
def _dsn_from_env():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Dailey may hand us a postgres:// URL; psycopg3 accepts it directly.
        return url
    host = os.environ.get("DB_HOST")
    if host:
        port = os.environ.get("DB_PORT", "5432")
        user = os.environ.get("DB_USER", "postgres")
        pw = os.environ.get("DB_PASSWORD", "")
        db = os.environ.get("DB_NAME", "postgres")
        return f"host={host} port={port} user={user} password={pw} dbname={db}"
    return None


_store = None
def get_store():
    global _store
    if _store is None:
        dsn = _dsn_from_env()
        if dsn:
            _store = PostgresStore(dsn)
        else:
            _store = MemoryStore()
    return _store


def init_db():
    get_store().init()


def load_meta(save_id):
    """Return a MetaSave for a save id (or None)."""
    row = get_store().get(save_id)
    if not row:
        return None
    return MetaSave(**row.meta)


def load_run(save_id):
    """Return the persisted run-state for a save (or None)."""
    row = get_store().get(save_id)
    if not row or not row.run:
        return None
    return row.run
