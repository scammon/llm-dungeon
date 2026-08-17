"""Persistent meta-progression (the roguelite layer).

What survives death:
  * grimoire     - every spell ever learned (castable in all future runs)
  * attunements  - per-spell permanent power boosts
  * essence      - persistent currency (spend in the hub)
  * up           - base stat upgrades (hp/mana/atk/def/sp_power)
  * codex        - lore entries discovered
  * stats        - runs, deaths, best_depth

What does NOT survive: equipment, gold, consumables, current hp/mana.
"""
import json
import os
import data
import config

DEFAULTS = dict(
    essence=0, essence_run=0,
    up={"hp": 0, "mana": 0, "atk": 0, "defense": 0, "sp_power": 0},
    grimoire=[], grimoire_capacity=config.START_GRIMOIRE_SLOTS,
    spare_tomes=[],
    attunements={}, codex={},
    runs=0, deaths=0, best_depth=0, total_essence=0,
)

class MetaSave:
    def __init__(self, **kw):
        for k, v in DEFAULTS.items():
            setattr(self, k, json.loads(json.dumps(v)))  # deep-copy defaults
        for k, v in kw.items():
            setattr(self, k, v)
        # existing saves may predate the slot cap; never strand learned spells
        if self.grimoire_capacity < len(self.grimoire):
            self.grimoire_capacity = len(self.grimoire)

    # ---- persistence ----------------------------------------------------
    def to_dict(self):
        return {k: getattr(self, k) for k in DEFAULTS}

    @classmethod
    def load(cls, path=None):
        path = path or config.SAVE_PATH
        if os.path.exists(path):
            try:
                with open(path) as f:
                    raw = json.load(f)
                obj = cls()
                for k in DEFAULTS:
                    if k in raw:
                        setattr(obj, k, raw[k])
                obj.grimoire_capacity = max(obj.grimoire_capacity, len(obj.grimoire))
                return obj
            except Exception:
                pass
        return cls()

    def save(self, path=None):
        path = path or config.SAVE_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    # ---- hub upgrades ---------------------------------------------------
    def stat_level(self, kind):
        return self.up.get(kind, 0)

    def upgrade_cost(self, kind):
        base = config.UPGRADE_BASE_COST[kind]
        lvl = self.up.get(kind, 0) if kind in self.up else self.attunements_total(kind)
        return round(base * (1 + 0.5 * lvl))

    def attunements_total(self, spell_id):
        return self.attunements.get(spell_id, 0)

    def attune_cost(self, spell_id):
        lvl = self.attunements.get(spell_id, 0)
        return round(config.UPGRADE_BASE_COST["attune"] * (1 + 0.6 * lvl))

    def buy_stat(self, kind):
        if kind not in config.UPGRADE_BASE_COST or kind == "attune":
            return False, "Not a stat upgrade."
        cost = self.upgrade_cost(kind)
        if self.essence < cost:
            return False, f"Need {cost} essence (have {self.essence})."
        self.essence -= cost
        self.up[kind] = self.up.get(kind, 0) + 1
        return True, f"Upgraded {kind.replace('_',' ')} (+1). New cost {self.upgrade_cost(kind)}."

    def buy_attune(self, spell_id):
        if spell_id not in self.grimoire:
            return False, "You haven't learned that spell yet."
        if self.attunements.get(spell_id, 0) >= config.ATTUNE_MAX:
            return False, "Already fully attuned."
        cost = self.attune_cost(spell_id)
        if self.essence < cost:
            return False, f"Need {cost} essence (have {self.essence})."
        self.essence -= cost
        self.attunements[spell_id] = self.attunements.get(spell_id, 0) + 1
        return True, f"Attuned {data.SPELLS[spell_id]['name']} to level {self.attunements[spell_id]}."

    def grimoire_cost(self):
        """Essence to bind one more spell slot; None when the grimoire is full."""
        if self.grimoire_capacity >= config.GRIMOIRE_MAX:
            return None
        lvl = self.grimoire_capacity - config.START_GRIMOIRE_SLOTS
        return round(config.GRIMOIRE_BASE_COST * (1 + 0.8 * lvl))

    def buy_grimoire(self):
        if self.grimoire_capacity >= config.GRIMOIRE_MAX:
            return False, "Your grimoire is already bound to its fullest."
        cost = self.grimoire_cost()
        if self.essence < cost:
            return False, f"Need {cost} essence (have {self.essence})."
        self.essence -= cost
        self.grimoire_capacity += 1
        nxt = self.grimoire_cost()
        tail = f" Next slot {nxt}." if nxt else " No further slots remain."
        return True, f"Your grimoire binds a new page: {self.grimoire_capacity} spell slots.{tail}"

    def bind_spare_tome(self, tome_sid, replace_sid=None):
        """Bind a spare tome into the grimoire.

        With a free slot the spell is simply added. When the grimoire is full,
        `replace_sid` (a known spell to forget) is required — the tome takes its
        place. Returns (ok, msg); msg=="full" when a replacement is needed but
        none was given."""
        if tome_sid not in self.spare_tomes:
            return False, "You don't have a spare tome of that spell."
        if tome_sid in self.grimoire:
            return False, f"You already know {data.SPELLS[tome_sid]['name']}."
        if len(self.grimoire) < self.grimoire_capacity:
            self.grimoire.append(tome_sid)
            self.spare_tomes.remove(tome_sid)
            return True, f"You bind {data.SPELLS[tome_sid]['name']} to a free page of your grimoire."
        if not replace_sid:
            return False, "full"
        if replace_sid not in self.grimoire:
            return False, "You don't know that spell to forget."
        if replace_sid == tome_sid:
            return False, "You can't forget and rebind the same spell."
        self.grimoire.remove(replace_sid)
        self.grimoire.append(tome_sid)
        self.spare_tomes.remove(tome_sid)
        return True, (f"You forget {data.SPELLS[replace_sid]['name']} and bind "
                      f"{data.SPELLS[tome_sid]['name']} in its place.")
