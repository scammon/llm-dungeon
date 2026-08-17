"""Headless verification for the roguelite loop (no interactive input()).

Two parts:
  1. playthrough  - an AI plays full run(s); we only require "no crash".
  2. persistence  - deterministic: learn spells, force a death, reload the
                    save, and assert grimoire + essence survived the death.

Run:  python test_drive.py [seed]
"""
import sys
import os
import config
from combat import Combat
from meta import MetaSave
from game import Game

SAVE = "/tmp/llm_dungeon_test_save.json"


def _item_score(it):
    return sum(v for v in it.get("stats", {}).values() if isinstance(v, int) and v > 0)


def _auto_equip(p):
    """Equip any pack item that strictly beats what's in its slot."""
    from player import SLOTS
    changed = True
    while changed:
        changed = False
        for slot in SLOTS:
            cur = p.equipment[slot]
            cur_score = _item_score(cur) if cur else -1
            best = None
            for it in p.inventory:
                if it["slot"] == slot and _item_score(it) > cur_score:
                    if best is None or _item_score(it) > _item_score(best):
                        best = it
            if best:
                p.equip(best["id"])
                changed = True


def _ai_turn(g, c, steps):
    """One AI combat action. Returns None."""
    p = g.player
    r = g.rng.random()
    if p.grimoire and p.mana > 12 and r < 0.45:
        c.act("cast", g.rng.choice(p.grimoire))
        return
    cons = [i for i in p.inventory if i["slot"] == "consumable"]
    if r < 0.2 and cons and (p.hp < p.max_hp * 0.5 or p.mana < p.max_mana * 0.4):
        c.act("use", cons[0]["id"])
        return
    c.act("attack")


def playthrough(g, max_steps=800):
    """Play one run. Returns ('dead'|'victory'|'stuck', steps)."""
    steps = 0
    while steps < max_steps:
        steps += 1
        room = g.floor["rooms"][g.current]
        g.show_room(room)  # marks discovered + prints scene
        mons = [m for m in room["monsters"] if m["alive"]]
        if mons:
            c = Combat(g.player, mons, g)
            g.combat = c
            while not c.over and steps < max_steps:
                steps += 1
                _ai_turn(g, c, steps)
            g.combat = None
            if c.result == "win":
                room["cleared"] = True
                for m in room["monsters"]:
                    m["alive"] = False
                g.loot_room(room)
                _auto_equip(g.player)
                if g.depth == config.MAX_FLOORS and room["id"] == g.floor["boss_room"]:
                    g.on_victory()
                    return "victory", steps
            elif c.result == "lose":
                last = [m for m in c.monsters if m["alive"]]
                g.on_death("overwhelmed in battle", last[0]["name"] if last else "the dark")
                return "dead", steps
            elif c.result == "fled":
                if g.prev_room is not None:
                    g.current = g.prev_room
                continue
        else:
            g.loot_room(room)
            _auto_equip(g.player)
        # move
        if room["id"] == g.floor["exit_room"] and g.depth < config.MAX_FLOORS:
            g.try_descend()
            continue
        conns = room["connections"]
        undiscovered = [i for i, cid in enumerate(conns) if not g.floor["rooms"][cid]["discovered"]]
        if undiscovered:
            g.try_move(f"go {undiscovered[0] + 1}")
        elif room["id"] == g.floor["exit_room"]:
            g.try_descend()
        elif conns:
            g.try_move("go 1")  # backtrack / wander toward exit
        else:
            return "stuck", steps
    return "stuck", steps


def test_playthrough(seed):
    print(f"--- playthrough (seed {seed}) ---")
    g = Game(no_llm=True, seed=seed)
    g.start_run()
    res, steps = playthrough(g)
    print(f"  result={res} steps={steps} depth={g.depth} "
          f"grimoire={len(g.meta.grimoire)} deaths={g.meta.deaths} essence={g.meta.essence}")
    assert res in ("dead", "victory", "stuck")
    return res


def test_persistence(seed):
    print("--- persistence (death -> reload) ---")
    if os.path.exists(SAVE):
        os.remove(SAVE)
    config.SAVE_PATH = SAVE

    g = Game(no_llm=True, seed=seed)
    g.start_run()
    # simulate having found tomes this run
    g.player.learn_spell("fireball")
    g.player.learn_spell("healing_light")
    g.meta.essence += 17  # banked from kills
    before_grim = list(g.meta.grimoire)
    before_ess = g.meta.essence

    # force a death
    g.player.hp = 1
    g.on_death("overwhelmed in battle", "a Troll")

    assert g.meta.deaths == 1, f"expected 1 death, got {g.meta.deaths}"
    assert g.meta.grimoire == before_grim, "grimoire lost on death"
    assert g.meta.essence == before_ess, "essence lost on death"
    assert os.path.exists(SAVE), "save file not written on death"

    # reload in a brand new process-level game
    g2 = Game(no_llm=True, seed=seed + 999)
    g2.meta = MetaSave.load(SAVE)
    assert g2.meta.grimoire == before_grim, f"reloaded grimoire mismatch: {g2.meta.grimoire}"
    assert g2.meta.essence == before_ess, "reloaded essence mismatch"
    assert g2.meta.deaths == 1

    g2.start_run()
    # the new run's player must start knowing the persistent spells
    assert set(g2.player.grimoire) == set(before_grim), "new run did not start with learned spells"
    print(f"  OK: survived death with grimoire={g2.meta.grimoire} essence={g2.meta.essence} deaths={g2.meta.deaths}")


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    config.SAVE_PATH = SAVE
    test_playthrough(seed)
    test_persistence(seed)
    print("\nALL DRIVE TESTS PASSED")


if __name__ == "__main__":
    main()
