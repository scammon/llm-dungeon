import type { Action, Snapshot } from "../types";
import { Icon } from "./Icon";

const STAT_LABEL: Record<string, string> = {
  hp: "Vitality",
  mana: "Focus",
  atk: "Might",
  defense: "Guard",
  sp_power: "Spellcraft",
};

export function Hub({ snap, onAction }: { snap: Snapshot; onAction: (a: Action) => void }) {
  const m = snap.meta;
  return (
    <div className="hub">
      <div className="hub-head">
        <Icon name="ui_essence" size={22} className="c-essence" />
        <span className="hub-essence">
          <b>{m.essence}</b> essence banked
        </span>
        <span className="muted small">
          · {m.runs} runs · {m.deaths} deaths · best depth {m.best_depth}
        </span>
      </div>

      <button className="btn btn-primary btn-big" onClick={() => onAction({ type: "hub_begin" })}>
        <Icon name="ui_skull" size={20} /> Begin the Descent
      </button>

      <div className="hub-cols">
        <div className="hub-col">
          <h3>
            <Icon name="ui_sp" size={16} className="c-essence" /> Upgrades
          </h3>
          <div className="upgrade-list">
            {m.upgrades.map((u) => (
              <button
                key={u.stat}
                className="upgrade-item"
                disabled={m.essence < u.cost}
                onClick={() => onAction({ type: "hub_upgrade", stat: u.stat })}
                title={`Costs ${u.cost} essence`}
              >
                <span className="upgrade-name">
                  {STAT_LABEL[u.stat] || u.stat} <em className="muted">Lv {u.level}</em>
                </span>
                <span className="upgrade-cost c-essence">
                  <Icon name="ui_essence" size={13} /> {u.cost}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="hub-col">
          <h3>
            <Icon name="tome" size={16} className="c-essence" /> Grimoire
            <span className="muted small"> ({m.grimoire.length})</span>
          </h3>
          {m.grimoire.length === 0 && (
            <div className="muted small">
              No spells yet. Learn them from tomes and the Sage — they are kept forever.
            </div>
          )}
          <div className="grimoire-list">
            {m.grimoire.map((sp) => (
              <button
                key={sp.id}
                className="grimoire-item"
                disabled={sp.attune_max || m.essence < sp.attune_cost}
                onClick={() => onAction({ type: "hub_attune", spell: sp.id })}
                title={`${sp.desc}\nAttune cost: ${sp.attune_cost} essence`}
              >
                <span className="grimoire-name">
                  {sp.name} <em className="muted">T{sp.tier}</em>
                  {sp.attuned > 0 && <em className="c-essence"> +{sp.attuned}</em>}
                </span>
                <span className="grimoire-cost c-essence">
                  {sp.attune_max ? "max" : (
                    <>
                      <Icon name="ui_essence" size={13} /> {sp.attune_cost}
                    </>
                  )}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {m.codex.length > 0 && (
        <div className="hub-col">
          <h3>
            <Icon name="ui_trophy" size={16} className="c-essence" /> Codex
            <span className="muted small"> ({m.codex.length})</span>
          </h3>
          <div className="codex-list">
            {m.codex.map((c) => (
              <details key={c.key} className="codex-item">
                <summary>{c.title}</summary>
                <p>{c.text}</p>
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
