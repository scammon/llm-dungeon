import { useEffect, useRef } from "react";
import type { FeedItem } from "../types";

// The rolling event log. New entries auto-scroll to the bottom.
export function Feed({ items }: { items: FeedItem[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [items.length]);

  return (
    <div className="feed">
      {items.length === 0 && <div className="feed-empty">The dark waits.</div>}
      {items.map((it, i) => (
        <div key={i} className={`feed-line feed-${it.kind}`}>
          {it.text}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
