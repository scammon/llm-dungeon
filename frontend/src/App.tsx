import { useCallback, useEffect, useState } from "react";
import type { Action, SaveSummary, Snapshot } from "./types";
import {
  listSaves,
  createSave as apiCreate,
  deleteSave as apiDelete,
  getState,
  doAction as apiAction,
  getActiveSave,
  setActiveSave,
} from "./api";
import { Icon } from "./components/Icon";
import { SaveSelect } from "./components/SaveSelect";
import { PlayerPanel } from "./components/PlayerPanel";
import { Hub } from "./components/Hub";
import { Explore } from "./components/Explore";
import { Combat } from "./components/Combat";
import { End } from "./components/End";
import { Feed } from "./components/Feed";

export default function App() {
  const [saves, setSaves] = useState<SaveSummary[]>([]);
  const [activeId, setActiveIdState] = useState<string | null>(getActiveSave());
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshSaves = useCallback(async () => {
    setSaves(await listSaves());
  }, []);

  // Initial load: fetch saves, then resume the active save if it still exists.
  useEffect(() => {
    (async () => {
      try {
        const list = await listSaves();
        setSaves(list);
        const id = getActiveSave();
        if (id && list.some((s) => s.id === id)) {
          setActiveIdState(id);
          setSnap(await getState(id));
        }
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const selectSave = useCallback(async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      setActiveSave(id);
      setActiveIdState(id);
      setSnap(await getState(id));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const createSave = useCallback(
    async (name: string) => {
      setBusy(true);
      setError(null);
      try {
        const row = await apiCreate(name);
        await refreshSaves();
        await selectSave(row.id);
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    },
    [refreshSaves, selectSave]
  );

  const deleteSave = useCallback(
    async (id: string) => {
      setBusy(true);
      setError(null);
      try {
        await apiDelete(id);
        if (id === activeId) {
          setActiveSave(null);
          setActiveIdState(null);
          setSnap(null);
        }
        await refreshSaves();
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    },
    [activeId, refreshSaves]
  );

  const backToSaves = useCallback(() => {
    setActiveSave(null);
    setActiveIdState(null);
    setSnap(null);
    setError(null);
  }, []);

  const doAction = useCallback(
    async (a: Action) => {
      if (!activeId || busy) return;
      setBusy(true);
      setError(null);
      try {
        setSnap(await apiAction(activeId, a));
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    },
    [activeId, busy]
  );

  if (loading) {
    return (
      <div className="app-loading">
        <Icon name="ui_skull" size={48} className="c-essence" />
        <p className="muted">Entering the Deep…</p>
      </div>
    );
  }

  if (error && !snap) {
    return (
      <div className="app-loading">
        <Icon name="ui_skull" size={48} />
        <p>Something went wrong: {error}</p>
        <button className="btn" onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    );
  }

  if (!snap) {
    return (
      <SaveSelect
        saves={saves}
        busy={busy}
        onSelect={selectSave}
        onCreate={createSave}
        onDelete={deleteSave}
      />
    );
  }

  const inRun = snap.screen === "explore" || snap.screen === "combat";
  const canSell = !!(
    snap.room?.npcs?.some((n) => n.role === "shop" || n.role === "blacksmith")
  );

  return (
    <div className="game">
      <header className="topbar">
        <div className="topbar-left">
          <Icon name="ui_skull" size={22} className="c-essence" />
          <span className="topbar-title">The Deep</span>
          <span className="topbar-save muted">{saveName(saves, activeId)}</span>
        </div>
        <div className="topbar-right">
          {inRun && snap.room && (
            <span className="chip" title="Current depth">
              depth {snap.room.depth}
            </span>
          )}
          <span className="chip c-essence" title="Banked essence">
            <Icon name="ui_essence" size={14} /> {snap.meta.essence}
          </span>
          <span
            className={`chip llm ${snap.llm ? "on" : "off"}`}
            title={snap.llm ? "Narrator (LLM) live" : "Narrator offline — using fallback text"}
          >
            {snap.llm ? "narrator live" : "narrator off"}
          </span>
          <button className="btn btn-ghost" onClick={backToSaves} disabled={busy}>
            Saves
          </button>
        </div>
      </header>

      {error && (
        <div className="error-bar" onClick={() => setError(null)}>
          {error} (click to dismiss)
        </div>
      )}

      <div className="content">
        <div className="stage">
          {snap.screen === "hub" && <Hub snap={snap} onAction={doAction} />}
          {snap.screen === "explore" && <Explore snap={snap} onAction={doAction} />}
          {snap.screen === "combat" && <Combat snap={snap} onAction={doAction} />}
          {(snap.screen === "dead" || snap.screen === "victory") && (
            <End snap={snap} onAction={doAction} />
          )}
          <Feed items={snap.feed} />
        </div>
        {snap.player && (
          <PlayerPanel player={snap.player} canSell={canSell} onAction={doAction} />
        )}
      </div>

      {busy && <div className="busy-veil" />}
    </div>
  );
}

function saveName(saves: SaveSummary[], id: string | null): string {
  return saves.find((s) => s.id === id)?.name ?? "";
}
