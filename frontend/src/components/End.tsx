import type { Action, Snapshot } from "../types";
import { Icon } from "./Icon";

export function End({ snap, onAction }: { snap: Snapshot; onAction: (a: Action) => void }) {
  const victory = snap.ended === "victory";
  return (
    <div className={`end ${victory ? "victory" : "dead"}`}>
      <Icon name={victory ? "ui_trophy" : "ui_skull"} size={72} />
      <h2>{victory ? "You Conquer the Deep" : "You Have Fallen"}</h2>
      <p className="muted">
        {victory
          ? "The Hollow King is no more. The Deep falls silent."
          : "Your gear is lost to the dark. Your knowledge endures."}
      </p>
      <button className="btn btn-primary btn-big" onClick={() => onAction({ type: "return" })}>
        Return to Camp
      </button>
    </div>
  );
}
