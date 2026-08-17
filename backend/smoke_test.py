"""Headless engine smoke test (no LLM). Run from the repo root:

    python3 backend/smoke_test.py

Exercises the full engine state machine with the narrator disabled, so it
verifies the deterministic referee + snapshot shape without any network.
"""
import json
import random
import data
import config
from meta import MetaSave
from backend.narrator import Narrator
from backend.engine import Engine


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    narrator = Narrator(enabled=False)
    meta = MetaSave()
    eng = Engine(meta, narrator, seed=1234)

    # --- hub ---
    snap = eng.snapshot()
    check(snap["screen"] == "hub", f"expected hub, got {snap['screen']}")
    check(snap["llm"] is False, "narrator should be off")
    check("meta" in snap and "feed" in snap, "snapshot missing meta/feed")

    # spend nothing (no essence yet) -> should be a no-op message
    eng.act({"type": "hub_upgrade", "stat": "hp"})
    snap = eng.snapshot()
    check(snap["screen"] == "hub", "still hub after failed upgrade")

    # --- begin a run ---
    snap = eng.act({"type": "hub_begin"})
    check(snap["screen"] in ("explore", "combat"), f"expected explore/combat, got {snap['screen']}")
    check(snap["room"]["depth"] == 1, "depth should be 1")
    check(snap["player"]["hp"] > 0, "player should be alive")
    check(len(snap["player"]["inventory"]) >= 2, "should start with 2 potions")
    check(snap["meta"]["runs"] == 1, "runs should be 1")

    # --- explore: walk every door a few times, fight, loot ---
    rng = random.Random(99)
    steps = 0
    saw_combat = False
    saw_loot = False
    while steps < 400 and eng.screen in ("explore", "combat"):
        steps += 1
        snap = eng.snapshot()
        if snap["screen"] == "combat":
            saw_combat = True
            # simple policy: attack the first monster, else cast if we have mana
            c = snap["combat"]
            if c["monsters"]:
                eng.act({"type": "attack", "n": 1})
            else:
                eng.act({"type": "defend"})
        else:
            room = snap["room"]
            if any(k in json.dumps(snap["feed"][-3:]) for k in ("Picked up", "learn")):
                saw_loot = True
            # prefer descending when at the exit
            if room["has_stairs"]:
                eng.act({"type": "descend"})
                continue
            # otherwise take a random door
            if room["doors"]:
                d = rng.choice(room["doors"])
                eng.act({"type": "move", "n": d["n"]})
            else:
                eng.act({"type": "look"})

    check(saw_combat, "should have encountered combat in 400 steps")
    check(saw_loot, "should have looted something in 400 steps")

    # --- run must have ended (death or victory) ---
    snap = eng.snapshot()
    check(snap["screen"] in ("dead", "victory"), f"run should end, got {snap['screen']}")
    if snap["screen"] == "dead":
        check(meta.deaths >= 1, "death should be recorded")
    check(meta.best_depth >= 1, "best_depth should be set")

    # --- play several more runs; meta-progression must accumulate ---
    start_grim = len(meta.grimoire)
    start_codex = len(meta.codex)
    for _ in range(10):
        snap = eng.act({"type": "hub_dismiss"})   # return to hub (no-op if already there)
        check(snap["screen"] == "hub", "should be at hub between runs")
        snap = eng.act({"type": "hub_begin"})
        steps = 0
        while steps < 400 and eng.screen in ("explore", "combat"):
            steps += 1
            s = eng.snapshot()
            if s["screen"] == "combat":
                eng.act({"type": "attack", "n": 1} if s["combat"]["monsters"] else {"type": "defend"})
            else:
                room = s["room"]
                if room["has_stairs"]:
                    eng.act({"type": "descend"})
                elif room["doors"]:
                    eng.act({"type": "move", "n": rng.choice(room["doors"])["n"]})
                else:
                    eng.act({"type": "look"})
        check(eng.screen in ("dead", "victory"), "each run must end")
        if len(meta.grimoire) > start_grim and len(meta.codex) > start_codex:
            break

    check(meta.deaths >= 1, "should have died at least once across runs")
    check(meta.total_essence >= 0, "total_essence sanity")
    check(len(meta.grimoire) > start_grim or len(meta.codex) > start_codex,
          "meta-progression (spells/lore) should accumulate across runs")

    # --- back to hub, meta persisted ---
    snap = eng.act({"type": "hub_dismiss"})
    check(snap["screen"] == "hub", "should be back at hub")
    check(snap["meta"]["deaths"] == meta.deaths, "meta deaths mismatch")
    check(snap["meta"]["essence"] == meta.essence, "meta essence mismatch")

    # --- meta round-trips through to_dict / MetaSave(**dict) ---
    d = meta.to_dict()
    meta2 = MetaSave(**d)
    check(meta2.to_dict() == d, "meta round-trip mismatch")

    print(f"OK  steps={steps} screen={snap['screen']} "
          f"depth={meta.best_depth} deaths={meta.deaths} "
          f"essence={meta.essence} grimoire={len(meta.grimoire)} "
          f"codex={len(meta.codex)}")
    print("ALL ENGINE SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
