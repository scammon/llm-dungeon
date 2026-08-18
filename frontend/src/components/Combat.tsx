import { useState } from "react";
import type { Action, Snapshot } from "../types";
import { Icon } from "./Icon";
import { Sprite } from "./Sprite";
import { DungeonView } from "./DungeonView";

function needsTarget(kind: string, aoe: boolean): boolean {
  return (kind === "damage" || kind === "debuff" || kind === "control") && !aoe;
}

export function Combat({ snap, onAction }: { snap: Snapshot; onAction: (a: Action) => void }) {
  const [spell, setSpell] = useState("");
  const [target, setTarget] = useState(1);
  const [item, setItem] = useState("");
  const combat = snap.combat!;
  const player = snap.player!;
  const spells = player.spells;
  const consumables = player.inventory.filter((i) => i.slot === "consumable");
  const mons = combat.monsters;

  const selSpell = spells.find((s) => s.id === spell);
  const needTgt = selSpell ? needsTarget(selSpell.kind, selSpell.aoe) : false;

  return (
    <div className="combat">
      <div className="combat-head muted small">
        Turn {combat.turn}
        {combat.defending && <span className="c-shield"> · defending</span>}
      </div>

      <DungeonView roomType={snap.room?.type}>
        {mons.map((m) => (
          <div key={m.n} className={`actor actor-monster ${m.is_boss ? "boss" : ""}`}>
            <Sprite name={m.name} size={m.is_boss ? 188 : 148} />
            <div className="actor-name">
              {m.name}
              {m.is_boss && <em className="boss-tag">BOSS</em>}
            </div>
            <div className="bar bar-sm">
              <div
                className="bar-fill"
                style={{ width: `${(m.hp / m.max_hp) * 100}%`, background: "var(--hp)" }}
              />
              <span className="bar-label">
                {m.hp}/{m.max_hp}
              </span>
            </div>
            {m.status.length > 0 && (
              <div className="actor-status muted small">{m.status.join(", ")}</div>
            )}
          </div>
        ))}
      </DungeonView>

      <div className="combat-actions">
        <div className="combat-col">
          <h4>Attack</h4>
          {mons.map((m) => (
            <button key={m.n} className="btn" onClick={() => onAction({ type: "attack", n: m.n })}>
              <Icon name="sword" size={15} /> {m.name}
            </button>
          ))}
        </div>

        <div className="combat-col">
          <h4>Cast</h4>
          <select value={spell} onChange={(e) => setSpell(e.target.value)}>
            <option value="">— spell —</option>
            {spells.map((s) => (
              <option key={s.id} value={s.id} disabled={player.mana < s.cost}>
                {s.name} ({s.cost} mana{player.mana < s.cost ? ", low mana" : ""})
              </option>
            ))}
          </select>
          {needTgt && (
            <select value={target} onChange={(e) => setTarget(+e.target.value)}>
              {mons.map((m) => (
                <option key={m.n} value={m.n}>
                  at {m.name}
                </option>
              ))}
            </select>
          )}
          <button
            className="btn btn-primary"
            disabled={!spell}
            onClick={() =>
              onAction({ type: "cast", spell, ...(needTgt ? { n: target } : {}) })
            }
          >
            <Icon name="ui_sp" size={15} /> Cast
          </button>
        </div>

        <div className="combat-col">
          <h4>Other</h4>
          <button className="btn" onClick={() => onAction({ type: "defend" })}>
            <Icon name="armor" size={15} /> Defend
          </button>
          <button className="btn" onClick={() => onAction({ type: "flee" })}>
            Flee
          </button>
          {consumables.length > 0 && (
            <>
              <select value={item} onChange={(e) => setItem(e.target.value)}>
                <option value="">— item —</option>
                {consumables.map((c) => (
                  <option key={c.n} value={c.n}>
                    {c.name}
                  </option>
                ))}
              </select>
              <button
                className="btn"
                disabled={!item}
                onClick={() => onAction({ type: "use", n: +item })}
              >
                <Icon name="potion" size={15} /> Use
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
