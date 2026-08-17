import { useState } from "react";
import type { Action, Snapshot } from "../types";
import { Icon } from "./Icon";
import { DungeonMap } from "./DungeonMap";
import { DungeonView } from "./DungeonView";
import { rarityColor, npcSprite } from "../helpers";

// Turn a freeform line into a structured action when it matches a command,
// otherwise pass it through as freeform narration.
function parseCommand(text: string): Action {
  const t = text.trim();
  let m: RegExpMatchArray | null;
  if ((m = t.match(/^buy\s+(\d+)$/i))) return { type: "buy", n: +m[1] };
  if ((m = t.match(/^sell\s+(\d+)$/i))) return { type: "sell", n: +m[1] };
  if ((m = t.match(/^equip\s+(.+)$/i))) return { type: "equip", arg: m[1] };
  if ((m = t.match(/^unequip\s+(\w+)$/i))) return { type: "unequip", slot: m[1] };
  if ((m = t.match(/^drop\s+(.+)$/i))) return { type: "drop", arg: m[1] };
  if ((m = t.match(/^examine\s+(.+)$/i))) return { type: "examine", text: m[1] };
  if ((m = t.match(/^talk\s+(.+)$/i))) return { type: "talk", text: m[1] };
  return { type: "freeform", text: t };
}

export function Explore({ snap, onAction }: { snap: Snapshot; onAction: (a: Action) => void }) {
  const [cmd, setCmd] = useState("");
  const room = snap.room!;
  const npc = room.npcs[0];
  const depth = room.depth;
  const gold = snap.player?.gold ?? 0;

  const submit = () => {
    if (!cmd.trim()) return;
    onAction(parseCommand(cmd));
    setCmd("");
  };

  return (
    <div className="explore">
      {snap.map && <DungeonMap map={snap.map} />}
      <DungeonView>
        {npc && (
          <div className="actor actor-npc">
            <img
              className="sprite"
              src={`/sprites/${npcSprite(npc.role)}.svg`}
              alt={npc.name}
              width={150}
              height={158}
              draggable={false}
            />
            <div className="actor-name">{npc.name}</div>
          </div>
        )}
      </DungeonView>
      <div className="room">
        <div className="room-head">
          <span className="room-type">{room.label}</span>
          <span className="muted">· depth {depth}</span>
        </div>
        <p className="room-scene">{room.scene}</p>

        {npc && (
          <div className="npc-row">
            <Icon name="ui_trophy" size={18} className="c-gold" />
            <span>
              <b>{npc.name}</b> <em className="muted">({npc.role})</em>
            </span>
          </div>
        )}

        {(room.item_count > 0 || room.tome_count > 0 || room.has_lore) && (
          <div className="room-hints muted small">
            {room.item_count > 0 && <span>{room.item_count} item(s) here</span>}
            {room.tome_count > 0 && <span>{room.tome_count} tome(s)</span>}
            {room.has_lore && <span>a lore tablet</span>}
          </div>
        )}
      </div>

      {room.stock.length > 0 && (
        <div className="shop">
          <div className="shop-head">
            <Icon name="ui_coin" size={14} className="c-gold" />
            <span className="shop-title">{npc?.name ?? "Merchant"}'s wares</span>
            <span className="muted small">{gold}g</span>
          </div>
          <div className="shop-list">
            {room.stock.map((s) => (
              <div key={s.n} className="shop-item">
                <span className="shop-n">{s.n}</span>
                <span className="shop-name" style={{ color: rarityColor(s.rarity) }}>
                  {s.name}
                </span>
                <span className="shop-price c-gold">{s.value}g</span>
                <button
                  className="btn-tiny"
                  disabled={gold < s.value}
                  onClick={() => onAction({ type: "buy", n: s.n })}
                >
                  Buy
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="action-grid">
        {room.doors.map((d) => (
          <button key={d.n} className="btn" onClick={() => onAction({ type: "move", n: d.n })}>
            <span className="door-n">{d.n}</span> {d.label}
            {!d.discovered && <span className="muted"> ?</span>}
          </button>
        ))}
        {room.has_stairs && (
          <button className="btn btn-primary" onClick={() => onAction({ type: "descend" })}>
            <Icon name="ui_skull" size={16} /> Descend to depth {depth + 1}
          </button>
        )}
        {npc?.role === "sage" && (
          <button className="btn" onClick={() => onAction({ type: "learn" })}>
            Learn a spell
          </button>
        )}
        {(npc?.role === "hermit" || npc?.role === "blacksmith") && (
          <button className="btn" onClick={() => onAction({ type: "heal" })}>
            Be mended (15g)
          </button>
        )}
        {room.type === "camp" && (
          <button className="btn" onClick={() => onAction({ type: "rest" })}>
            Rest by the fire
          </button>
        )}
      </div>

      <div className="cmd-row">
        <input
          value={cmd}
          placeholder="say or do something… (e.g. examine the tablet, talk to them, buy 2)"
          onChange={(e) => setCmd(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <button className="btn btn-primary" onClick={submit} disabled={!cmd.trim()}>
          Do
        </button>
      </div>
    </div>
  );
}
