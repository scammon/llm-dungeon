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
    grimoire=[], attunements={}, codex={},
    runs=0, deaths=0, best_depth=0, total_essence=0,
)

class MetaSave:
    def __init__(self, **kw):
        for k, v in DEFAULTS.items():
            setattr(self, k, json.loads(json.dumps(v)))  # deep-copy defaults
        for k, v in kw.items():
            setattr(self, k, v)

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
