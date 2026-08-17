import { useMemo } from "react";
import type { FloorMap, MapRoom } from "../types";

const SPACING_X = 96;
const SPACING_Y = 62;
const R = 13;

// BFS from the start room: each room's x is its distance from the start,
// rooms at the same distance stack vertically (centered). Gives a clean
// left-to-right flow from the entrance toward the exit.
function layout(rooms: MapRoom[], start: string) {
  const ids = new Set(rooms.map((r) => r.id));
  const root = ids.has(start) ? start : rooms[0]?.id;
  const adj = new Map<string, string[]>();
  rooms.forEach((r) => adj.set(r.id, []));
  rooms.forEach((r) =>
    r.connections.forEach((c) => {
      if (ids.has(c)) {
        adj.get(r.id)!.push(c);
        adj.get(c)!.push(r.id);
      }
    })
  );
  const level = new Map<string, number>();
  if (root) {
    const q = [root];
    level.set(root, 0);
    while (q.length) {
      const cur = q.shift()!;
      for (const nb of adj.get(cur) ?? []) {
        if (!level.has(nb)) {
          level.set(nb, level.get(cur)! + 1);
          q.push(nb);
        }
      }
    }
  }
  rooms.forEach((r) => {
    if (!level.has(r.id)) level.set(r.id, 0);
  });
  const groups = new Map<number, string[]>();
  rooms.forEach((r) => {
    const l = level.get(r.id)!;
    if (!groups.has(l)) groups.set(l, []);
    groups.get(l)!.push(r.id);
  });
  let maxCount = 1;
  groups.forEach((g) => (maxCount = Math.max(maxCount, g.length)));
  const pos = new Map<string, { x: number; y: number }>();
  groups.forEach((g, l) => {
    const offset = ((maxCount - g.length) / 2) * SPACING_Y;
    g.forEach((id, i) => {
      pos.set(id, { x: l * SPACING_X, y: offset + i * SPACING_Y });
    });
  });
  return pos;
}

const TYPE_COLOR: Record<string, string> = {
  camp: "var(--shield)",
  boss: "var(--monster)",
  treasure: "var(--gold)",
  shrine: "var(--sp)",
  library: "var(--mana)",
  pit: "var(--essence)",
  market: "var(--market)",
  forge: "var(--forge)",
};

export function DungeonMap({ map }: { map: FloorMap }) {
  const pos = useMemo(() => layout(map.rooms, map.start), [map]);
  const byId = useMemo(() => new Map(map.rooms.map((r) => [r.id, r])), [map]);

  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  pos.forEach((p) => {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  });
  if (!isFinite(minX)) {
    minX = minY = 0;
    maxX = maxY = 0;
  }
  const PAD = R + 10;
  const w = maxX - minX + PAD * 2;
  const h = maxY - minY + PAD * 2;

  const edges: { x1: number; y1: number; x2: number; y2: number; key: string }[] = [];
  const seen = new Set<string>();
  map.rooms.forEach((r) => {
    r.connections.forEach((c) => {
      if (!byId.has(c)) return;
      const key = [r.id, c].sort().join("|");
      if (seen.has(key)) return;
      seen.add(key);
      const a = pos.get(r.id)!;
      const b = pos.get(c)!;
      edges.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, key });
    });
  });

  return (
    <div className="floor-map">
      <div className="floor-map-head">
        <span className="floor-map-title">Floor map</span>
        <span className="muted small">depth {map.depth}</span>
      </div>
      <div className="floor-map-scroll">
        <svg
          className="floor-map-svg"
          viewBox={`${minX - PAD} ${minY - PAD} ${w} ${h}`}
          width={w}
          height={h}
        >
          {edges.map((e) => (
            <line key={e.key} x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2} className="map-edge" />
          ))}
          {map.rooms.map((r) => {
            const p = pos.get(r.id)!;
            const color = TYPE_COLOR[r.type] ?? "var(--muted)";
            return (
              <g key={r.id} transform={`translate(${p.x},${p.y})`}>
                {r.is_current && <circle r={R + 6} className="map-current-ring" />}
                {r.is_exit && <circle r={R + 4} className="map-exit-ring" />}
                <circle
                  r={r.is_boss ? R + 2 : R}
                  className="map-node"
                  fill={color}
                  opacity={r.cleared ? 0.4 : 1}
                />
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
