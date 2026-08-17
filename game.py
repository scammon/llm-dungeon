"""The main game: hub (between runs) and the dungeon run loop.

Architecture: the LLM narrates (rooms, NPCs, items, deaths); the code referees
(combat numbers, inventory, spell effects, roguelite persistence). Free-text the
player types is routed to the LLM for "deeper interaction" (dialogue,
examination, ambient narration) but can never change game state by itself.

Run:  python game.py            (uses the local llama.cpp server)
      python game.py --no-llm   (deterministic fallbacks only)
      python game.py --verbose  (print LLM call stats)
"""
import sys
import random
import data
import config
import gen
import ui
from player import Player, SLOTS
from combat import Combat
from meta import MetaSave
from llm import get_llm

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

EXPLORE_PROMPT = "\033[36m  >\033[0m "
HUB_PROMPT = "\033[35m  camp>\033[0m "


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


class Game:
    def __init__(self, no_llm=False, verbose=False, seed=None):
        self.llm = get_llm(enabled=False if no_llm else None, verbose=verbose)
        self.meta = MetaSave.load()
        self.rng = random.Random(seed)
        self.depth = 1
        self.floors = None
        self.floor = None
        self.current = None
        self.prev_room = None
        self.player = None
        self.combat = None

    # ===================================================================
    # TOP LEVEL
    # ===================================================================
    def play(self):
        print(ui.hr("="))
        print(ui.bold("        THE HOLLOW DEEP"))
        print(ui.gray("        a roguelite dungeon crawler — die, and only your knowledge survives"))
        print(ui.hr("="))
        if not self.llm.enabled:
            print(ui.yellow("  LLM disabled — running on written fallbacks."))
        elif not self.llm.ready():
            print(ui.yellow("  LLM server unreachable — running on written fallbacks."))
            print(ui.gray(f"  (expected at {config.BASE_URL})"))
        else:
            print(ui.gray(f"  LLM narrator connected: {config.MODEL}"))
        print(ui.gray(f"  Save file: {config.SAVE_PATH}"))
        print()
        self.hub()

    # ===================================================================
    # HUB (between runs)
    # ===================================================================
    def hub(self):
        while True:
            self.show_hub()
            line = input(HUB_PROMPT).strip().lower()
            if line in ("begin", "start", "descend", "d", "new", "run"):
                res = self.run()
                if res == "quit":
                    return
            elif line.startswith(("upgrade ", "up ")):
                kind = line.split()[1].replace(" ", "_")
                ok, msg = self.meta.buy_stat(kind)
                self.meta.save()
                print("  " + msg)
            elif line.startswith("attune "):
                arg = line.split(None, 1)[1]
                sid = self.resolve_spell(arg)
                if sid:
                    ok, msg = self.meta.buy_attune(sid)
                    self.meta.save()
                else:
                    msg = "Name a spell you've learned (see grimoire)."
                print("  " + msg)
            elif line in ("expand", "bind", "page"):
                ok, msg = self.meta.buy_grimoire()
                self.meta.save()
                print("  " + msg)
            elif line == "tome" or line.startswith("tome "):
                self.do_bind_tome(line)
            elif line in ("codex", "lore", "c"):
                self.show_codex()
            elif line in ("spells", "s", "grimoire", "g"):
                self.show_grimoire()
            elif line in ("help", "?", "h"):
                self.show_hub_help()
            elif line in ("quit", "q", "exit"):
                self.meta.save()
                print("  You bank your essence and rest. Farewell.")
                return
            else:
                print("  Unknown. Try: begin, upgrade <stat>, attune <spell>, codex, grimoire, help, quit")

    def show_hub(self):
        m = self.meta
        print(ui.hr())
        print(ui.bold("  THE CAMP — between descents"))
        print(ui.hr())
        print(f"  Essence: {ui.magenta(str(m.essence))}")
        print(f"  Runs: {m.runs}    Deaths: {m.deaths}    Deepest reached: {m.best_depth}")
        print("  Base upgrades (costs in essence):")
        for k in ("hp", "mana", "atk", "defense", "sp_power"):
            print(f"    {k:9} lvl {m.up.get(k, 0):<2}  next {m.upgrade_cost(k)}")
        gc = m.grimoire_cost()
        gc_txt = f"next slot {gc}" if gc else "fully bound"
        spare_txt = f"    Spare tomes: {len(m.spare_tomes)}" if m.spare_tomes else ""
        print(f"  Grimoire: {len(m.grimoire)}/{m.grimoire_capacity} spell slots    "
              f"Attunements: {sum(m.attunements.values())}    ({gc_txt}){spare_txt}")
        print()
        print(ui.gray("  begin | upgrade <hp|mana|atk|def|sp_power> | attune <spell> | expand | tome | codex | grimoire | help | quit"))

    def show_grimoire(self):
        m = self.meta
        if not m.grimoire:
            print("  Your grimoire is empty. Descend and find tomes to learn spells.")
            return
        for sid in m.grimoire:
            sp = data.SPELLS[sid]
            att = m.attunements.get(sid, 0)
            print(f"    {ui.cyan(sp['name'])} ({sp['element']}, tier {sp['tier']})  attuned {att}"
                  + (f"  (cost {max(1, sp['cost']-att)}, power {sp['power']+att*2})" if att else f"  (cost {sp['cost']}, power {sp['power']})"))
            print(f"       {sp['desc']}")

    def show_codex(self):
        m = self.meta
        if not m.codex:
            print("  No lore discovered yet. Seek tablets and wandering souls.")
            return
        for key, text in m.codex.items():
            title, _ = data.LORE[key]
            print(ui.cyan(f"  {title}"))
            print("   " + text)

    def show_hub_help(self):
        print(ui.panel("Camp commands", [
            "begin      start a new descent",
            "upgrade X  spend essence on a permanent base stat (hp, mana, atk, def, sp_power)",
            "attune S   spend essence to strengthen a spell you've learned",
            "expand     spend essence to bind a new spell slot in your grimoire",
            "tome       list spare tomes; 'tome <spell> [forget <spell>]' binds one",
            "codex      read your discovered lore",
            "grimoire   review learned spells",
            "quit       save and exit",
            "",
            "Death is permanent for gear & gold, but every spell you learn",
            "stays in your grimoire forever.",
        ]))

    def resolve_spell(self, arg):
        arg = _norm_spell(arg)
        for sid, sp in data.SPELLS.items():
            if arg in (_norm_spell(sid), _norm_spell(sp["name"])):
                return sid
            if arg and arg in _norm_spell(sp["name"]):
                return sid
        return None

    def do_bind_tome(self, line):
        m = self.meta
        if not m.spare_tomes:
            print("  You carry no spare tomes. Find tomes of new spells while your grimoire is full.")
            return
        parts = line.split(None, 1)
        if len(parts) < 2:
            print(ui.bold("  Spare tomes you carry:"))
            for sid in m.spare_tomes:
                sp = data.SPELLS[sid]
                print(f"    {ui.cyan(sp['name'])} (tier {sp['tier']}) — {sp['desc']}")
            print(ui.gray("  tome <spell> [forget <spell>]   bind a spare tome (forget a known spell if the grimoire is full)"))
            return
        arg = parts[1]
        # spell names contain spaces, so split on the ' forget ' delimiter
        low = arg.lower()
        if " forget " in low:
            idx = low.index(" forget ")
            tome_sid = self.resolve_spell(arg[:idx])
            replace_sid = self.resolve_spell(arg[idx + len(" forget "):])
        else:
            tome_sid = self.resolve_spell(arg)
            replace_sid = None
        if not tome_sid:
            print("  Name a spare tome's spell (see 'tome').")
            return
        ok, msg = m.bind_spare_tome(tome_sid, replace_sid)
        if ok:
            m.save()
        print("  " + msg)

    # ===================================================================
    # RUN
    # ===================================================================
    def start_run(self):
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
        print()
        print(ui.bold(ui.cyan(f"  You descend into the Deep. Depth 1 of {config.MAX_FLOORS}.")))
        if self.meta.deaths > 0:
            print(ui.gray(f"  You have died {self.meta.deaths} time(s). "
                          f"Your grimoire of {len(self.meta.grimoire)} spell(s) is yours to keep."))
        print()

    def run(self):
        self.start_run()
        while True:
            r = self.explore_step()
            if r in ("dead", "victory", "quit"):
                return r

    def explore_step(self):
        room = self.floor["rooms"][self.current]
        self.show_room(room)
        mons = [m for m in room["monsters"] if m["alive"]]
        if mons:
            res = self.start_combat(room)
            if res:
                return res
        else:
            self.loot_room(room)
        while True:
            line = input(EXPLORE_PROMPT).strip().lower()
            if not line:
                continue
            if line.startswith("go "):
                if self.try_move(line):
                    return None
            elif line in ("descend", "down", "stairs"):
                if self.try_descend():
                    return None
            elif line in ("quit", "q", "save"):
                r = self.confirm_quit()
                if r:
                    return r
            else:
                self.handle_explore_cmd(line)

    # ---- room display -------------------------------------------------
    def show_room(self, room):
        room["discovered"] = True
        print(ui.hr())
        print(ui.bold(f"  Depth {self.depth} — {TYPE_LABEL[room['type']]}"))
        print(ui.hr())
        print("  " + self.scene_text(room))
        mons = [m["name"] for m in room["monsters"] if m["alive"]]
        if mons:
            print(ui.red("  You see: " + ", ".join(mons)))
        npcs = [n["name"] for n in room["npcs"] if n["alive"]]
        if npcs:
            print(ui.cyan("  Present: " + ", ".join(npcs)))
        if room["items"]:
            print(f"  Loot glints here ({len(room['items'])} item).")
        if room["tomes"]:
            print(f"  {len(room['tomes'])} tome(s) rest here.")
        if room["lore"]:
            print("  An ancient tablet bears inscriptions.")
        conns = room["connections"]
        if conns:
            print("  Doors:")
            for i, cid in enumerate(conns, 1):
                t = self.floor["rooms"][cid]["type"]
                disc = " (explored)" if self.floor["rooms"][cid]["discovered"] else ""
                print(f"    {i}) {TYPE_LABEL[t]}{disc}")
        if room["id"] == self.floor["exit_room"]:
            print(ui.cyan("  Stairs descend deeper."))
        print()
        print(ui.gray("  go <n> | descend | look | examine <x> | talk <...> | buy | sell | learn | heal | rest | status | inventory | spells | map | help"))

    def scene_text(self, room):
        if room["scene"] is None:
            flavor = data.ROOM_FLAVOR.get(room["type"], "a dark room")
            fb = f"{flavor}, at depth {self.depth}."
            if self.llm.ready():
                room["scene"] = self.llm.room_scene(flavor, self.depth) or fb
            else:
                room["scene"] = fb
        return room["scene"]

    # ---- loot / learning / lore --------------------------------------
    def loot_room(self, room):
        for it in room["items"]:
            self.player.take(it)
            print(ui.green(f"  Picked up: {ui.rarity(it['name'], it['rarity'])} ({stat_str(it.get('stats') or {}) or it.get('effect','')})"))
        room["items"] = []
        for tome in room["tomes"]:
            self.learn_tome(tome)
        room["tomes"] = []
        for key in room["lore"]:
            self.discover_lore(key)
        room["lore"] = []
        room["cleared"] = True

    def learn_tome(self, tome):
        sid = tome["spell_id"]
        name = data.SPELLS[sid]["name"]
        if self.player.knows(sid):
            att = self.player.attune_run(sid)
            print(ui.gray(f"  You already know {name}. The tome deepens your attunement to {att} for this run."))
            return
        ok, msg = self.player.learn_spell(sid)
        if not ok:
            if msg == "full":
                if sid in self.meta.spare_tomes:
                    print(ui.yellow(f"  Your grimoire is full and you already keep a spare tome of {name}."))
                else:
                    self.meta.spare_tomes.append(sid)
                    self.meta.save()
                    print(ui.yellow(f"  Your grimoire is full. You tuck the tome of {name} away to bind later at the camp."))
            else:
                print(ui.gray(f"  {msg}"))
            return
        self.meta.save()
        print(ui.magenta(f"  * You learn {name}! It is added to your grimoire forever."))

    def discover_lore(self, key):
        if key in self.meta.codex:
            return
        title, seed = data.LORE[key]
        text = self.llm.lore_entry(title, seed) if self.llm.ready() else seed
        self.meta.codex[key] = text
        self.meta.save()
        print(ui.cyan(f"  Lore discovered — {title}:"))
        print("   " + text)

    # ---- movement -----------------------------------------------------
    def try_move(self, line):
        try:
            n = int(line.split()[1])
        except (IndexError, ValueError):
            print("  Which door? (numbered above)")
            return False
        room = self.floor["rooms"][self.current]
        conns = room["connections"]
        if n < 1 or n > len(conns):
            print("  No such door here.")
            return False
        self.prev_room = self.current
        self.current = conns[n - 1]
        return True

    def try_descend(self):
        room = self.floor["rooms"][self.current]
        if room["id"] != self.floor["exit_room"]:
            print("  No stairs here.")
            return False
        if self.depth >= config.MAX_FLOORS:
            print("  This is the bottom of the Deep.")
            return False
        self.depth += 1
        self.floor = self.floors[self.depth - 1]
        self.current = self.floor["start"]
        self.prev_room = None
        self.meta.best_depth = max(self.meta.best_depth, self.depth)
        self.meta.save()
        print(ui.cyan(f"  You descend the stairs to depth {self.depth}."))
        return True

    def confirm_quit(self):
        if input("  Abandon this run and return to camp? (y/N) ").strip().lower() in ("y", "yes"):
            self.meta.save()
            print("  You retreat to camp. Your grimoire is safe.")
            return "quit"
        return None

    # ===================================================================
    # COMBAT
    # ===================================================================
    def start_combat(self, room):
        mons = [m for m in room["monsters"] if m["alive"]]
        self.combat = Combat(self.player, mons, self)
        for m in mons:
            if m["is_boss"] or self.rng.random() < 0.5:
                intro = self.llm.monster_intro(m["name"], m["desc"], m["is_boss"]) if self.llm.ready() else m["desc"]
                print(ui.red(f"  A {m['name']} blocks the way!"))
                if intro:
                    print("   " + intro)
        print(ui.red(ui.hr()))
        return self.combat_loop(room)

    def combat_loop(self, room):
        c = self.combat
        while not c.over:
            self.combat_status(c)
            line = input("\033[31m  fight>\033[0m ").strip().lower()
            if not line:
                continue
            self.handle_combat_cmd(line, c)
            for m in c.log:
                print("  " + m)
            c.log = []
            if c.over:
                break
        res = None
        if c.result == "win":
            room["cleared"] = True
            for m in room["monsters"]:
                m["alive"] = False
            self.loot_room(room)
            if self.depth == config.MAX_FLOORS and room["id"] == self.floor["boss_room"]:
                self.on_victory()
                res = "victory"
        elif c.result == "lose":
            last = [m for m in c.monsters if m["alive"]]
            how = "overwhelmed in battle"
            self.on_death(how, last[0]["name"] if last else "the dark")
            res = "dead"
        elif c.result == "fled":
            if self.prev_room is not None:
                self.current = self.prev_room
                self.show_room(self.floor["rooms"][self.current])
        self.combat = None
        return res

    def combat_status(self, c):
        p = self.player
        shield = p.shield_absorb()
        shield_txt = f"  shield {shield}" if shield else ""
        print(f"  HP {p.hp}/{p.max_hp}   Mana {p.mana}/{p.max_mana}   "
              f"ATK {p.total_atk()}   DEF {p.total_def()}   SP {p.total_sp()}{shield_txt}")
        for i, m in enumerate(c.alive(), 1):
            st = ""
            if any(s["kind"] == "poison" for s in m["status"]):
                st += " [poisoned]"
            if any(s["kind"] == "stunned" for s in m["status"]):
                st += " [stunned]"
            if any(s["kind"] == "chill" for s in m["status"]):
                st += " [chilled]"
            print(f"    {i}) {m['name']}: {m['hp']}/{m['max_hp']}{st}")
        print(ui.gray("  attack [n] | cast <spell> [n] | defend | use <item> | flee | spells"))

    def handle_combat_cmd(self, line, c):
        if line.startswith("attack"):
            idx = self._arg_int(line)
            c.act("attack", idx)
        elif line.startswith("cast") or line.startswith("spell"):
            parts = line.split()
            if len(parts) < 2:
                print("  Cast which spell? (see 'spells')")
                return
            args = parts[1:]
            idx = None
            if args[-1].isdigit() and len(args) > 1:
                idx = int(args[-1])
                args = args[:-1]
            sid = self.resolve_spell(" ".join(args))
            if sid:
                c.act("cast", (sid, idx) if idx else sid)
            else:
                print("  You don't know a spell by that name.")
        elif line == "defend":
            c.act("defend")
        elif line == "flee":
            c.act("flee")
        elif line.startswith("use"):
            if len(line.split()) < 2:
                print("  Use what? (pack number)")
                return
            idx = self._arg_int(line)
            if idx and 1 <= idx <= len(self.player.inventory):
                c.act("use", self.player.inventory[idx - 1]["id"])
            else:
                print("  No such item.")
        elif line == "spells" or line == "s":
            self.show_spells()
        else:
            print("  In combat: attack, cast, defend, use, flee, spells.")

    def _arg_int(self, line):
        parts = line.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            return int(parts[-1])
        return None

    # ===================================================================
    # EXPLORE COMMANDS
    # ===================================================================
    def handle_explore_cmd(self, line):
        if line in ("look", "l"):
            self.show_room(self.floor["rooms"][self.current])
        elif line.startswith(("examine", "inspect", "study", "look at", "read")):
            self.do_examine(line)
        elif line.startswith(("talk", "speak", "ask", "say", "tell")):
            self.do_talk(line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else "")
        elif line.startswith("buy"):
            self.do_buy(line)
        elif line.startswith("sell"):
            self.do_sell(line)
        elif line == "learn":
            self.do_learn()
        elif line == "heal":
            self.do_heal()
        elif line == "rest":
            self.do_rest()
        elif line == "status":
            self.do_status()
        elif line in ("inventory", "i", "pack", "inv"):
            self.show_inventory()
        elif line in ("spells", "s", "grimoire"):
            self.show_spells()
        elif line == "map":
            self.show_map()
        elif line == "equip" or line.startswith("equip "):
            arg = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else None
            self.do_equip(arg)
        elif line.startswith("unequip "):
            slot = line.split()[1]
            if slot in SLOTS:
                ok, msg = self.player.unequip(slot)
                print("  " + msg)
            else:
                print("  Unequip which slot? (weapon, armor, helm, boots, trinket)")
        elif line.startswith("drop "):
            it = self.resolve_item(line.split(None, 1)[1])
            if it:
                ok, msg = self.player.drop(it["id"])
                print("  " + msg)
        elif line in ("help", "?", "h"):
            self.show_explore_help()
        else:
            # free-form -> LLM narrator
            self.freeform(line)

    # ---- individual explore actions ----------------------------------
    def do_status(self):
        p = self.player
        print(ui.panel("Status", [
            f"HP {p.hp}/{p.max_hp}    Mana {p.mana}/{p.max_mana}",
            f"ATK {p.total_atk()}    DEF {p.total_def()}    Spell Power {p.total_sp()}",
            f"Gold {p.gold}    Essence (run) {self.meta.essence_run}",
            f"Depth {self.depth}    Grimoire {len(p.grimoire)} spell(s)",
            "Status: " + (", ".join(f"{s['kind']}({s['turns']})" for s in p.status) or "none"),
        ]))

    def show_inventory(self):
        p = self.player
        print(ui.bold("  Equipment:"))
        for s in SLOTS:
            it = p.equipment[s]
            if it:
                print(f"    {s:8} {ui.rarity(it['name'], it['rarity'])}  ({stat_str(it['stats'])})")
            else:
                print(f"    {s:8} —")
        print(ui.bold("  Pack:"))
        if not p.inventory:
            print("    (empty)")
        for i, it in enumerate(p.inventory, 1):
            if it["slot"] in SLOTS:
                extra = stat_str(it["stats"])
            else:
                extra = f"[{it.get('effect','')} {it.get('power','')}]"
            print(f"    {i}) {ui.rarity(it['name'], it['rarity'])}  {extra}")
        print(f"  Gold: {p.gold}    HP {p.hp}/{p.max_hp}    Mana {p.mana}/{p.max_mana}")

    def show_spells(self):
        p = self.player
        if not p.grimoire:
            print("  Your grimoire is empty. Find tomes or a Sage to learn spells.")
            return
        for sid in p.grimoire:
            sp = data.SPELLS[sid]
            att = p.attunement(sid)
            tail = f", attuned {att}" if att else ""
            print(f"    {ui.cyan(sp['name'])} ({sp['element']}, t{sp['tier']}) — {p.spell_cost(sid)} mana, power {p.spell_power(sid)}{tail}")
            print(f"       {sp['desc']}")

    def show_map(self):
        f = self.floor
        print(ui.bold(f"  Map — depth {self.depth}:"))
        for rid in sorted(f["rooms"]):
            r = f["rooms"][rid]
            if not r["discovered"]:
                continue
            mark = "*" if rid == self.current else ("." if r["cleared"] else "?")
            label = TYPE_LABEL[r["type"]]
            extra = ""
            if any(m["alive"] for m in r["monsters"]):
                extra += " [monsters]"
            if r["id"] == f["exit_room"]:
                extra += " [stairs]"
            print(f"    {mark} {label}{extra}")

    def show_explore_help(self):
        print(ui.panel("Dungeon commands", [
            "go <n>        move through a numbered door",
            "descend       take the stairs to the next depth (only at the exit room)",
            "look          re-describe the room",
            "examine <x>   look closely at something (LLM narrates)",
            "talk <...>    speak to an NPC (free text, LLM in character)",
            "buy [n]       browse / buy from a shopkeeper",
            "sell <n>      sell a pack item to a shopkeeper",
            "learn         ask a Sage to teach you a spell",
            "heal          pay a healer/blacksmith to restore you",
            "rest          rest at a camp (full restore)",
            "equip <n>     equip a pack item   |   unequip <slot>",
            "drop <n>      drop a pack item",
            "status / inventory / spells / map",
            "Any other text is passed to the narrator.",
        ]))

    def do_equip(self, arg):
        it = self.resolve_item(arg)
        if not it:
            print("  Equip what? (pack number or name)")
            return
        ok, msg = self.player.equip(it["id"])
        print("  " + msg)

    def resolve_item(self, arg):
        if arg is None:
            return None
        arg = arg.strip()
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

    def do_examine(self, line):
        room = self.floor["rooms"][self.current]
        target = self.extract_target(line, room)
        room_desc = self.scene_text(room)
        if self.llm.ready():
            text = self.llm.examine(target, room_desc) or f"You look closely at {target}."
        else:
            text = f"You examine {target}. It is old, and it has seen things."
        print("  " + text)

    def extract_target(self, line, room):
        line = line.lower()
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

    def room_npc(self):
        room = self.floor["rooms"][self.current]
        for n in room["npcs"]:
            if n["alive"]:
                return n
        return None

    def do_talk(self, text):
        npc = self.room_npc()
        room = self.floor["rooms"][self.current]
        if not npc:
            self.freeform(text or "you call out into the dark")
            return
        room_desc = f"{TYPE_LABEL[room['type']]}, depth {self.depth}"
        if self.llm.ready():
            reply = self.llm.npc_reply(npc["name"], npc["persona"], text or "You approach.", room_desc) \
                or f"{npc['name']} regards you silently."
        else:
            reply = f"{npc['name']} regards you. (LLM offline — dialogue is limited.)"
        print(f"  {ui.cyan(npc['name'])}: {reply}")
        # role-specific hooks
        if npc["role"] == "lore" and self.rng.random() < 0.6:
            undiscovered = [k for k in data.LORE if k not in self.meta.codex]
            if undiscovered:
                self.discover_lore(self.rng.choice(undiscovered))
        if npc["role"] == "shop" and not npc.get("greeted"):
            npc["greeted"] = True

    def do_buy(self, line):
        npc = self.room_npc()
        if not npc or npc["role"] != "shop":
            print("  No one here is selling anything.")
            return
        parts = line.split()
        if len(parts) > 1 and parts[1].isdigit():
            n = int(parts[1])
            if 1 <= n <= len(npc["stock"]):
                it = npc["stock"][n - 1]
                price = it["value"]
                if self.player.gold >= price:
                    self.player.gold -= price
                    npc["stock"].remove(it)
                    self.player.take(it)
                    print(f"  Bought {ui.rarity(it['name'], it['rarity'])} for {price}g.")
                else:
                    print(f"  Not enough gold (need {price}, have {self.player.gold}).")
            else:
                print("  No such item.")
            return
        if not npc["stock"]:
            print("  The shop is empty.")
            return
        blurb = self.llm.shop_blurb(npc["name"], npc["persona"], [s["name"] for s in npc["stock"]]) \
            if self.llm.ready() else f"{npc['name']} spreads out the wares."
        print("  " + blurb)
        for i, s in enumerate(npc["stock"], 1):
            print(f"    {i}) {ui.rarity(s['name'], s['rarity'])} ({s['rarity']}) — {s['value']}g")
        print(f"  Your gold: {self.player.gold}")

    def do_sell(self, line):
        npc = self.room_npc()
        if not npc or npc["role"] not in ("shop", "blacksmith"):
            print("  No one here will buy from you.")
            return
        parts = line.split()
        if len(parts) < 2 or not parts[1].isdigit():
            print("  Sell what? (pack number)")
            self.show_inventory()
            return
        n = int(parts[1])
        inv = self.player.inventory
        if 1 <= n <= len(inv):
            it = inv[n - 1]
            price = max(1, it["value"] // 2) if it["slot"] in SLOTS else max(1, it.get("power", 4) // 2)
            self.player.gold += price
            inv.remove(it)
            print(f"  Sold {it['name']} for {price}g.")
        else:
            print("  No such item.")

    def do_learn(self):
        npc = self.room_npc()
        if not npc or npc["role"] != "sage":
            print("  No one here is teaching spells.")
            return
        if npc.get("taught_spell"):
            print("  The Sage has nothing more to teach you this descent.")
            return
        tier = gen.depth_tier(self.depth)
        pool = [sid for sid in data.SPELLS
                if data.SPELLS[sid]["tier"] <= tier and not self.player.knows(sid)]
        if not pool:
            print("  The Sage sees you know all that is useful down here.")
            return
        sid = self.rng.choice(pool)
        self.player.learn_spell(sid)
        self.meta.save()
        npc["taught_spell"] = sid
        print(ui.magenta(f"  The Sage teaches you {data.SPELLS[sid]['name']}! (added to your grimoire forever.)"))

    def do_heal(self):
        npc = self.room_npc()
        if not npc or npc["role"] not in ("hermit", "blacksmith"):
            print("  No one here will mend you.")
            return
        cost = 15
        if self.player.gold < cost:
            print(f"  They want {cost}g (you have {self.player.gold}).")
            return
        self.player.gold -= cost
        self.player.hp = self.player.max_hp
        self.player.mana = self.player.max_mana
        print(f"  {npc['name']} mends you. Fully restored. (-{cost}g)")

    def do_rest(self):
        room = self.floor["rooms"][self.current]
        if room["type"] != "camp":
            print("  You need a safe camp hollow to rest.")
            return
        if any(m["alive"] for m in room["monsters"]):
            print("  Too dangerous to rest.")
            return
        self.player.hp = self.player.max_hp
        self.player.mana = self.player.max_mana
        print("  You rest by the old fire. Fully restored.")

    # ---- free-form LLM narration -------------------------------------
    def freeform(self, line):
        room = self.floor["rooms"][self.current]
        npc = self.room_npc()
        room_desc = self.scene_text(room)
        looks_like_talk = line.startswith(("ask", "say", "speak", "talk", "tell", "hello", "hey", "who"))
        if npc and (looks_like_talk or self.rng.random() < 0.55):
            self.do_talk(line)
            return
        if any(v in line for v in ("examine", "inspect", "look at", "study", "read", "touch", "smell")):
            self.do_examine(line)
            return
        if self.llm.ready():
            text = self.llm.ambient(line, room_desc) or f"You {line}. The dark is unimpressed."
        else:
            text = f"You {line}. Nothing happens."
        print("  " + text)

    # ===================================================================
    # DEATH / VICTORY
    # ===================================================================
    def on_death(self, how, monster_name):
        m = self.meta
        m.deaths += 1
        m.total_essence += m.essence_run
        m.best_depth = max(m.best_depth, self.depth)
        m.save()
        print()
        print(ui.red(ui.hr()))
        if self.llm.ready():
            scene = self.llm.death_scene("you", how, self.depth, monster_name) \
                or f"You fall at depth {self.depth}. Your gear is lost to the dark."
        else:
            scene = f"You fall at depth {self.depth} to the {monster_name}. Your gear is lost."
        print(ui.red(scene))
        print(ui.red(ui.hr()))
        print(f"  Essence kept: +{m.essence_run}  (banked {m.essence})")
        print(f"  Spells kept:  {len(m.grimoire)}")
        print(ui.gray("  Equipment, gold, and consumables are lost to the Deep. Your knowledge is not."))
        print()

    def on_victory(self):
        m = self.meta
        m.essence += 100
        m.total_essence += m.essence_run + 100
        m.best_depth = max(m.best_depth, self.depth)
        m.save()
        print()
        print(ui.yellow(ui.hr()))
        if self.llm.ready():
            scene = self.llm.victory_scene("you", self.depth, "the Hollow King") \
                or "You conquer the Deep."
        else:
            scene = "You slay the Hollow King and conquer the Deep."
        print(ui.yellow(scene))
        print(ui.yellow(ui.hr()))
        print(f"  Victory! +100 bonus essence. Banked essence: {m.essence}.")
        print()


def main():
    no_llm = "--no-llm" in sys.argv
    verbose = "--verbose" in sys.argv
    seed = None
    for i, a in enumerate(sys.argv):
        if a == "--seed" and i + 1 < len(sys.argv):
            seed = int(sys.argv[i + 1])
    Game(no_llm=no_llm, verbose=verbose, seed=seed).play()


if __name__ == "__main__":
    main()
