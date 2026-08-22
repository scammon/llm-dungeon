"""Player state for a single run + persistent-grimoire helpers.

Roguelite contract:
  * `meta` (a MetaSave) holds the *persistent* stuff: grimoire (spells ever
    learned), attunements, essence, base-stat upgrades, codex.
  * `Player` holds the *run-scoped* stuff: current hp/mana, gold, equipment,
    inventory, and the consumable effects. On death, the Player is discarded;
    the MetaSave (already updated as spells are learned) survives.
"""
import data
import config

SLOTS = ["weapon", "armor", "helm", "boots", "trinket"]

class Player:
    def __init__(self, meta, rng):
        self.meta = meta
        self.rng = rng
        # base stats = platform starts + persistent upgrades
        self.base_max_hp = config.STARTING_HP + meta.up["hp"] * config.HP_STEP
        self.base_max_mana = config.STARTING_MANA + meta.up["mana"] * config.MANA_STEP
        self.base_atk = config.STARTING_ATK + meta.up["atk"] * config.ATK_STEP
        self.base_def = config.STARTING_DEF + meta.up["defense"] * config.DEF_STEP
        self.base_sp = config.STARTING_SPELL_POWER + meta.up["sp_power"] * config.SP_POWER_STEP

        self.gold = 0
        self.equipment = {s: None for s in SLOTS}
        self.inventory = []
        self.grimoire = list(meta.grimoire)          # spells castable this run
        self.run_attunements = {}                     # run-only attunement boosts (tomes of known spells)
        self.status = []                              # active effects this run

        # refresh derived pools
        self._refresh()
        self.hp = self.max_hp
        self.mana = self.max_mana

    # ---- derived stats --------------------------------------------------
    def _equip_sum(self, key):
        total = 0
        for it in self.equipment.values():
            if it:
                total += it["stats"].get(key, 0)
        return total

    def _buff_sum(self, kind):
        return sum(s["power"] for s in self.status if s["kind"] == kind)

    def _refresh(self):
        self.max_hp = self.base_max_hp + self._equip_sum("hp")
        self.max_mana = self.base_max_mana + self._equip_sum("mana")

    def total_atk(self):
        return self.base_atk + self._equip_sum("atk") + self._buff_sum("buff_atk")

    def total_def(self):
        return self.base_def + self._equip_sum("defense") + self._buff_sum("buff_def")

    def total_sp(self):
        return self.base_sp + self._equip_sum("sp") + self._buff_sum("buff_sp")

    def shield_absorb(self):
        return sum(s["power"] for s in self.status if s["kind"] == "shield")

    # ---- equipment / inventory -----------------------------------------
    def take(self, item):
        self.inventory.append(item)

    def equip(self, item_id):
        item = self._find(self.inventory, item_id)
        if not item or item["slot"] not in SLOTS:
            return False, "That can't be equipped."
        cur = self.equipment[item["slot"]]
        self.inventory.remove(item)
        if cur:
            self.inventory.append(cur)
        self.equipment[item["slot"]] = item
        self._refresh()
        self.hp = min(self.hp, self.max_hp)
        self.mana = min(self.mana, self.max_mana)
        return True, f"You equip the {item['name']}."

    def unequip(self, slot):
        item = self.equipment.get(slot)
        if not item:
            return False, f"You have nothing in {slot}."
        self.equipment[slot] = None
        self.inventory.append(item)
        self._refresh()
        self.hp = min(self.hp, self.max_hp)
        self.mana = min(self.mana, self.max_mana)
        return True, f"You unequip the {item['name']}."

    def drop(self, item_id):
        item = self._find(self.inventory, item_id)
        if not item:
            return False, "Not in your pack."
        self.inventory.remove(item)
        return True, f"You drop the {item['name']}."

    def _find(self, lst, iid):
        for it in lst:
            if it["id"] == iid:
                return it
        return None

    # ---- consumables ----------------------------------------------------
    def use_item(self, item_id):
        item = self._find(self.inventory, item_id)
        if not item:
            return False, "You don't have that."
        if item["slot"] != "consumable":
            return False, f"The {item['name']} is not a consumable."
        self.inventory.remove(item)
        eff = item["effect"]
        if eff == "heal_hp":
            self.hp = min(self.max_hp, self.hp + item["power"])
            return True, f"You drink the {item['name']}; +{item['power']} hp."
        if eff == "heal_mana":
            self.mana = min(self.max_mana, self.mana + item["power"])
            return True, f"You drink the {item['name']}; +{item['power']} mana."
        if eff == "buff_atk":
            self.status.append(dict(kind="buff_atk", power=item["power"], turns=item.get("turns", 3)))
            return True, f"You feel surging power; +{item['power']} atk for {item.get('turns',3)} turns."
        if eff == "cleanse":
            self.status = [s for s in self.status if s["kind"] not in ("poison", "chill")]
            return True, "The bitter potion purges you of ailment."
        return True, f"You use the {item['name']}."

    # ---- spells ---------------------------------------------------------
    def knows(self, spell_id):
        return spell_id in self.grimoire

    def learn_spell(self, spell_id):
        """Learn a spell *permanently* (persisted to meta.grimoire).

        Returns (ok, msg). Fails with msg=="full" when the grimoire has no
        free spell slots (expand it at the camp to learn more)."""
        if spell_id in self.meta.grimoire:
            return False, f"You already know {data.SPELLS[spell_id]['name']}."
        if len(self.meta.grimoire) >= self.meta.grimoire_capacity:
            return False, "full"
        self.meta.grimoire.append(spell_id)
        self.grimoire.append(spell_id)
        return True, "learned"

    def attunement(self, spell_id):
        # persistent (essence-bought) + run-only (tomes of spells already known)
        return self.meta.attunements.get(spell_id, 0) + self.run_attunements.get(spell_id, 0)

    def attune_run(self, spell_id):
        """Deepen a known spell's attunement for this run only (discarded on death)."""
        self.run_attunements[spell_id] = self.run_attunements.get(spell_id, 0) + 1
        return self.attunement(spell_id)

    def spell_cost(self, spell_id):
        sp = data.SPELLS[spell_id]
        return max(1, sp["cost"] - self.attunement(spell_id))

    def spell_power(self, spell_id):
        sp = data.SPELLS[spell_id]
        return sp.get("power", 0) + self.attunement(spell_id) * 2

    # ---- turn upkeep ----------------------------------------------------
    def tick_status(self):
        """Advance durations; return list of messages (poison ticks, etc.)."""
        msgs = []
        for s in list(self.status):
            if s["kind"] == "poison":
                self.hp -= s["power"]
                msgs.append(f"You take {s['power']} poison damage.")
            s["turns"] -= 1
            if s["turns"] <= 0:
                self.status.remove(s)
        if self.hp > self.max_hp:
            self.hp = self.max_hp
        return msgs

    def regen(self):
        self.mana = min(self.max_mana, self.mana + config.MANA_REGEN_PER_TURN)

    # ---- run persistence --------------------------------------------------
    def to_state(self):
        return {
            "gold": self.gold,
            "equipment": self.equipment,
            "inventory": list(self.inventory),
            "grimoire": list(self.grimoire),
            "run_attunements": dict(self.run_attunements),
            "status": [dict(s) for s in self.status],
            "hp": self.hp,
            "mana": self.mana,
        }

    @classmethod
    def restore(cls, meta, rng, state):
        p = cls(meta, rng)
        p.gold = state["gold"]
        p.equipment = state["equipment"]
        p.inventory = state["inventory"]
        p.grimoire = state["grimoire"]
        p.run_attunements = state["run_attunements"]
        p.status = state["status"]
        p.hp = state["hp"]
        p.mana = state["mana"]
        p._refresh()
        p.hp = min(p.hp, p.max_hp)
        p.mana = min(p.mana, p.max_mana)
        return p
