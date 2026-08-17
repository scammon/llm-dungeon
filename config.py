"""Central configuration for the LLM dungeon crawler.

Everything that might need to change (server address, model, tuning knobs)
lives here. Override any of these with environment variables.
"""
import os

# --- llama.cpp server -------------------------------------------------------
BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
MODEL = os.environ.get("LLM_MODEL", "Qwen3.8-27B-UD-Q4_K_XL.gguf")

# Disable the model's internal "thinking" for snappy flavor text. The Qwen3
# family is a reasoning model that emits `reasoning_content` before `content`;
# appending /no_think makes it answer directly and fast (~37 tok/s on this box).
NO_THINK = os.environ.get("LLM_NOTHINK", "1") == "1"

# LLM request tuning
MAX_TOKENS_SHORT = 140    # item flavor, room description, taunts
MAX_TOKENS_MED = 320      # NPC dialogue, examinations, lore
MAX_TOKENS_LONG = 520     # boss monologues, death scenes
TEMPERATURE = float(os.environ.get("LLM_TEMP", "0.8"))
REQUEST_TIMEOUT = 180     # seconds; a 27B model can be slow under load

# Toggle the LLM entirely (deterministic-only play). `--no-llm` also does this.
LLM_ENABLED = os.environ.get("LLM_ENABLED", "1") == "1"

# --- roguelite tuning -------------------------------------------------------
MAX_FLOORS = 10                 # descend this far to win the run
BOSS_EVERY = 3                  # a boss guards every Nth floor
STARTING_HP = 40
STARTING_MANA = 30
STARTING_ATK = 8
STARTING_DEF = 3
STARTING_SPELL_POWER = 5
MANA_REGEN_PER_TURN = 3
CRIT_CHANCE = 0.10
CRIT_MULT = 2.0

# Essence: the persistent currency. Earned from kills (more from bosses),
# spent in the hub between runs on permanent upgrades.
ESSENCE_PER_TIER = {1: 3, 2: 6, 3: 10, 4: 16}
BOSS_ESSENCE_MULT = 4

# Hub upgrade costs (in essence), scaling +50% per purchase of the same upgrade.
UPGRADE_BASE_COST = {
    "hp": 10,      # +6 max hp
    "mana": 10,    # +6 max mana
    "atk": 12,     # +2 atk
    "defense": 12,     # +1 def
    "sp_power": 12,  # +2 spell power
    "attune": 8,    # +1 attunement to a chosen spell (better per-spell)
}
HP_STEP = 6
MANA_STEP = 6
ATK_STEP = 2
DEF_STEP = 1
SP_POWER_STEP = 2
ATTUNE_MAX = 5

# Grimoire: how many spells you can keep (cast) at once. Starts small; spend
# a lot of essence at the camp to bind more spell slots.
START_GRIMOIRE_SLOTS = 4
GRIMOIRE_BASE_COST = 40   # essence for the first extra slot (4 -> 5)
GRIMOIRE_MAX = 8          # hard cap on spell slots

SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "save.json")
