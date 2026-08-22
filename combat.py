"""Turn-based combat engine.

The player acts once per round; then every surviving monster acts (fastest
first). Spells, items, defending, and fleeing are player actions. The LLM is
consulted only for flavor (monster intros, boss taunts) — all numbers here are
deterministic so the game is fair and fast.
"""
import random
import data
import config

class Combat:
    def __init__(self, player, monsters, game):
        self.player = player
        self.game = game
        self.monsters = [m for m in monsters if m["alive"]]
        for m in self.monsters:
            m.setdefault("status", [])
        self.turn = 0
        self.over = False
        self.result = None          # 'win' | 'lose' | 'fled'
        self.defending = False
        self.log = []

    # ---- run persistence --------------------------------------------------
    def to_state(self):
        return {
            "monsters": self.monsters,
            "turn": self.turn,
            "over": self.over,
            "result": self.result,
            "defending": self.defending,
            "log": list(self.log),
        }

    @classmethod
    def restore(cls, player, game, state):
        c = object.__new__(cls)
        c.player = player
        c.game = game
        c.monsters = state["monsters"]
        c.turn = state["turn"]
        c.over = state["over"]
        c.result = state["result"]
        c.defending = state["defending"]
        c.log = state["log"]
        return c

    # ---- helpers --------------------------------------------------------
    def alive(self):
        return [m for m in self.monsters if m["alive"]]

    def target(self, idx=None):
        a = self.alive()
        if not a:
            return None
        if idx is None or idx < 1 or idx > len(a):
            return a[0]
        return a[idx - 1]

    def _add(self, msg):
        self.log.append(msg)

    def _end(self, result):
        self.over = True
        self.result = result

    # ---- player actions -------------------------------------------------
    def act(self, action, arg=None):
        if self.over:
            return
        self.turn += 1
        self.defending = False
        if action == "attack":
            self.do_attack(self.target(arg))
        elif action == "cast":
            if isinstance(arg, tuple):
                self.do_cast(arg[0], arg[1])
            else:
                self.do_cast(arg)
        elif action == "defend":
            self.defending = True
            self._add("You brace behind your guard, ready to cut damage in half.")
            self.player.mana = min(self.player.max_mana, self.player.mana + 2)
        elif action == "flee":
            self.do_flee()
        elif action == "use":
            ok, msg = self.player.use_item(arg)
            self._add(msg)
        else:
            self._add("You hesitate.")
        if self.over:
            return
        if not self.alive():
            self._end("win")
            return
        self._monster_phase()
        if self.over:
            return
        if not self.alive():
            self._end("win")
            return
        # player status ticks at end of round
        for m in self.player.tick_status():
            self._add(m)
        self.player.regen()
        if self.player.hp <= 0 and not self.over:
            self._end("lose")

    def do_attack(self, mon):
        if not mon:
            self._add("There is nothing left to strike.")
            return
        atk = self.player.total_atk()
        dmg, crit = _roll(atk, mon["defense"], self.game.rng)
        mon["hp"] -= dmg
        line = f"You strike the {mon['name']} for {dmg}."
        if crit:
            line += " Critical!"
        self._add(line)
        if mon["hp"] <= 0:
            mon["alive"] = False
            mon["hp"] = 0
            self._on_kill(mon)

    def do_cast(self, spell_id, target_idx=None):
        p = self.player
        if not p.knows(spell_id):
            self._add("You don't know that spell.")
            return
        sp = data.SPELLS[spell_id]
        cost = p.spell_cost(spell_id)
        if p.mana < cost:
            self._add(f"Not enough mana for {sp['name']} (needs {cost}).")
            return
        p.mana -= cost
        power = p.spell_power(spell_id)
        kind = sp["kind"]
        tgt = self.target() if not sp.get("aoe") else None

        if kind == "damage":
            targets = self.alive() if sp.get("aoe") else [self.target(target_idx)]
            for mon in targets:
                if not mon or not mon["alive"]:
                    continue
                raw = power + p.total_sp()
                dmg, crit = _roll(raw, mon["defense"] // 2, self.game.rng)
                mon["hp"] -= dmg
                self._add(f"{sp['name']} hits the {mon['name']} for {dmg}." + (" Critical!" if crit else ""))
                if sp.get("lifesteal"):
                    heal = dmg // 2
                    p.hp = min(p.max_hp, p.hp + heal)
                    self._add(f"You drain {heal} vitality.")
                if mon["hp"] <= 0:
                    mon["alive"] = False
                    mon["hp"] = 0
                    self._on_kill(mon)
        elif kind == "heal":
            heal = power + p.total_sp()
            p.hp = min(p.max_hp, p.hp + heal)
            self._add(f"{sp['name']} restores {heal} hp.")
        elif kind == "buff":
            if sp["name"] == "Stone Skin":
                p.status.append(dict(kind="buff_def", power=power, turns=sp["turns"]))
                self._add(f"{sp['name']}: your skin hardens (+{power} def).")
            else:  # Berserk and any generic buff -> attack
                p.status.append(dict(kind="buff_atk", power=power, turns=sp["turns"]))
                self._add(f"{sp['name']}: your attack surges (+{power} atk).")
        elif kind == "debuff":
            targets = self.alive() if sp.get("aoe") else [self.target(target_idx)]
            for mon in targets:
                if not mon or not mon["alive"]:
                    continue
                mon["status"].append(dict(kind="poison" if sp["name"] == "Nature's Wrath" else "chill",
                                          power=power, turns=sp["turns"]))
                self._add(f"{sp['name']} seizes the {mon['name']}.")
        elif kind == "control":
            mon = self.target(target_idx)
            if mon and mon["alive"]:
                mon["status"].append(dict(kind="stunned", power=0, turns=sp["turns"]))
                self._add(f"{sp['name']} stuns the {mon['name']}!")
        elif kind == "shield":
            p.status.append(dict(kind="shield", power=power + p.total_sp(), turns=sp["turns"]))
            self._add(f"{sp['name']}: a ward soaks up to {power + p.total_sp()} damage.")

    def do_flee(self):
        # harder to flee from bosses
        chance = 0.4 if any(m["is_boss"] for m in self.monsters) else 0.7
        if self.game.rng.random() < chance:
            self._add("You slip away into the dark.")
            self._end("fled")
        else:
            self._add("You fail to escape!")

    def _on_kill(self, mon):
        self._add(f"The {mon['name']} is destroyed.")
        self.player.gold += mon["gold"]
        self.game.meta.essence += mon["essence"]
        self.game.meta.essence_run += mon["essence"]
        self._add(f"  +{mon['gold']} gold, +{mon['essence']} essence.")
        # chance to drop a tome or item
        r = self.game.rng.random()
        if r < 0.18:
            tome = _drop_tome(mon, self.game)
            if tome:
                self.player.take(tome)
                self._add(f"  It drops: {tome['name']}.")
        elif r < 0.45:
            it = _drop_item(mon, self.game)
            if it:
                self.player.take(it)
                self._add(f"  It drops: {it['name']} ({it['rarity']}).")

    # ---- monster phase --------------------------------------------------
    def _monster_phase(self):
        mons = sorted(self.alive(), key=lambda m: -m["speed"])
        for mon in mons:
            if self.over:
                break
            if not mon["alive"]:
                continue
            # poison tick
            for s in list(mon["status"]):
                if s["kind"] == "poison":
                    mon["hp"] -= s["power"]
                    self._add(f"The {mon['name']} takes {s['power']} poison damage.")
                    if mon["hp"] <= 0:
                        mon["alive"] = False
                        mon["hp"] = 0
                        self._on_kill(mon)
                        break
            if not mon["alive"]:
                continue
            # stunned?
            stunned = [s for s in mon["status"] if s["kind"] == "stunned"]
            if stunned:
                self._add(f"The {mon['name']} is stunned and cannot act.")
            else:
                self._monster_attack(mon)
            # decrement durations
            for s in list(mon["status"]):
                s["turns"] -= 1
                if s["turns"] <= 0:
                    mon["status"].remove(s)

    def _monster_attack(self, mon):
        p = self.player
        ability = mon["ability"]
        use_special = ability and self.game.rng.random() < 0.4
        mult = 1.0
        note = ""
        if use_special:
            if ability == "heavy":
                mult, note = 1.5, " with a crushing blow"
            elif ability == "charge":
                mult, note = 1.8, " with a devastating charge"
            elif ability == "swift":
                mult, note = 1.0, ""
            elif ability in ("hex", "chill", "void", "life_drain"):
                mult, note = 1.3, f" ({ability})"
            elif ability == "bone_shards":
                mult, note = 1.2, " with scattering bone shards"
            elif ability == "regrow":
                heal = mon["max_hp"] // 6
                mon["hp"] = min(mon["max_hp"], mon["hp"] + heal)
                self._add(f"The {mon['name']} knits itself back together (+{heal} hp).")
                return
        raw = round(mon["atk"] * mult)
        defense = p.total_def()
        if use_special and ability == "bone_shards":
            defense //= 2
        dmg, crit = _roll(raw, defense, self.game.rng)
        # chill reduces monster damage
        for s in mon["status"]:
            if s["kind"] == "chill":
                dmg = max(1, dmg - 3)
        absorbed = _apply_to_player(p, dmg)
        line = f"The {mon['name']} hits you{note} for {dmg}."
        if crit:
            line += " Critical!"
        if absorbed:
            line += f" ({absorbed} absorbed)"
        self._add(line)
        # ability side effects
        if use_special:
            if ability == "hex":
                p.mana = max(0, p.mana - 8)
                p.status.append(dict(kind="buff_def", power=-3, turns=2))  # negative buff = def down
                self._add("A hex saps your mana and focus.")
            elif ability == "chill":
                p.status.append(dict(kind="chill", power=3, turns=2))
                self._add("A creeping cold stiffens you.")
            elif ability == "life_drain":
                heal = dmg // 2
                mon["hp"] = min(mon["max_hp"], mon["hp"] + heal)
                self._add(f"The {mon['name']} drains {heal} of your vitality.")
            elif ability == "charge":
                mon["status"].append(dict(kind="stunned", power=0, turns=1))
                self._add(f"The {mon['name']}'s charge carries it past, leaving it off-balance.")

def _roll(atk, defense, rng, ignore_def=False):
    base = atk if ignore_def else atk - defense
    base = max(1, base + rng.randint(-2, 3))
    crit = rng.random() < config.CRIT_CHANCE
    if crit:
        base = int(base * config.CRIT_MULT)
    return base, crit

def _apply_to_player(p, dmg):
    # shield absorb, then apply the remainder to hp
    shields = [s for s in p.status if s["kind"] == "shield" and s["power"] > 0]
    absorbed = 0
    for s in shields:
        if absorbed >= dmg:
            break
        take = min(s["power"], dmg - absorbed)
        s["power"] -= take
        absorbed += take
    dmg -= absorbed
    p.hp -= dmg
    return absorbed

def _drop_tome(mon, game):
    # bosses drop strong tomes; normal monsters sometimes drop a tome
    if mon["is_boss"]:
        sid = _boss_spell(mon)
        if sid:
            return _tome(sid, game)
    return None

def _boss_spell(mon):
    for sid, src in data.SPELL_SOURCES.items():
        if src["boss"] == mon["template_id"]:
            return sid
    return None

def _tome(sid, game):
    import gen
    return gen.make_tome(game.rng, sid, max(1, game.depth))

def _drop_item(mon, game):
    import gen
    return gen.roll_item(game.rng, max(1, game.depth))
