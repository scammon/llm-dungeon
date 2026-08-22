"""FastAPI routes for the web client.

The client is a thin SPA: it lists/creates/deletes saves, fetches a save's
current state snapshot, and posts one action at a time. Every response to a
state/action call is the full engine snapshot the UI renders.
"""
from typing import Optional, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import db, store
from backend.db import DuplicateName

router = APIRouter(prefix="/api")


class CreateSave(BaseModel):
    name: str


class Action(BaseModel):
    type: str
    n: Optional[int] = None
    spell: Optional[str] = None
    stat: Optional[str] = None
    arg: Optional[str] = None
    slot: Optional[str] = None
    text: Optional[str] = None
    room: Optional[Union[int, str]] = None


@router.get("/saves")
def list_saves():
    return [row.summary() for row in db.get_store().list()]


@router.post("/saves")
def create_save(body: CreateSave):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "A save name is required.")
    if len(name) > 40:
        raise HTTPException(400, "Save name is too long (max 40).")
    try:
        row = db.get_store().create(name)
    except DuplicateName as e:
        raise HTTPException(409, str(e))
    return row.summary()


@router.delete("/saves/{save_id}")
def delete_save(save_id: str):
    store.drop(save_id)
    if not db.get_store().delete(save_id):
        raise HTTPException(404, "Save not found.")
    return {"ok": True}


@router.get("/saves/{save_id}/state")
def get_state(save_id: str):
    with store.lock_for(save_id):
        eng = store.get_engine(save_id)
        if eng is None:
            raise HTTPException(404, "Save not found.")
        return eng.snapshot()


@router.post("/saves/{save_id}/action")
def do_action(save_id: str, body: Action):
    with store.lock_for(save_id):
        eng = store.get_engine(save_id)
        if eng is None:
            raise HTTPException(404, "Save not found.")
        snap = eng.act(body.model_dump(exclude_none=True))
        store.persist(save_id, eng)
        return snap
