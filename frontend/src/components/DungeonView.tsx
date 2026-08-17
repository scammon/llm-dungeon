import type { ReactNode } from "react";

// Persistent first-person dungeon viewport (1987 Dungeon Master style).
// The room is a fixed backdrop; children are the actors standing in it
// (monsters in combat, an NPC while exploring). Always present.
export function DungeonView({ children, className = "" }: {
  children?: ReactNode; className?: string;
}) {
  return (
    <div className={`dungeon-view ${className}`.trim()}>
      <div className="dungeon-actors">{children}</div>
    </div>
  );
}
