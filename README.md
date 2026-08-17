# The Deep — an LLM-narrated roguelite

A single-player roguelite dungeon crawler. The **game logic runs in Python on the
server**; the browser is a thin custom React/TypeScript UI over a small REST API.
The **narrator** (room scenes, monster intros, NPC dialogue, deaths, lore) is an
LLM behind **Dailey AI**. Saves live in a **Postgres** database.

> Originally a Python CLI (`llm-dungeon`). This repo is the web port: same game
> engine, new UI, LLM narrator, and server-side persistence.

## Architecture

```
Browser (React + TS, Vite)
   │  fetch /api/*
   ▼
FastAPI (backend/)
   ├── engine.py     I/O-free game engine (rooms, combat, meta-progression)
   ├── narrator.py   Dailey AI client (OpenAI-compatible) w/ fallback text
   ├── store.py      in-memory engine cache, one lock per save
   ├── db.py         Postgres save store (or in-memory when no DB)
   ├── api.py        REST routes
   └── main.py       app + serves the built frontend SPA
   │
   ├── root modules (single source of truth, imported as top-level):
   │     data.py  config.py  gen.py  player.py  combat.py  meta.py
   ▼
Postgres (saves)  +  Dailey AI (narration)
```

- **One origin in production.** The backend builds and serves the frontend, so the
  app is a single deployable.
- **No auth.** Single-user app; the active save is tracked in a browser cookie and
  passed explicitly in the API path.
- **Graceful degradation.** If Dailey AI is unreachable, the narrator returns
  `None` and the engine uses its built-in fallback text — the game always plays.

## How to play

- **Hub** — bank essence, buy permanent upgrades, learn spells (grimoire), read
  discovered lore (codex), then descend.
- **Explore** — move between rooms (doors), loot, talk to NPCs, buy/sell/equip
  gear, or type freeform commands (`buy 1`, `equip sword`, `examine chest`,
  `talk merchant`, …).
- **Combat** — attack, cast spells, or flee. Survive to the boss every 3rd floor;
  reach depth 10 to win.
- **Meta** — essence and knowledge persist across runs.

## Local development

Prereqs: Python 3.11+, Node 20+.

```bash
# 1. Backend
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# 2. Frontend
npm --prefix frontend install
npm --prefix frontend run build        # outputs frontend/dist

# 3. Run (from repo root, so root modules import as top-level)
.venv/bin/python -m uvicorn backend.main:app --port 8000
# open http://localhost:8000
```

Without a `DATABASE_URL` the app uses an in-memory store (fine for trying the UI;
saves do not persist across restarts). To use Postgres, set `DATABASE_URL` (see
`.env.example`).

**Frontend dev server** (hot reload, proxies `/api` to `:8000`):

```bash
npm --prefix frontend run dev         # http://localhost:5173
```

**Headless engine test** (no server, no DB):

```bash
python3 -m backend.smoke_test
```

## Environment variables

| Var | Purpose |
|-----|---------|
| `DATABASE_URL` | Postgres connection string (managed DB on Dailey). |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | Fallback if `DATABASE_URL` is unset. |
| `DAILEY_AI_BASE_URL` / `DAILEY_AI_KEY` / `DAILEY_AI_MODEL` | Dailey AI narrator (injected when enabled). |
| `DAILEY_AI_NOTHINK` / `DAILEY_AI_TIMEOUT` / `DAILEY_AI_TEMP` | Optional narrator tuning. |

See `.env.example`.

## Deploying to Dailey

The repo is a single Docker image (see `Dockerfile`): a Node stage builds the
frontend, a Python stage installs the backend and serves `frontend/dist`.

1. Push to GitHub.
2. Create a Dailey project from the repo.
3. Enable the **managed Postgres** database (injects `DATABASE_URL`).
4. Enable **Dailey AI** (injects `DAILEY_AI_*`).
5. Deploy. The app is served at the project's `*.dailey.cloud` URL.

## Project structure

```
backend/            FastAPI app (engine, narrator, store, db, api, main)
frontend/           React + TS + Vite UI
  public/icons/     36 monochrome SVG icons (equipment / monsters / UI)
  src/              components + api client + types
combat.py … meta.py reusable pure game logic (single source of truth)
Dockerfile          multi-stage build (node → python)
```

## Attribution

Icons from [game-icons.net](https://game-icons.net) (Lorc) — licensed
**CC BY 3.0**. Attribution: "Icons by Lorc on game-icons.net".
