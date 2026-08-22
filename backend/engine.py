"""I/O-free game engine for the web port.

Ports the CLI `Game` loop (game.py) into a state machine that:
  * holds all run state (meta, floors, player, combat),
  * exposes snapshot()  -> a JSON-serializable state the UI renders,
  * exposes act(action) -> applies one player action, returns the new snapshot.

There is no input()/print(). All narration goes through the Narrator (Dailey
AI) and degrades to pre-written fallbacks when the LLM is unavailable, so the
game is always playable. The deterministic referee (combat, player, gen, data)
is reused unchanged from the root modules.
"""
import random
from collections import deque
import data
import config
import gen
from player import Player, SLOTS
from combat import Combat

TYPE_LABEL = {
    "corridor": "a narrow corridor",
    "chamber": "a stone chamber",
    "treasure": "a treasure vault",
    "shrine": "a mossy shrine",
    "boss": "a vast antechamber",
    "camp": "a dry camp hollow",
    "ruin": "a collapsed ruin",
    "library": "a flooded archive",
    "pit": "a railed edge over a pit",
    "market": "a candlelit market",
    "forge": "a smith's forge",
}


def _norm_spell(s):
    """Lowercase alphanumeric-only form, so 'Power Word: Stun' matches 'power word stun'."""
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def stat_str(stats):
    parts = []
    if stats.get("atk"):
        parts.append(f"+{stats['atk']} atk")
    if stats.get("defense"):
        parts.append(f"+{stats['defense']} def")
    if stats.get("hp"):
        parts.append(f"+{stats['hp']} hp")
    if stats.get("mana"):
        parts.append(f"+{stats['mana']} mana")
    if stats.get("sp"):
        parts.append(f"+{stats['sp']} sp")
    return ", ".join(parts) if parts else ""


class Engine:
    def __init__(self, meta, narrator, seed=None):
        self.meta = meta
        self.narrator = narrator
        self.rng = random.Random(seed)
        self.feed = deque(maxlen=300)   # rolling event log for the UI
        self.ended = None               # None | "dead" | "victory"
        # run state (None while at the hub)
        self.floors = None
        self.depth = None
        self.floor = None
        self.current = None
        self.prev_room = None
        self.player = None
        self.combat = None

    # ===================================================================
    # STATE / DISPATCH
    # ===================================================================
    @property
    def in_run(self):
        return self.floors is not None

    @property
    def screen(self):
        if self.ended:
            return self.ended
        if not self.in_run:
            return "hub"
        return "combat" if self.combat else "explore"

    def _feed(self, kind, text):
        if text:
            self.feed.append({"kind": kind, "text": text})

    def act(self, action):
        """Apply one player action. Returns the new snapshot."""
        t = (action or {}).get("type")
        if self.ended:
            # run is over; any action returns to the camp
            self._clear_run()
            return self.snapshot()
        if not self.in_run:
            self._hub_act(t, action or {})
        elif self.combat:
            self._combat_act(t, action or {})
        else:
            self._explore_act(t, action or {})
        return self.snapshot()

    # ===================================================================
    # SNAPSHOT (what the UI renders)
    # ===================================================================
    def snapshot(self):
        snap = {
            "screen": self.screen,
            "meta": self._meta_snapshot(),
            "feed": list(self.feed),
            "ended": self.ended,
            "llm": self.narrator.ready() if self.narrator else False,
        }
        if self.in_run:
            snap["room"] = self._room_snapshot()
            snap["player"] = self._player_snapshot()
            snap["combat"] = self._combat_snapshot()
            if self.screen == "explore":
                snap["map"] = self._floor_map()
        return snap

    def _meta_snapshot(self):
        m = self.meta
        upgrades = []
        for k in ("hp", "mana", "atk", "defense", "sp_power"):
            upgrades.append({"stat": k, "level": m.up.get(k, 0), "cost": m.upgrade_cost(k)})
        grimoire = []
        for sid in m.grimoire:
            sp = data.SPELLS[sid]
            att = m.attunements.get(sid, 0)
            grimoire.append({
                "id": sid, "name": sp["name"], "element": sp["element"], "tier": sp["tier"],
                "attuned": att, "cost": max(1, sp["cost"] - att), "power": sp.get("power", 0) + att * 2,
                "desc": sp["desc"], "attune_cost": m.attune_cost(sid),
                "attune_max": att >= config.ATTUNE_MAX,
            })
        spare_tomes = []
        for sid in m.spare_tomes:
            sp = data.SPELLS[sid]
            spare_tomes.append({
                "id": sid, "name": sp["name"], "element": sp["element"], "tier": sp["tier"],
                "desc": sp["desc"],
            })
        codex = []
        for key, text in m.codex.items():
            title, _ = data.LORE[key]
            codex.append({"key": key, "title": title, "text": text})
        return {
            "essence": m.essence, "runs": m.runs, "deaths": m.deaths,
            "best_depth": m.best_depth, "total_essence": m.total_essence,
            "upgrades": upgrades, "grimoire": grimoire, "spare_tomes": spare_tomes,
            "codex": codex,
            "grimoire_capacity": m.grimoire_capacity,
            "grimoire_cost": m.grimoire_cost(),
            "grimoire_max": m.grimoire_capacity >= config.GRIMOIRE_MAX,
        }

    def _room_snapshot(self):
        room = self.floor["rooms"][self.current]
        room["discovered"] = True
        mons = [m for m in room["monsters"] if m["alive"]]
        doors = []
        for i, cid in enumerate(room["connections"], 1):
            t = self.floor["rooms"][cid]["type"]
            doors.append({"n": i, "type": t, "label": TYPE_LABEL[t],
                          "discovered": self.floor["rooms"][cid]["discovered"]})
        alive_npcs = [n for n in room["npcs"] if n["alive"]]
        shop = next((n for n in alive_npcs if n["role"] == "shop"), None)
        stock = [{"n": i, "name": s["name"], "rarity": s["rarity"],
                  "value": s["value"], "slot": s["slot"]}
                 for i, s in enumerate(shop["stock"], 1)] if shop else []
        return {
            "depth": self.depth,
            "type": room["type"],
            "label": TYPE_LABEL[room["type"]],
            "scene": self._scene_text(room),
            "monsters": [{"name": m["name"], "is_boss": m["is_boss"]} for m in mons],
            "npcs": [{"name": n["name"], "role": n["role"]} for n in alive_npcs],
            "stock": stock,
            "item_count": len(room["items"]),
            "tome_count": len(room["tomes"]),
            "has_lore": bool(room["lore"]),
            "doors": doors,
            "is_exit": room["id"] == self.floor["exit_room"],
            "has_stairs": room["id"] == self.floor["exit_room"] and self.depth < config.MAX_FLOORS,
        }

    def _floor_map(self):
        rooms = []
        for rid, room in self.floor["rooms"].items():
            if not room["discovered"]:
                continue
            rooms.append({
                "id": rid,
                "type": room["type"],
                "label": TYPE_LABEL[room["type"]],
                "cleared": room["cleared"],
                "is_current": rid == self.current,
                "is_exit": rid == self.floor["exit_room"],
                "is_boss": rid == self.floor["boss_room"],
                "connections": [cid for cid in room["connections"]
                                 if self.floor["rooms"][cid]["discovered"]],
            })
        return {
            "depth": self.depth,
            "start": self.floor["start"],
            "current": self.current,
            "rooms": rooms,
        }

    def _player_snapshot(self):
        p = self.player
        equipment = {}
        for s in SLOTS:
            it = p.equipment[s]
            equipment[s] = ({"name": it["name"], "rarity": it["rarity"], "stats": it["stats"]}
                            if it else None)
        inventory = []
        for i, it in enumerate(p.inventory, 1):
            entry = {"n": i, "name": it["name"], "rarity": it["rarity"],
                     "slot": it["slot"], "value": it.get("value", 0)}
            if it["slot"] in SLOTS:
                entry["stats"] = it["stats"]
            else:
                entry["effect"] = it.get("effect", "")
                entry["power"] = it.get("power", "")
            inventory.append(entry)
        spells = []
        for sid in p.grimoire:
            sp = data.SPELLS[sid]
            att = p.attunement(sid)
            spells.append({
                "id": sid, "name": sp["name"], "element": sp["element"], "tier": sp["tier"],
                "cost": p.spell_cost(sid), "power": p.spell_power(sid), "attuned": att,
                "desc": sp["desc"], "aoe": bool(sp.get("aoe")), "kind": sp["kind"],
            })
        return {
            "hp": p.hp, "max_hp": p.max_hp, "mana": p.mana, "max_mana": p.max_mana,
            "atk": p.total_atk(), "def": p.total_def(), "sp": p.total_sp(),
            "gold": p.gold, "essence_run": self.meta.essence_run, "shield": p.shield_absorb(),
            "equipment": equipment, "inventory": inventory,
            "status": [{"kind": s["kind"], "turns": s["turns"], "power": s.get("power", 0)}
                       for s in p.status],
            "spells": spells,
        }

    def _combat_snapshot(self):
        c = self.combat
        if not c:
            return None
        return {
            "turn": c.turn,
            "defending": c.defending,
            "monsters": [
                {"n": i, "name": m["name"], "hp": m["hp"], "max_hp": m["max_hp"],
                 "is_boss": m["is_boss"],
                 "status": [s["kind"] for s in m["status"]]}
                for i, m in enumerate(c.alive(), 1)
            ],
        }

    # ===================================================================
    # HUB
    # ===================================================================
    def _hub_act(self, t, action):
        if t == "hub_begin":
            self._start_run()
        elif t == "hub_upgrade":
            ok, msg = self.meta.buy_stat(action.get("stat", ""))
            self._feed("system", msg)
        elif t == "hub_attune":
            sid = self._resolve_spell(action.get("spell", ""))
            if sid:
                ok, msg = self.meta.buy_attune(sid)
                self._feed("system", msg)
            else:
                self._feed("system", "Name a spell you've learned (see grimoire).")
        elif t == "hub_grimoire":
            ok, msg = self.meta.buy_grimoire()
            self._feed("system", msg)
        elif t == "hub_use_tome":
            ok, msg = self.meta.bind_spare_tome(
                self._resolve_spell(action.get("spell", "")),
                self._resolve_spell(action.get("arg", "")))
            self._feed("system", msg)
        elif t == "hub_dismiss":
            self._clear_run()
        else:
            self._feed("system", "Unknown camp command.")

    def _start_run(self):
        self.meta.runs += 1
        self.meta.essence_run = 0
        self.floors = [gen.make_floor(self.rng, d) for d in range(1, config.MAX_FLOORS + 1)]
        self.depth = 1
        self.floor = self.floors[0]
        self.current = self.floor["start"]
        self.prev_room = None
        self.player = Player(self.meta, self.rng)
        self.player.take(gen.make_consumable(self.rng, "health_potion", 1))
        self.player.take(gen.make_consumable(self.rng, "mana_potion", 1))
        self.ended = None
        self._feed("system", f"You descend into the Deep. Depth 1 of {config.MAX_FLOORS}.")
        if self.meta.deaths > 0:
            self._feed("system",
                       f"You have died {self.meta.deaths} time(s). "
                       f"Your grimoire of {len(self.meta.grimoire)} spell(s) is yours to keep.")
        self._enter_room()

    def _clear_run(self):
        self.ended = None
        self.floors = None
        self.depth = None
        self.floor = None
        self.current = None
        self.prev_room = None
        self.player = None
        self.combat = None

    def _resolve_spell(self, arg):
        arg = _norm_spell(arg)
        for sid, sp in data.SPELLS.items():
            if arg in (_norm_spell(sid), _norm_spell(sp["name"])):
                return sid
            if arg and arg in _norm_spell(sp["name"]):
                return sid
        return None

    # ===================================================================
    # EXPLORE
    # ===================================================================
    def _enter_room(self):
        room = self.floor["rooms"][self.current]
        mons = [m for m in room["monsters"] if m["alive"]]
        if mons:
            self._start_combat(room)
        else:
            self._loot_room(room)

    def _explore_act(self, t, action):
        if t == "move":
            self._move(action.get("n"))
        elif t == "move_room":
            self._move_room(action.get("room"))
        elif t == "descend":
            self._descend()
        elif t == "look":
            pass  # snapshot already re-renders the room
        elif t == "examine":
            self._examine(action.get("text", ""))
        elif t == "talk":
            self._talk(action.get("text", ""))
        elif t == "buy":
            self._buy(action.get("n"))
        elif t == "sell":
            self._sell(action.get("n"))
        elif t == "learn":
            self._learn()
        elif t == "heal":
            self._heal()
        elif t == "rest":
            self._rest()
        elif t == "equip":
            self._equip(action.get("arg"))
        elif t == "unequip":
            self._unequip(action.get("slot"))
        elif t == "drop":
            self._drop(action.get("arg"))
        elif t == "use":
            self._use_item(action.get("n"))
        elif t == "freeform":
            self._freeform(action.get("text", ""))
        else:
            self._freeform(t or "")

    def _scene_text(self, room):
        if room["scene"] is None:
            flavor = data.ROOM_FLAVOR.get(room["type"], "a dark room")
            fb = f"{flavor}, at depth {self.depth}."
            if self.narrator.ready():
                room["scene"] = self.narrator.room_scene(flavor, self.depth) or fb
            else:
                room["scene"] = fb
        return room["scene"]

    def _loot_room(self, room):
        for it in room["items"]:
            self.player.take(it)
            self._feed("loot", f"Picked up: {it['name']} "
                       f"({stat_str(it.get('stats') or {}) or it.get('effect', '')})")
        room["items"] = []
        for tome in room["tomes"]:
            self._learn_tome(tome)
        room["tomes"] = []
        for key in room["lore"]:
            self._discover_lore(key)
        room["lore"] = []
        room["cleared"] = True

    def _learn_tome(self, tome):
        sid = tome["spell_id"]
        name = data.SPELLS[sid]["name"]
        if self.player.knows(sid):
            att = self.player.attune_run(sid)
            self._feed("system",
                       f"You already know {name}. The tome deepens your attunement "
                       f"to {att} for this run.")
            return
        ok, msg = self.player.learn_spell(sid)
        if not ok:
            if msg == "full":
                if sid in self.meta.spare_tomes:
                    self._feed("system",
                               f"Your grimoire is full and you already keep a spare tome of {name}.")
                else:
                    self.meta.spare_tomes.append(sid)
                    self._feed("system",
                               f"Your grimoire is full. You tuck the tome of {name} away to "
                               f"bind later at the camp.")
            else:
                self._feed("system", msg)
            return
        self._feed("loot", f"* You learn {name}! It is added to your grimoire forever.")

    def _discover_lore(self, key):
        if key in self.meta.codex:
            return
        title, seed = data.LORE[key]
        text = self.narrator.lore_entry(title, seed) if self.narrator.ready() else seed
        self.meta.codex[key] = text
        self._feed("narration", f"Lore discovered — {title}: {text}")

    def _move(self, n):
        try:
            n = int(n)
        except (TypeError, ValueError):
            self._feed("system", "Which door? (numbered above)")
            return
        room = self.floor["rooms"][self.current]
        conns = room["connections"]
        if n < 1 or n > len(conns):
            self._feed("system", "No such door here.")
            return
        self.prev_room = self.current
        self.current = conns[n - 1]
        self._enter_room()

    def _move_room(self, room_id):
        """Move to a connected room by id (used when clicking a map node)."""
        room = self.floor["rooms"][self.current]
        conns = room["connections"]
        room_id = str(room_id)
        conns = [str(c) for c in conns]
        if room_id not in conns:
            self._feed("system", "No door leads there from here.")
            return
        self.prev_room = self.current
        self.current = int(room_id) if room_id.isdigit() else room_id
        self._maybe_wanderer_spawn(self.current)
        self._enter_room()

    def _maybe_wanderer_spawn(self, room_id):
        """Small chance a wanderer stalks a room as you move in. Skips safe
        rooms (camp/market) so shops and rest spots stay safe."""
        room_id = int(room_id) if str(room_id).isdigit() else room_id
        room = self.floor["rooms"][room_id]
        if room["type"] in ("camp", "market"):
            return
        if any(m["alive"] for m in room["monsters"]):
            return
        if room["id"] == self.floor["start"]:
            return
        if self.rng.random() > 0.12:
            return
        wanderers = gen.roll_monsters(self.rng, self.depth, count=self.rng.randint(1, 2))
        room["monsters"].extend(wanderers)
        self._feed("combat", f"Something stirs in the dark — a {wanderers[0]['name']} appears!")

    def _descend(self):
        room = self.floor["rooms"][self.current]
        if room["id"] != self.floor["exit_room"]:
            self._feed("system", "No stairs here.")
            return
        if self.depth >= config.MAX_FLOORS:
            self._feed("system", "This is the bottom of the Deep.")
            return
        self.depth += 1
        self.floor = self.floors[self.depth - 1]
        self.current = self.floor["start"]
        self.prev_room = None
        self.meta.best_depth = max(self.meta.best_depth, self.depth)
        self._feed("system", f"You descend the stairs to depth {self.depth}.")
        self._enter_room()

    def _use_item(self, n):
        try:
            n = int(n)
        except (TypeError, ValueError):
            self._feed("system", "Which item? (numbered in your pack)")
            return
        inv = self.player.inventory
        if n < 1 or n > len(inv):
            self._feed("system", "No such item in your pack.")
            return
        ok, msg = self.player.use_item(inv[n - 1]["id"])
        self._feed("system" if not ok else "loot", msg)

    # ---- individual explore actions ----------------------------------
    def _room_npc(self):
        room = self.floor["rooms"][self.current]
        for n in room["npcs"]:
            if n["alive"]:
                return n
        return None

    def _extract_target(self, line, room):
        line = (line or "").lower()
        for m in room["monsters"]:
            if m["name"].lower() in line:
                return m["name"]
        for n in room["npcs"]:
            if n["name"].lower() in line:
                return n["name"]
        for it in room["items"]:
            if it["name"].lower() in line:
                return it["name"]
        if "tablet" in line or "inscription" in line or "lore" in line:
            return "the ancient tablet"
        if "door" in line:
            return "the door"
        return f"the {TYPE_LABEL[room['type']]}"

    def _examine(self, line):
        room = self.floor["rooms"][self.current]
        target = self._extract_target(line, room)
        room_desc = self._scene_text(room)
        if self.narrator.ready():
            text = self.narrator.examine(target, room_desc) or f"You look closely at {target}."
        else:
            text = f"You examine {target}. It is old, and it has seen things."
        self._feed("narration", text)

    def _talk(self, text):
        npc = self._room_npc()
        room = self.floor["rooms"][self.current]
        if not npc:
            self._freeform(text or "you call out into the dark")
            return
        room_desc = f"{TYPE_LABEL[room['type']]}, depth {self.depth}"
        if self.narrator.ready():
            reply = self.narrator.npc_reply(npc["name"], npc["persona"], text or "You approach.", room_desc) \
                or f"{npc['name']} regards you silently."
        else:
            reply = f"{npc['name']} regards you. (narrator offline — dialogue is limited.)"
        self._feed("npc", f"{npc['name']}: {reply}")
        if npc["role"] == "lore" and self.rng.random() < 0.6:
            undiscovered = [k for k in data.LORE if k not in self.meta.codex]
            if undiscovered:
                self._discover_lore(self.rng.choice(undiscovered))
        if npc["role"] == "shop" and not npc.get("greeted"):
            npc["greeted"] = True

    def _buy(self, n):
        npc = self._room_npc()
        if not npc or npc["role"] != "shop":
            self._feed("system", "No one here is selling anything.")
            return
        if n is not None:
            try:
                n = int(n)
            except (TypeError, ValueError):
                n = None
        if n is not None:
            if 1 <= n <= len(npc["stock"]):
                it = npc["stock"][n - 1]
                price = it["value"]
                if self.player.gold >= price:
                    self.player.gold -= price
                    npc["stock"].remove(it)
                    self.player.take(it)
                    self._feed("loot", f"Bought {it['name']} for {price}g.")
                else:
                    self._feed("system", f"Not enough gold (need {price}, have {self.player.gold}).")
            else:
                self._feed("system", "No such item.")
            return
        if not npc["stock"]:
            self._feed("system", "The shop is empty.")
            return
        blurb = self.narrator.shop_blurb(npc["name"], npc["persona"], [s["name"] for s in npc["stock"]]) \
            if self.narrator.ready() else f"{npc['name']} spreads out the wares."
        self._feed("npc", blurb)
        for i, s in enumerate(npc["stock"], 1):
            self._feed("system", f"  {i}) {s['name']} ({s['rarity']}) — {s['value']}g")
        self._feed("system", f"Your gold: {self.player.gold}")

    def _sell(self, n):
        npc = self._room_npc()
        if not npc or npc["role"] not in ("shop", "blacksmith"):
            self._feed("system", "No one here will buy from you.")
            return
        try:
            n = int(n)
        except (TypeError, ValueError):
            self._feed("system", "Sell what? (pack number)")
            return
        inv = self.player.inventory
        if 1 <= n <= len(inv):
            it = inv[n - 1]
            price = max(1, it["value"] // 2) if it["slot"] in SLOTS else max(1, it.get("power", 4) // 2)
            self.player.gold += price
            inv.remove(it)
            self._feed("loot", f"Sold {it['name']} for {price}g.")
        else:
            self._feed("system", "No such item.")

    def _learn(self):
        npc = self._room_npc()
        if not npc or npc["role"] != "sage":
            self._feed("system", "No one here is teaching spells.")
            return
        if npc.get("taught_spell"):
            self._feed("system", "The Sage has nothing more to teach you this descent.")
            return
        if len(self.player.grimoire) >= self.meta.grimoire_capacity:
            cap = self.meta.grimoire_capacity
            self._feed("system",
                       f"Your grimoire is full ({cap}/{cap}). Bind more pages at the camp "
                       f"before the Sage can teach you.")
            return
        tier = gen.depth_tier(self.depth)
        pool = [sid for sid in data.SPELLS
                if data.SPELLS[sid]["tier"] <= tier and not self.player.knows(sid)]
        if not pool:
            self._feed("system", "The Sage sees you know all that is useful down here.")
            return
        sid = self.rng.choice(pool)
        self.player.learn_spell(sid)
        npc["taught_spell"] = sid
        self._feed("loot", f"The Sage teaches you {data.SPELLS[sid]['name']}! (added to your grimoire forever.)")

    def _heal(self):
        npc = self._room_npc()
        if not npc or npc["role"] not in ("hermit", "blacksmith"):
            self._feed("system", "No one here will mend you.")
            return
        cost = 15
        if self.player.gold < cost:
            self._feed("system", f"They want {cost}g (you have {self.player.gold}).")
            return
        self.player.gold -= cost
        self.player.hp = self.player.max_hp
        self.player.mana = self.player.max_mana
        self._feed("system", f"{npc['name']} mends you. Fully restored. (-{cost}g)")

    def _rest(self):
        room = self.floor["rooms"][self.current]
        if room["type"] != "camp":
            self._feed("system", "You need a safe camp hollow to rest.")
            return
        if any(m["alive"] for m in room["monsters"]):
            self._feed("system", "Too dangerous to rest.")
            return
        self.player.hp = self.player.max_hp
        self.player.mana = self.player.max_mana
        self._feed("system", "You rest by the old fire. Fully restored.")

    def _resolve_item(self, arg):
        if arg is None:
            return None
        arg = str(arg).strip()
        if arg.isdigit():
            i = int(arg)
            if 1 <= i <= len(self.player.inventory):
                return self.player.inventory[i - 1]
            return None
        a = arg.lower()
        for it in self.player.inventory:
            if a in it["name"].lower():
                return it
        return None

    def _equip(self, arg):
        it = self._resolve_item(arg)
        if not it:
            self._feed("system", "Equip what? (pack number or name)")
            return
        ok, msg = self.player.equip(it["id"])
        self._feed("system", msg)

    def _unequip(self, slot):
        if slot in SLOTS:
            ok, msg = self.player.unequip(slot)
            self._feed("system", msg)
        else:
            self._feed("system", "Unequip which slot? (weapon, armor, helm, boots, trinket)")

    def _drop(self, arg):
        it = self._resolve_item(arg)
        if it:
            ok, msg = self.player.drop(it["id"])
            self._feed("system", msg)

    def _freeform(self, line):
        room = self.floor["rooms"][self.current]
        npc = self._room_npc()
        room_desc = self._scene_text(room)
        looks_like_talk = line.startswith(("ask", "say", "speak", "talk", "tell", "hello", "hey", "who"))
        if npc and (looks_like_talk or self.rng.random() < 0.55):
            self._talk(line)
            return
        if any(v in line for v in ("examine", "inspect", "look at", "study", "read", "touch", "smell")):
            self._examine(line)
            return
        if self.narrator.ready():
            text = self.narrator.ambient(line, room_desc) or f"You {line}. The dark is unimpressed."
        else:
            text = f"You {line}. Nothing happens."
        self._feed("narration", text)

    # ===================================================================
    # COMBAT
    # ===================================================================
    def _start_combat(self, room):
        mons = [m for m in room["monsters"] if m["alive"]]
        self.combat = Combat(self.player, mons, self)
        for m in mons:
            if m["is_boss"] or self.rng.random() < 0.5:
                intro = self.narrator.monster_intro(m["name"], m["desc"], m["is_boss"]) \
                    if self.narrator.ready() else m["desc"]
                self._feed("combat", f"A {m['name']} blocks the way!")
                if intro:
                    self._feed("narration", intro)

    def _combat_act(self, t, action):
        c = self.combat
        if t == "attack":
            c.act("attack", action.get("n"))
        elif t == "cast":
            sid = self._resolve_spell(action.get("spell", ""))
            if sid:
                n = action.get("n")
                c.act("cast", (sid, n) if n else sid)
            else:
                self._feed("system", "You don't know a spell by that name.")
        elif t == "defend":
            c.act("defend")
        elif t == "flee":
            c.act("flee")
        elif t == "use":
            n = action.get("n")
            if n and 1 <= n <= len(self.player.inventory):
                c.act("use", self.player.inventory[n - 1]["id"])
            else:
                self._feed("system", "No such item.")
        else:
            self._feed("system", "In combat: attack, cast, defend, use, flee.")
        for m in c.log:
            self._feed("combat", m)
        c.log = []
        if c.over:
            self._combat_end()

    def _combat_end(self):
        c = self.combat
        room = self.floor["rooms"][self.current]
        if c.result == "win":
            room["cleared"] = True
            for m in room["monsters"]:
                m["alive"] = False
            self.combat = None
            self._loot_room(room)
            if self.depth == config.MAX_FLOORS and room["id"] == self.floor["boss_room"]:
                self._on_victory()
        elif c.result == "lose":
            last = [m for m in c.monsters if m["alive"]]
            self.combat = None
            self._on_death("overwhelmed in battle", last[0]["name"] if last else "the dark")
        elif c.result == "fled":
            self.combat = None
            if self.prev_room is not None:
                self.current = self.prev_room

    # ===================================================================
    # DEATH / VICTORY
    # ===================================================================
    def _on_death(self, how, monster_name):
        m = self.meta
        m.deaths += 1
        m.total_essence += m.essence_run
        m.best_depth = max(m.best_depth, self.depth)
        if self.narrator.ready():
            scene = self.narrator.death_scene("you", how, self.depth, monster_name) \
                or f"You fall at depth {self.depth}. Your gear is lost to the dark."
        else:
            scene = f"You fall at depth {self.depth} to the {monster_name}. Your gear is lost."
        self.ended = "dead"
        self._feed("death", scene)
        self._feed("system", f"Essence kept: +{m.essence_run}  (banked {m.essence})")
        self._feed("system", f"Spells kept: {len(m.grimoire)}")
        self._feed("system", "Equipment, gold, and consumables are lost to the Deep. Your knowledge is not.")

    def _on_victory(self):
        m = self.meta
        m.essence += 100
        m.total_essence += m.essence_run + 100
        m.best_depth = max(m.best_depth, self.depth)
        if self.narrator.ready():
            scene = self.narrator.victory_scene("you", self.depth, "the Hollow King") \
                or "You conquer the Deep."
        else:
            scene = "You slay the Hollow King and conquer the Deep."
        self.ended = "victory"
        self._feed("victory", scene)
        self._feed("system", f"Victory! +100 bonus essence. Banked essence: {m.essence}.")
