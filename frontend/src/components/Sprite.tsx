import { monsterIcon } from "../helpers";

// Full-color enemy sprite (1987 Dungeon Master style).
// Renders a generated PNG from /sprites/<name>.png so its colors show
// (unlike Icon, which is a monochrome CSS mask).
export function Sprite({ name, size = 132, className = "" }: {
  name: string; size?: number; className?: string;
}) {
  const file = monsterIcon(name);
  return (
    <img
      src={`/sprites/${file}.png`}
      alt={name}
      width={size}
      height={Math.round(size * 1.05)}
      className={`sprite ${className}`.trim()}
      draggable={false}
    />
  );
}
