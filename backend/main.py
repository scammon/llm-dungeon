"""Application entrypoint.

Run from the repo root (so the root game modules import as top-level):

    uvicorn backend.main:app --host 0.0.0.0 --port 8000

Serves:
  * /api/*            - the game API (see backend/api.py)
  * everything else   - the built frontend SPA (frontend/dist), if present

In production (Dailey) the frontend is built at image-build time and served
from here, so the whole app is one origin.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import db
from backend.api import router

app = FastAPI(title="llm-dungeon")

# Same-origin in prod; permissive CORS only helps local dev (vite on :5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def _startup():
    db.init_db()


@app.get("/api/health")
def health():
    return {"ok": True, "store": type(db.get_store()).__name__}


# ---------------------------------------------------------------------------
# Static SPA (built frontend)
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(_REPO_ROOT, "frontend", "dist")

if os.path.isdir(DIST):
    assets = os.path.join(DIST, "assets")
    if os.path.isdir(assets):
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = os.path.join(DIST, path)
        if path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(DIST, "index.html"))
else:
    @app.get("/")
    def root():
        return JSONResponse({
            "app": "llm-dungeon",
            "note": "Frontend not built. Run `npm --prefix frontend install && "
                    "npm --prefix frontend run build`, then reload.",
            "api": "/api/saves",
        })
