"""In-memory engine cache keyed by save id.

Holds one Engine per active save. The Engine carries the live run state
(floors/player/combat) plus the MetaSave. Meta is persisted to the DB after
every action; the run state is ephemeral (a cold start rebuilds the engine
from the saved meta, i.e. back at camp).

Per-save locks serialize a single player's actions without blocking other
saves. The LLM (narrator) call happens inside engine.act(), so the lock is
held across it — that's correct: one player's turns are sequential.
"""
import threading

from backend import db
from backend.engine import Engine
from backend.narrator import get_narrator

_engines = {}
_locks = {}
_global_lock = threading.Lock()


def lock_for(save_id):
    with _global_lock:
        if save_id not in _locks:
            _locks[save_id] = threading.Lock()
        return _locks[save_id]


def get_engine(save_id):
    """Return the Engine for a save, building it from the DB meta if cold.

    Caller must already hold lock_for(save_id). Returns None if the save does
    not exist.
    """
    eng = _engines.get(save_id)
    if eng is not None:
        return eng
    meta = db.load_meta(save_id)
    if meta is None:
        return None
    eng = Engine(meta, get_narrator())
    _engines[save_id] = eng
    return eng


def persist(save_id, engine):
    db.get_store().update_meta(save_id, engine.meta.to_dict())


def drop(save_id):
    with _global_lock:
        _engines.pop(save_id, None)
