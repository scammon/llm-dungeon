"""Procedural generation: dungeon floors, items, monsters, tomes.

Pure functions + a per-run RNG. No LLM here; the LLM narrates what these
functions produce. Everything is deterministic given the seed.
"""
import random
import data
import config

_uid = 0
def next_id(prefix="o"):
    global _uid
    _uid += 1
    return f"{prefix}{_uid}"

def depth_tier(depth):
    """Map a floor depth to a monster/item tier (1..4)."""
    return min(4, (depth - 1) // 3 + 1)

def depth_scale(depth):
    """Stat scaling multiplier as you go deeper."""
    return 1.0 + (depth - 1) * 0.14

# ===========================================================================
# ITEMS
# ===========================================================================
def _scale(val, rarity, depth):
    return round(val * data.RARITY_MULT[rarity] * depth_scale(depth))

def roll_rarity(rng):
    total = sum(data.RARITY_WEIGHTS)
    r = rng.randint(1, total)
    for name, w in zip(data.RARITIES, data.RARITY_WEIGHTS):
        if r <= w:
            return name
        r -= w
    return "Common"

def _make_equipment(rng, slot, depth, rarity=None):
    rarity = rarity or roll_rarity(rng)
    if slot == "weapon":
        base = random.choice(list(data.WEAPON_BASES.values())) if rng is None else rng.choice(list(data.WEAPON_BASES.values()))
        lo, hi = base["dmg"]
        atk = _scale((lo + hi) // 2, rarity, depth)
        stats = {"atk": atk, "dmg": (atk - 2, atk + 2)}
        if base.get("sp"):
            stats["sp"] = _scale(base["sp"], rarity, depth)
        name = base["name"]
    elif slot == "armor":
        base = rng.choice(list(data.ARMOR_BASES.values()))
        stats = {"defense": _scale(base["defense"], rarity, depth), "hp": _scale(base.get("hp", 0), rarity, depth)}
        if base.get("mana"):
            stats["mana"] = _scale(base["mana"], rarity, depth)
        if base.get("sp"):
            stats["sp"] = _scale(base["sp"], rarity, depth)
        name = base["name"]
    elif slot == "helm":
        base = rng.choice(list(data.HELM_BASES.values()))
        stats = {"defense": _scale(base.get("defense", 0), rarity, depth), "hp": _scale(base.get("hp", 0), rarity, depth)}
        if base.get("mana"):
            stats["mana"] = _scale(base["mana"], rarity, depth)
        if base.get("sp"):
            stats["sp"] = _scale(base["sp"], rarity, depth)
        name = base["name"]
    elif slot == "boots":
        base = rng.choice(list(data.BOOT_BASES.values()))
        stats = {"defense": _scale(base.get("defense", 0), rarity, depth)}
        if base.get("hp"):
            stats["hp"] = _scale(base["hp"], rarity, depth)
        name = base["name"]
    elif slot == "trinket":
        base = rng.choice(list(data.TRINKET_BASES.values()))
        stats = {}
        for k in ("atk", "defense", "hp", "mana", "sp"):
            if base.get(k):
                stats[k] = _scale(base[k], rarity, depth)
        name = base["name"]
    else:
        return None

    # epic/legendary get an LLM flavor at runtime; mark them
    return dict(id=next_id("it"), name=name, slot=slot, rarity=rarity,
                stats=stats, value=10 + sum(v for v in stats.values() if isinstance(v, int)) * 2,
                flavor=None)

def make_consumable(rng, key=None, depth=1):
    key = key or rng.choice(list(data.CONSUMABLES.keys()))
    base = data.CONSUMABLES[key]
    item = dict(id=next_id("it"), name=base["name"], slot="consumable",
                rarity="Common", effect=base["effect"],
                power=round(base.get("power", 0) * depth_scale(depth)),
                turns=base.get("turns"), value=8, flavor=None)
    return item

def make_tome(rng, spell_id, depth):
    sp = data.SPELLS[spell_id]
    return dict(id=next_id("it"), name=f"Tome of {sp['name']}", slot="tome",
                rarity=["Common", "Rare", "Epic"][min(2, sp["tier"] - 1)],
                spell_id=spell_id, value=20 + sp["tier"] * 15, flavor=None)

def roll_item(rng, depth, slot=None, rarity=None):
    """Roll a random equipment item (or a specific slot)."""
    if slot is None:
        slot = rng.choice(["weapon", "weapon", "armor", "armor", "helm", "boots", "trinket"])
    return _make_equipment(rng, slot, depth, rarity)

def roll_loot(rng, depth, count=2):
    items = []
    for _ in range(count):
        r = rng.random()
        if r < 0.55:
            items.append(roll_item(rng, depth))
        elif r < 0.8:
            items.append(make_consumable(rng, depth=depth))
        else:
            items.append(make_tome(rng, pick_spell_for_depth(rng, depth), depth))
    return items

def pick_spell_for_depth(rng, depth, tier=None):
    tier = tier or depth_tier(depth)
    pool = [sid for sid, s in data.SPELLS.items()
            if s["tier"] <= tier and data.SPELL_SOURCES[sid]["tome"] > 0]
    # bias toward the current tier
    weighted = []
    for sid in pool:
        s = data.SPELLS[sid]
        w = 3 if s["tier"] == tier else 1
        weighted += [sid] * w
    return rng.choice(weighted) if weighted else "fire_bolt"

# ===========================================================================
# MONSTERS
# ===========================================================================
def make_monster(rng, template_id, depth, scale=1.0):
    base = data.MONSTERS[template_id]
    tier = base["tier"]
    s = depth_scale(depth) * scale
    hp = round(base["hp"] * s)
    m = dict(
        id=next_id("mo"), template_id=template_id, name=base["name"],
        hp=hp, max_hp=hp,
        atk=round(base["atk"] * s),
        defense=round(base["defense"] * s),
        speed=base["speed"], tier=tier,
        is_boss=bool(base.get("boss")),
        ability=base.get("ability"), desc=base["desc"],
        essence=config.ESSENCE_PER_TIER.get(tier, 5) * (config.BOSS_ESSENCE_MULT if base.get("boss") else 1),
        gold=rng.randint(4, 10) + tier * rng.randint(3, 8),
        alive=True,
    )
    return m

def roll_monsters(rng, depth, count=None):
    tier = depth_tier(depth)
    pool = [mid for mid, m in data.MONSTERS.items() if m["tier"] == tier and not m.get("boss")]
    if not pool:  # fall back to the nearest lower tier that has regulars
        for t in range(tier - 1, 0, -1):
            pool = [mid for mid, m in data.MONSTERS.items() if m["tier"] == t and not m.get("boss")]
            if pool:
                break
    count = count or rng.randint(1, 3)
    monsters = []
    for _ in range(count):
        monsters.append(make_monster(rng, rng.choice(pool), depth))
    return monsters

def roll_boss(rng, depth):
    bid = data.FLOOR_BOSS.get(depth)
    if not bid:
        return None
    return make_monster(rng, bid, depth, scale=1.0)

# ===========================================================================
# FLOOR / ROOMS
# ===========================================================================
def _bfs_farthest(adj, start):
    dist = {start: 0}
    from collections import deque
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj.get(u, []):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return max(dist, key=dist.get) if dist else start

def make_floor(rng, depth):
    """Build a connected graph of rooms for one floor."""
    n_rooms = rng.randint(5, 8)
    is_boss_floor = depth in data.FLOOR_BOSS
    rooms = {}
    ids = list(range(n_rooms))
    rng.shuffle(ids)
    adj = {i: [] for i in ids}

    # random spanning tree: connect each node to an earlier one
    for i in ids[1:]:
        j = rng.choice(ids[:ids.index(i)])
        adj[i].append(j)
        adj[j].append(i)
    # add 1-2 loop edges for variety
    for _ in range(rng.randint(1, 2)):
        a, b = rng.sample(ids, 2)
        if b not in adj[a]:
            adj[a].append(b)
            adj[b].append(a)

    # assign room types
    start = ids[0]
    exit_room = _bfs_farthest(adj, start)
    if is_boss_floor:
        # boss room = the exit room (must beat boss to descend)
        boss_room = exit_room
    else:
        boss_room = None

    type_pool = ["chamber", "corridor", "corridor", "ruin", "chamber", "pit"]
    for i in ids:
        if i == start:
            rtype = "camp"
        elif i == boss_room:
            rtype = "boss"
        elif i == exit_room and not is_boss_floor:
            rtype = "chamber"
        else:
            rtype = rng.choice(type_pool)
        rooms[i] = dict(
            id=i, type=rtype, connections=sorted(adj[i]),
            monsters=[], items=[], npcs=[], tomes=[], lore=[],
            cleared=False, discovered=(i == start), scene=None,
        )

    # sprinkle special rooms
    non_special = [i for i in ids if i not in (start, boss_room)]
    if non_special:
        rooms[rng.choice(non_special)]["type"] = "treasure"
        normal = lambda: [x for x in non_special
                          if rooms[x]["type"] in ("chamber", "corridor", "ruin", "pit")]
        # a shop on most floors (buy / sell)
        if rng.random() < 0.75:
            cand = normal()
            if len(cand) > 2:
                rooms[rng.choice(cand)]["type"] = "market"
        # one more themed room: sage / healer / smith
        if rng.random() < 0.6:
            cand = normal()
            if len(cand) > 2:
                rooms[rng.choice(cand)]["type"] = rng.choice(["library", "shrine", "forge"])
    # a camp/rest room sometimes
    if non_special and rng.random() < 0.5:
        cand = [x for x in non_special if rooms[x]["type"] in ("chamber", "corridor")]
        if cand:
            rooms[rng.choice(cand)]["type"] = "camp"

    # populate contents
    for i, room in rooms.items():
        rtype = room["type"]
        if rtype == "camp":
            room["monsters"] = []
            if rng.random() < 0.7:
                room["items"].append(make_consumable(rng, depth=depth))
            if rng.random() < 0.4:
                room["npcs"].append(make_npc(rng, "wandering_soul", depth))
        elif rtype == "boss" and is_boss_floor:
            boss = roll_boss(rng, depth)
            if boss:
                room["monsters"].append(boss)
            room["items"] = roll_loot(rng, depth, count=3)
            if depth == config.MAX_FLOORS:
                room["lore"].append("void")
        elif rtype == "treasure":
            room["items"] = roll_loot(rng, depth, count=rng.randint(2, 4))
            room["tomes"].append(make_tome(rng, pick_spell_for_depth(rng, depth, tier=depth_tier(depth)), depth))
            if rng.random() < 0.5:
                room["lore"].append(rng.choice(list(data.LORE.keys())))
        elif rtype == "market":
            room["npcs"].append(make_npc(rng, "merchant", depth))
            if rng.random() < 0.5:
                room["items"].append(roll_loot(rng, depth, count=1)[0])
        elif rtype == "forge":
            room["npcs"].append(make_npc(rng, "blacksmith", depth))
        elif rtype == "library":
            for _ in range(rng.randint(2, 3)):
                room["tomes"].append(make_tome(rng, pick_spell_for_depth(rng, depth), depth))
            room["lore"].append(rng.choice(list(data.LORE.keys())))
            if rng.random() < 0.7:
                room["npcs"].append(make_npc(rng, "sage", depth))
        elif rtype == "shrine":
            if rng.random() < 0.6:
                room["npcs"].append(make_npc(rng, "hermit", depth))
            room["lore"].append(rng.choice(list(data.LORE.keys())))
        else:
            # normal room: monsters, maybe a find
            if rtype != "start":
                room["monsters"] = roll_monsters(rng, depth)
            if rng.random() < 0.4:
                room["items"].append(roll_loot(rng, depth, count=1)[0])

    # start room is safe & discovered
    rooms[start]["monsters"] = []
    rooms[start]["discovered"] = True

    return dict(
        depth=depth, rooms=rooms, start=start,
        exit_room=exit_room, boss_room=boss_room,
        is_boss_floor=is_boss_floor,
    )

# ===========================================================================
# NPCs
# ===========================================================================
def make_npc(rng, template_id, depth):
    base = data.NPCS[template_id]
    npc = dict(id=next_id("np"), template_id=template_id, name=base["name"],
               persona=base["persona"], role=base["role"], alive=True,
               stock=[], taught_spell=None, greeted=False)
    if base["role"] == "shop":
        n = rng.randint(3, 5)
        for _ in range(n):
            r = rng.random()
            if "consumable" in base["sells"] and r < 0.5:
                npc["stock"].append(make_consumable(rng, depth=depth))
            else:
                slot = rng.choice([s for s in base["sells"] if s != "consumable"]) or "weapon"
                it = roll_item(rng, depth, slot=slot)
                if it:
                    npc["stock"].append(it)
    return npc
