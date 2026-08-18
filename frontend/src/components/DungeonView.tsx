import type { ReactNode } from "react";

// Per-room-type background images (generated, wide panoramas). Filenames match
// the room.type values in gen.py. dungeon_fp.svg is the fallback layer shown
// if a room PNG is missing (e.g. before the batch has been deployed).
const ROOM_BG: Record<string, string> = {
  camp: "/sprites/rooms/camp.png",
  boss: "/sprites/rooms/boss.png",
  chamber: "/sprites/rooms/chamber.png",
  corridor: "/sprites/rooms/corridor.png",
  ruin: "/sprites/rooms/ruin.png",
  pit: "/sprites/rooms/pit.png",
  treasure: "/sprites/rooms/treasure.png",
  market: "/sprites/rooms/market.png",
  library: "/sprites/rooms/library.png",
  shrine: "/sprites/rooms/shrine.png",
  forge: "/sprites/rooms/forge.png",
};

// Persistent first-person dungeon viewport (1987 Dungeon Master style).
// The room is a fixed backdrop; children are the actors standing in it
// (monsters in combat, an NPC while exploring). Always present.
export function DungeonView({ children, className = "", roomType }: {
  children?: ReactNode; className?: string; roomType?: string;
}) {
  const bg = roomType && ROOM_BG[roomType]
    ? `url(${ROOM_BG[roomType]}), url(/sprites/dungeon_fp.svg)`
    : undefined;
  return (
    <div
      className={`dungeon-view ${className}`.trim()}
      style={bg ? { backgroundImage: bg } : undefined}
    >
      <div className="dungeon-actors">{children}</div>
    </div>
  );
}
