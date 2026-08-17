"""Static game content: spells, monsters, item templates, NPCs, lore.

This is the "content database." Procedural generation (gen.py) rolls from
these templates; the LLM adds narrative flavor on top at runtime.
"""

# ===========================================================================
# SPELLS
# ===========================================================================
# kind: damage | heal | buff | debuff | control | shield
#   power  -> base magnitude (dmg/heal/buff amount)
#   turns  -> duration for buff/debuff/control/shield
#   aoe    -> hits all enemies in combat (damage spells)
SPELLS = {
    # ---- Tier 1 ---------------------------------------------------------
    "fire_bolt": dict(name="Fire Bolt", element="Fire", tier=1, kind="damage",
                      cost=6, power=10,
                      desc="Hurl a compact bolt of flame at a single foe."),
    "healing_light": dict(name="Healing Light", element="Holy", tier=1, kind="heal",
                          cost=6, power=14,
                          desc="Warm light mends your wounds."),
    "ice_shard": dict(name="Ice Shard", element="Frost", tier=1, kind="damage",
                      cost=6, power=9,
                      desc="A jagged shard of ice strikes a single foe."),
    "arcane_shield": dict(name="Arcane Shield", element="Arcane", tier=1, kind="shield",
                          cost=8, power=12, turns=3,
                          desc="A ward of force absorbs damage for a few turns."),
    "power_word_stun": dict(name="Power Word: Stun", element="Arcane", tier=1, kind="control",
                            cost=10, turns=1,
                            desc="A psychic jolt stuns a foe, skipping its next turn."),
    # ---- Tier 2 ---------------------------------------------------------
    "fireball": dict(name="Fireball", element="Fire", tier=2, kind="damage", aoe=True,
                     cost=12, power=20,
                     desc="A roaring sphere of fire sears every foe in the room."),
    "frost_nova": dict(name="Frost Nova", element="Frost", tier=2, kind="debuff", aoe=True,
                       cost=14, power=8, turns=2,
                     desc="A ring of frost chills all foes, slowing and weakening them."),
    "natures_wroth": dict(name="Nature's Wrath", element="Nature", tier=2, kind="debuff",
                          cost=12, power=6, turns=3,
                          desc="Thorned vines poison a foe, bleeding it each turn."),
    "greater_heal": dict(name="Greater Heal", element="Holy", tier=2, kind="heal",
                         cost=14, power=26,
                         desc="Restorative power knits flesh and bone."),
    "lightning": dict(name="Lightning", element="Storm", tier=2, kind="damage",
                      cost=13, power=24,
                      desc="A fork of lightning crashes down on a single foe."),
    "stone_skin": dict(name="Stone Skin", element="Earth", tier=2, kind="buff",
                       cost=10, power=6, turns=4,
                       desc="Your skin hardens to granite, boosting defense."),
    # ---- Tier 3 ---------------------------------------------------------
    "meteor": dict(name="Meteor", element="Fire", tier=3, kind="damage", aoe=True,
                   cost=22, power=40,
                   desc="Call a burning rock from the sky onto every foe."),
    "chain_lightning": dict(name="Chain Lightning", element="Storm", tier=3, kind="damage", aoe=True,
                            cost=20, power=28,
                            desc="Lightning arcs from foe to foe."),
    "lifes_drain": dict(name="Lifes Drain", element="Shadow", tier=3, kind="damage",
                        cost=16, power=22, lifesteal=True,
                        desc="Drain a foe's vitality to heal yourself."),
    "berserk": dict(name="Berserk", element="Chaos", tier=3, kind="buff",
                    cost=16, power=10, turns=4,
                    desc="Rage floods you, greatly raising your attack."),
    "wall_of_stone": dict(name="Wall of Stone", element="Earth", tier=3, kind="shield",
                          cost=18, power=30, turns=4,
                          desc="A barrier of living rock soaks heavy damage."),
    # ---- Boss-exclusive -------------------------------------------------
    "void_collapse": dict(name="Void Collapse", element="Void", tier=4, kind="damage", aoe=True,
                          cost=30, power=60,
                          desc="Tear a wound in reality that consumes everything."),
    "suns_wrath": dict(name="Sun's Wrath", element="Holy", tier=4, kind="damage", aoe=True,
                       cost=28, power=50,
                       desc="Unsheathe the raw light of a dying star."),
}
SPEL_BY_ID = SPELLS  # alias

# Where spells can be found (tome chance weight, npc teach, boss drop)
SPELL_SOURCES = {
    "fire_bolt":      dict(tome=8,  boss=None),
    "ice_shard":      dict(tome=8,  boss=None),
    "healing_light":  dict(tome=8,  boss=None),
    "arcane_shield":  dict(tome=6,  boss=None),
    "power_word_stun":dict(tome=5,  boss=None),
    "fireball":       dict(tome=5,  boss="goblin_king"),
    "frost_nova":     dict(tome=4,  boss=None),
    "natures_wroth":  dict(tome=4,  boss=None),
    "greater_heal":   dict(tome=4,  boss=None),
    "lightning":      dict(tome=4,  boss="wraith_lord"),
    "stone_skin":     dict(tome=4,  boss=None),
    "meteor":         dict(tome=2,  boss="minotaur"),
    "chain_lightning":dict(tome=2,  boss=None),
    "lifes_drain":    dict(tome=2,  boss="wraith_lord"),
    "berserk":        dict(tome=2,  boss="ogre_shaman"),
    "wall_of_stone":  dict(tome=2,  boss=None),
    "void_collapse":  dict(tome=0,  boss="the_hollow_king"),
    "suns_wrath":     dict(tome=0,  boss="the_hollow_king"),
}

# ===========================================================================
# MONSTERS
# ===========================================================================
# tier drives depth scaling & essence reward. abilities: list of special moves.
MONSTERS = {
    # ---- tier 1 ---------------------------------------------------------
    "dungeon_rat": dict(name="Giant Dungeon Rat", tier=1, hp=16, atk=6, defense=1, speed=3,
                        desc="A bloated rat the size of a dog, teeth like needles.",
                        ability=None),
    "cave_bat": dict(name="Cave Bat", tier=1, hp=12, atk=5, defense=0, speed=5,
                     desc="A screeching bat with razor wings.", ability="swift"),
    "goblin": dict(name="Goblin Raider", tier=1, hp=22, atk=8, defense=2, speed=3,
                   desc="A snarling goblin with a chipped blade.", ability=None),
    "skeleton": dict(name="Restless Skeleton", tier=1, hp=20, atk=7, defense=3, speed=2,
                     desc="Bones rattle as it lunges, sword still gripped.", ability="bone_shards"),
    # ---- tier 2 ---------------------------------------------------------
    "orc": dict(name="Orc Brute", tier=2, hp=38, atk=12, defense=4, speed=2,
                desc="A hulking orc, scarred and thirsty for blood.", ability="heavy"),
    "dark_mage": dict(name="Dark Mage", tier=2, hp=30, atk=14, defense=2, speed=3,
                      desc="A robed figure crackling with sickly light.", ability="hex"),
    "wraith": dict(name="Wraith", tier=2, hp=34, atk=13, defense=5, speed=4,
                   desc="A cold presence that leaks shadow from its eyes.", ability="chill"),
    "harpy": dict(name="Harpy", tier=2, hp=28, atk=11, defense=2, speed=6,
                  desc="A bird-woman with a maniacal cackle.", ability="swift"),
    # ---- tier 3 ---------------------------------------------------------
    "troll": dict(name="Troll", tier=3, hp=70, atk=18, defense=6, speed=2,
                  desc="A mountain of green muscle and bad breath.", ability="regrow"),
    "minotaur": dict(name="Minotaur", tier=3, hp=78, atk=20, defense=7, speed=3,
                     desc="A bull-headed brute, horns curving like scythes.", ability="charge"),
    "lich": dict(name="Lich", tier=3, hp=60, atk=24, defense=6, speed=3,
                 desc="An undead wizard crowned in cracked bone.", ability="life_drain"),
    "stone_golem": dict(name="Stone Golem", tier=3, hp=90, atk=16, defense=12, speed=1,
                        desc="A walking boulder animated by ancient sigils.", ability=None),
    # ---- tier 4 ---------------------------------------------------------
    "bone_colossus": dict(name="Bone Colossus", tier=4, hp=125, atk=22, defense=11, speed=2,
                          desc="A cathedral of ribs and marrow, stitched up to walk again.", ability=None),
    "abyssal_horror": dict(name="Abyssal Horror", tier=4, hp=105, atk=27, defense=8, speed=4,
                           desc="Something that surfaced from below the dark, still dripping with it.", ability="hex"),
    # ---- bosses ---------------------------------------------------------
    "goblin_king": dict(name="The Goblin King", tier=2, hp=60, atk=14, defense=5, speed=3, boss=True,
                        desc="A goblin swollen with stolen gold and a stolen crown.",
                        ability="heavy"),
    "ogre_shaman": dict(name="Ogre Shaman", tier=3, hp=95, atk=18, defense=6, speed=2, boss=True,
                        desc="A totem-wielding ogre chanting in a dead tongue.",
                        ability="hex"),
    "wraith_lord": dict(name="The Wraith Lord", tier=3, hp=85, atk=26, defense=8, speed=4, boss=True,
                        desc="A tangle of cold and old hatred given a crown of mist.",
                        ability="chill"),
    "the_hollow_king": dict(name="The Hollow King", tier=4, hp=160, atk=30, defense=10, speed=3, boss=True,
                            desc="The first ruler of the deep, now a hollow thing wearing a crown of void.",
                            ability="void"),
}

# Which boss guards which floor (floors are 1-indexed; BOSS_EVERY=3)
FLOOR_BOSS = {
    3: "goblin_king",
    6: "ogre_shaman",
    9: "wraith_lord",
    10: "the_hollow_king",
}

# ===========================================================================
# ITEM TEMPLATES
# ===========================================================================
# slot: weapon | armor | helm | boots | trinket | consumable | tome | material
# base stats scale with rarity & depth at generation time.
WEAPON_BASES = {
    "dagger":  dict(name="Dagger",   dmg=(4, 6),  slot="weapon"),
    "sword":   dict(name="Shortsword", dmg=(7, 10), slot="weapon"),
    "longsword": dict(name="Longsword", dmg=(10, 14), slot="weapon"),
    "war_axe": dict(name="War Axe",  dmg=(11, 15), slot="weapon"),
    "mace":    dict(name="Mace",     dmg=(9, 13),  slot="weapon"),
    "staff":   dict(name="Staff",    dmg=(6, 9),   slot="weapon", sp=4),
}
ARMOR_BASES = {
    "leather": dict(name="Leather Armor",  slot="armor", defense=2, hp=6),
    "chain":   dict(name="Chainmail",      slot="armor", defense=4, hp=10),
    "plate":   dict(name="Plate Armor",    slot="armor", defense=6, hp=16),
    "robe":    dict(name="Arcane Robe",    slot="armor", defense=2, hp=4, mana=10, sp=3),
}
HELM_BASES = {
    "cap":   dict(name="Leather Cap", slot="helm", defense=1, hp=4),
    "helm":  dict(name="Iron Helm",   slot="helm", defense=2, hp=6),
    "crown": dict(name="Circlet",     slot="helm", defense=1, mana=6, sp=2),
}
BOOT_BASES = {
    "sandals": dict(name="Sandals", slot="boots", defense=1),
    "greaves": dict(name="Greaves", slot="boots", defense=2, hp=4),
}
TRINKET_BASES = {
    "ring_power":  dict(name="Ring of Power",  slot="trinket", atk=3),
    "ring_guard":  dict(name="Ring of Guard",  slot="trinket", defense=3, hp=4),
    "amulet_mana": dict(name="Amulet of the Deep", slot="trinket", mana=12, sp=3),
    "amulet_life": dict(name="Heart Amulet",   slot="trinket", hp=12),
    "fang":        dict(name="Talisman Fang",  slot="trinket", atk=4),
}
CONSUMABLES = {
    "health_potion": dict(name="Health Potion", slot="consumable", effect="heal_hp", power=25),
    "greater_health_potion": dict(name="Greater Health Potion", slot="consumable", effect="heal_hp", power=55),
    "mana_potion": dict(name="Mana Potion", slot="consumable", effect="heal_mana", power=25),
    "elixir": dict(name="Elixir of Vigor", slot="consumable", effect="buff_atk", power=6, turns=5),
    "antidote": dict(name="Antidote", slot="consumable", effect="cleanse"),
}
RARITIES = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
RARITY_MULT = {"Common": 1.0, "Uncommon": 1.3, "Rare": 1.7, "Epic": 2.2, "Legendary": 3.0}
RARITY_WEIGHTS = [46, 30, 15, 7, 2]   # relative weights for a random roll

# ===========================================================================
# NPC TEMPLATES
# ===========================================================================
NPCS = {
    "merchant": dict(
        name="Bramble the Merchant",
        persona="A wheezing gnome in a patched coat, more shrewd than you'd like. "
                "Haggles a little, knows the dungeon's old trades.",
        role="shop",
        sells=["consumable", "weapon", "armor", "trinket"],
        teaches=[]),
    "sage": dict(
        name="The Veiled Sage",
        persona="An ancient figure behind a grey veil. Speaks in riddles but is "
                "genuinely kind. Teaches spells to those who ask well.",
        role="sage",
        sells=[],
        teaches=["tier"]),  # teaches a random spell of a suitable tier
    "blacksmith": dict(
        name="Karr the Smith",
        persona="A broad-shouldered dwarf with a hammer older than the dungeon. "
                "Gruff, but will forge and mend for coin.",
        role="blacksmith",
        sells=["weapon", "armor", "helm", "boots"],
        teaches=[]),
    "wandering_soul": dict(
        name="A Wandering Soul",
        persona="The translucent ghost of someone who died here long ago. "
                "Lamenting, half-lucid, and full of fragments of the past.",
        role="lore",
        sells=[],
        teaches=[]),
    "hermit": dict(
        name="The Hermit",
        persona="A gaunt monk who has lived in the dark so long he's stopped "
                "blinking. Sells oddities and heals the curious.",
        role="healer",
        sells=["consumable"],
        heals=True),
}

# ===========================================================================
# LORE (codex fragments; LLM expands into entries)
# ===========================================================================
LORE = {
    "old_king": ("The Hollow King", "A tablet of black glass: 'We crowned him when "
               "the light died. Now he wears the dark like a second skin.'"),
    "dungeon_origin": ("The Deep", "Carved into a wall: 'Below the cellar, below the "
                    "cellar, the stairs go on. Do not count them.'"),
    "the_sage": ("The Veiled One", "A mural of a robed figure: 'She was the last to "
                "leave with her life. The veil is all that kept her from the void.'"),
    "rats": ("The Hunger Below", "Scratched into stone: 'The rats came first. Then the "
             "things that feed the rats.'"),
    "void": ("The Void", "A symbol that hurts to look at, ringed by the words: "
             "'It was here before the stone. It will be here after.'"),
    "minotaur": ("The Maze-Warden", "A horned skull on a pike, with: 'He guards the "
                "turning of the halls. Be blood, or be food.'"),
}

# Room atmosphere seeds (used with LLM to build room descriptions)
ROOM_FLAVOR = {
    "corridor": "a narrow stone corridor, dripping",
    "chamber": "a low stone chamber",
    "treasure": "a vaulted chamber thick with old gold and dust",
    "shrine": "a mossy shrine to a forgotten god",
    "boss": "a vast antechamber, the air heavy and wrong",
    "camp": "a dry hollow where a fire has burned before",
    "ruin": "a collapsed ruin, beams and rubble",
    "library": "a flooded archive of blackened tomes",
    "pit": "a railed edge over a lightless pit",
    "market": "a candlelit market of stalls and haggling voices",
    "forge": "a smith's forge, sparks drifting from a dying coals",
}
