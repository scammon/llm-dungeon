import { monsterIcon } from "../helpers";

// Full-color isometric enemy sprite (1987 Dungeon Master style).
// Renders a standalone SVG from /sprites/<name>.svg so its colors show
// (unlike Icon, which is a monochrome CSS mask).
export function Sprite({ name, size = 132, className = "" }: {
  name: string; size?: number; className?: string;
}) {
  const file = monsterIcon(name);
  return (
    <img
      src={`/sprites/${file}.svg`}
      alt={name}
      width={size}
      height={Math.round(size * 1.05)}
      className={`sprite ${className}`.trim()}
      draggable={false}
    />
  );
}
