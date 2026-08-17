import type { CSSProperties } from "react";

// Monochrome SVGs (white on transparent) recolored via CSS mask, so any
// icon can take `currentColor`.
export function Icon({
  name,
  size = 24,
  className = "",
  style,
}: {
  name: string;
  size?: number;
  className?: string;
  style?: CSSProperties;
}) {
  const mask = `url(/icons/${name}.svg)`;
  return (
    <span
      aria-hidden
      className={`icon ${className}`}
      style={{
        display: "inline-block",
        width: size,
        height: size,
        backgroundColor: "currentColor",
        WebkitMaskImage: mask,
        maskImage: mask,
        WebkitMaskSize: "contain",
        maskSize: "contain",
        WebkitMaskRepeat: "no-repeat",
        maskRepeat: "no-repeat",
        WebkitMaskPosition: "center",
        maskPosition: "center",
        flex: "0 0 auto",
        ...style,
      }}
    />
  );
}
