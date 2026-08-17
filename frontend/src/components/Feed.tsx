import { useEffect, useRef, useState } from "react";
import type { FeedItem } from "../types";

const RECENT = 10;

// The rolling event log. Shows only the most recent lines by default; a
// toggle expands the full history. New entries auto-scroll to the bottom.
export function Feed({ items }: { items: FeedItem[] }) {
  const [expanded, setExpanded] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const visible = expanded ? items : items.slice(-RECENT);
  const hidden = items.length - visible.length;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [items.length, expanded]);

  return (
    <div className="feed">
      <div className="feed-head">
        <span className="feed-head-label">Log</span>
        {items.length > RECENT && (
          <button className="feed-toggle" onClick={() => setExpanded((v) => !v)}>
            {expanded
              ? `▴ Collapse (showing all ${items.length})`
              : `▾ Full log (${hidden} earlier)`}
          </button>
        )}
      </div>
      {items.length === 0 && <div className="feed-empty">The dark waits.</div>}
      {visible.map((it, i) => (
        <div key={i} className={`feed-line feed-${it.kind}`}>
          {it.text}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
