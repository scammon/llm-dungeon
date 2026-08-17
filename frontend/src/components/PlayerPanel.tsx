import type { Action, InvItem, Player } from "../types";
import { Icon } from "./Icon";
import { itemIcon, rarityColor, statLine } from "../helpers";

const SLOTS = ["weapon", "armor", "helm", "boots", "trinket"];

// Mirrors the backend sell price: equipment = value//2, consumables = power//2.
function sellPriceOf(it: InvItem): number {
  const isEquip = SLOTS.includes(it.slot);
  return isEquip
    ? Math.max(1, Math.floor((it.value ?? 0) / 2))
    : Math.max(1, Math.floor((typeof it.power === "number" ? it.power : 4) / 2));
}

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className="bar">
      <div className="bar-fill" style={{ width: `${pct}%`, background: color }} />
      <span className="bar-label">
        {value}/{max}
      </span>
    </div>
  );
}

export function PlayerPanel({ player, canSell, onAction }: { player: Player; canSell: boolean; onAction: (a: Action) => void }) {
  return (
    <aside className="panel">
      <div className="panel-block">
        <div className="stat-row">
          <Icon name="ui_heart" size={16} className="c-hp" />
          <Bar value={player.hp} max={player.max_hp} color="var(--hp)" />
        </div>
        <div className="stat-row">
          <Icon name="ui_mana" size={16} className="c-mana" />
          <Bar value={player.mana} max={player.max_mana} color="var(--mana)" />
        </div>
        <div className="mini-stats">
          <span title="Attack">
            <b>{player.atk}</b> atk
          </span>
          <span title="Defense">
            <b>{player.def}</b> def
          </span>
          <span title="Spell power">
            <b>{player.sp}</b> sp
          </span>
          {player.shield > 0 && (
            <span title="Shield" className="c-shield">
              <b>{player.shield}</b> shield
            </span>
          )}
          <span title="Gold">
            <Icon name="ui_coin" size={13} className="c-gold" /> <b>{player.gold}</b>
          </span>
          <span title="Essence this run" className="c-essence">
            <Icon name="ui_essence" size={13} /> <b>{player.essence_run}</b>
          </span>
        </div>
        {player.status.length > 0 && (
          <div className="status-row">
            {player.status.map((s, i) => (
              <span key={i} className="status-chip" title={`${s.kind} for ${s.turns} turns`}>
                {s.kind} ({s.turns})
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="panel-block">
        <h3>Equipment</h3>
        <div className="equip-grid">
          {SLOTS.map((slot) => {
            const it = player.equipment[slot];
            return (
              <button
                key={slot}
                className={`equip-slot ${it ? "filled" : ""}`}
                title={
                  it
                    ? `${it.name} (${it.rarity})\n${statLine(it.stats)}\nClick to unequip`
                    : `Empty ${slot}`
                }
                onClick={() => it && onAction({ type: "unequip", slot })}
                style={it ? { color: rarityColor(it.rarity) } : undefined}
              >
                <Icon name={itemIcon(slot, it?.name)} size={26} />
                <span className="equip-name">{it ? it.name : slot}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="panel-block">
        <h3>
          Pack <span className="muted">({player.inventory.length})</span>
        </h3>
        {player.inventory.length === 0 && <div className="muted small">Empty.</div>}
        <div className="inv-list">
          {player.inventory.map((it) => {
            const isEquip = SLOTS.includes(it.slot);
            const isConsumable = it.slot === "consumable";
            const sell = canSell ? sellPriceOf(it) : null;
            const detail = isEquip
              ? statLine(it.stats)
              : `${it.effect || ""} ${it.power ?? ""}`.trim();
            const tooltip = [
              `${it.name} (${it.rarity})`,
              detail,
              sell !== null ? `Sell for ${sell}g` : null,
            ]
              .filter(Boolean)
              .join("\n");
            return (
              <div key={it.n} className="inv-item" title={tooltip}>
                <span className="inv-n">{it.n}</span>
                <Icon name={itemIcon(it.slot, it.name)} size={20} style={{ color: rarityColor(it.rarity) }} />
                <div className="inv-main">
                  <span className="inv-name" style={{ color: rarityColor(it.rarity) }}>
                    {it.name}
                  </span>
                  {detail && <span className="inv-sub muted">{detail}</span>}
                </div>
                <div className="inv-actions">
                  {isEquip && (
                    <button className="btn-tiny" onClick={() => onAction({ type: "equip", arg: String(it.n) })}>
                      Equip
                    </button>
                  )}
                  {isConsumable && (
                    <button className="btn-tiny" onClick={() => onAction({ type: "use", n: it.n })}>
                      Use
                    </button>
                  )}
                  {sell !== null && (
                    <button className="btn-tiny btn-sell" onClick={() => onAction({ type: "sell", n: it.n })}>
                      Sell {sell}g
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {player.spells.length > 0 && (
        <div className="panel-block">
          <h3>
            Spells <span className="muted">({player.spells.length})</span>
          </h3>
          <div className="spell-list">
            {player.spells.map((sp) => (
              <div key={sp.id} className="spell-item" title={sp.desc}>
                <span className="spell-name">
                  {sp.name}
                  {sp.attuned > 0 && <em className="c-essence"> +{sp.attuned}</em>}
                </span>
                <span className="muted small">
                  {sp.cost} mana · {sp.power} pw{sp.aoe ? " · aoe" : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
