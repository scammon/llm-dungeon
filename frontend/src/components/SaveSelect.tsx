import { useState } from "react";
import type { SaveSummary } from "../types";
import { Icon } from "./Icon";
import { fmtDate } from "../helpers";

export function SaveSelect({
  saves,
  onSelect,
  onCreate,
  onDelete,
  busy,
}: {
  saves: SaveSummary[];
  onSelect: (id: string) => void;
  onCreate: (name: string) => void;
  onDelete: (id: string) => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");

  return (
    <div className="save-select">
      <div className="save-hero">
        <Icon name="ui_skull" size={64} className="c-essence" />
        <h1>The Deep</h1>
        <p className="muted">A roguelite dungeon, narrated by a language model.</p>
      </div>

      <div className="save-create">
        <input
          value={name}
          maxLength={40}
          placeholder="Name a new save (e.g. Run 1)"
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && name.trim()) {
              onCreate(name.trim());
              setName("");
            }
          }}
        />
        <button
          className="btn btn-primary"
          disabled={busy || !name.trim()}
          onClick={() => {
            onCreate(name.trim());
            setName("");
          }}
        >
          New Save
        </button>
      </div>

      <div className="save-list">
        {saves.length === 0 && <div className="muted">No saves yet. Create one to begin.</div>}
        {saves.map((s) => (
          <div key={s.id} className="save-card">
            <button className="save-open" disabled={busy} onClick={() => onSelect(s.id)}>
              <div className="save-name">{s.name}</div>
              <div className="save-meta muted">
                <span title="Banked essence">
                  <Icon name="ui_essence" size={13} className="c-essence" /> {s.essence}
                </span>
                <span title="Runs">
                  <Icon name="ui_trophy" size={13} /> {s.runs} runs
                </span>
                <span title="Deaths">
                  <Icon name="ui_skull" size={13} /> {s.deaths}
                </span>
                <span title="Best depth">best d{s.best_depth}</span>
                <span title="Spells learned">{s.spells} spells</span>
                <span title="Lore found">{s.lore} lore</span>
              </div>
              <div className="save-date muted small">{fmtDate(s.updated_at)}</div>
            </button>
            <button
              className="btn btn-ghost save-del"
              title="Delete save"
              disabled={busy}
              onClick={() => {
                if (confirm(`Delete save "${s.name}"? This cannot be undone.`)) onDelete(s.id);
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
