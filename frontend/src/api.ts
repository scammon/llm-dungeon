import type { Action, SaveSummary, Snapshot } from "./types";

// Same origin in production (backend serves the SPA). In dev, vite proxies /api.
const BASE = "";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j && j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const listSaves = () => req<SaveSummary[]>("/api/saves");

export const createSave = (name: string) =>
  req<SaveSummary>("/api/saves", { method: "POST", body: JSON.stringify({ name }) });

export const deleteSave = (id: string) =>
  req<{ ok: boolean }>(`/api/saves/${id}`, { method: "DELETE" });

export const getState = (id: string) => req<Snapshot>(`/api/saves/${id}/state`);

export const doAction = (id: string, action: Action) =>
  req<Snapshot>(`/api/saves/${id}/action`, { method: "POST", body: JSON.stringify(action) });

// --- active-save persistence (cookie) -------------------------------------
const COOKIE = "llm_dungeon_save";

export function getActiveSave(): string | null {
  const m = document.cookie.match(new RegExp(`(?:^|; )${COOKIE}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : null;
}

export function setActiveSave(id: string | null) {
  if (id) {
    document.cookie = `${COOKIE}=${encodeURIComponent(id)}; path=/; max-age=${60 * 60 * 24 * 365}`;
  } else {
    document.cookie = `${COOKIE}=; path=/; max-age=0`;
  }
}
