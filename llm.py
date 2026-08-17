"""Client for the local llama.cpp `llama-server` (OpenAI-compatible REST).

Design notes
------------
* The loaded model (Qwen3.8-27B) is a *reasoning* model: it emits
  `reasoning_content` (its private thinking) before the real `content`.
  We only ever surface `content`.
* For short, high-frequency flavor (room scenes, item text, taunts) we
  append `/no_think` so the model answers directly instead of spending
  hundreds of tokens thinking. This keeps the game snappy.
* For the rare "big moment" (boss monologue, death scene) we allow a short
  stretch of thinking for quality.
* Every method degrades gracefully: on any error (server down, timeout,
  empty result) it returns `None` and the caller uses pre-written fallback
  text. The game is always playable with the LLM off.
"""
import json
import requests
import config

class LLM:
    def __init__(self, enabled=None, verbose=False):
        self.enabled = config.LLM_ENABLED if enabled is None else enabled
        self.verbose = verbose
        self._available = None  # lazily probed

    # -- low-level ---------------------------------------------------------
    def _url(self, path):
        return config.BASE_URL.rstrip("/") + path

    def probe(self):
        """Return True if the server answers /models."""
        try:
            r = requests.get(self._url("/models"), timeout=5)
            self._available = r.status_code == 200
        except Exception:
            self._available = False
        return self._available

    def ready(self):
        if self._available is None:
            self.probe()
        return self.enabled and self._available

    def _chat(self, system, user, max_tokens, temperature, think):
        if not self.enabled:
            return None
        if self._available is None:
            self.probe()
        if not self._available:
            return None

        if not think and config.NO_THINK:
            user = user.rstrip() + "\n/no_think"

        payload = {
            "model": config.MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            r = requests.post(self._url("/chat/completions"),
                              json=payload, timeout=config.REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            if self.verbose and content:
                print(f"[llm] {len(content)} chars, "
                      f"{data.get('usage', {}).get('completion_tokens', '?')} tok")
            return content or None
        except Exception as e:
            if self.verbose:
                print(f"[llm] error: {e}")
            return None

    # -- high-level prompts ------------------------------------------------
    def room_scene(self, room_desc, depth):
        """Paint an atmospheric scene for a room. 1-3 sentences."""
        system = ("You are the narrator of a dark-fantasy dungeon crawler. "
                  "Describe the scene in vivid, evocative prose. 1-3 sentences. "
                  "No lists. Do not mention the player by name. Do not end with "
                  "a question. Present tense.")
        user = (f"Depth {depth}. Room: {room_desc}. "
                f"Write the scene the player sees as they step in.")
        return self._chat(system, user, config.MAX_TOKENS_SHORT, config.TEMPERATURE, think=False)

    def item_flavor(self, item_name, rarity, item_type, stats):
        """Lore-flavored description for a notable item (Epic/Legendary)."""
        system = ("You write item lore for a dark-fantasy RPG. Give this item a "
                  "haunting one-sentence backstory or inscription. 1 sentence, "
                  "under 30 words. No quotes around it.")
        user = (f"Item: {item_name} ({rarity} {item_type}). Stats: {stats}. "
                f"Write its lore.")
        return self._chat(system, user, 60, 0.9, think=False)

    def monster_intro(self, monster_name, monster_desc, is_boss):
        """A taunt / first impression when a new monster (or boss) appears."""
        system = ("You are the narrator of a dark-fantasy dungeon crawler. "
                  + ("The player faces a BOSS. Write a dramatic 1-2 sentence "
                     "monologue or taunt in its voice, then one narrator line. "
                     if is_boss else
                     "Write a short 1-sentence narrator line as this creature "
                     "reveals itself. ")
                  + "Present tense, no lists.")
        user = f"{monster_name}: {monster_desc}"
        mtok = config.MAX_TOKENS_MED if is_boss else config.MAX_TOKENS_SHORT
        return self._chat(system, user, mtok, 0.9, think=False)

    def npc_reply(self, npc_name, npc_persona, player_says, context):
        """Free-form in-character NPC dialogue."""
        system = (f"You are {npc_name} in a dark-fantasy dungeon. "
                  f"Persona: {npc_persona}. Stay in character, reply in 1-3 "
                  f"sentences. You are a game NPC: you may offer clues, sell "
                  f"things, or teach the player, but you never control game "
                  f"state. If the player says something odd, respond "
                  f"colorfully in character.")
        user = f"Context: {context}\nThe player says: {player_says}"
        return self._chat(system, user, config.MAX_TOKENS_MED, 0.9, think=False)

    def examine(self, target_desc, room_desc):
        """Narrate the player closely examining an object/thing."""
        system = ("You are the narrator of a dark-fantasy dungeon crawler. "
                  "The player is examining something up close. Describe it in "
                  "2-3 vivid sentences, including one small detail that hints "
                  "at lore or a possible use. Present tense, no lists.")
        user = f"Room: {room_desc}\nExamining: {target_desc}"
        return self._chat(system, user, config.MAX_TOKENS_MED, 0.85, think=False)

    def ambient(self, player_action, room_desc):
        """Narrate a free-form player action that isn't a real command."""
        system = ("You are the narrator of a dark-fantasy dungeon crawler. The "
                  "player did something not covered by the game's commands. "
                  "Narrate the result or reaction in 1-2 sentences. Present "
                  "tense, no lists. Do not invent loot or game effects.")
        user = f"Room: {room_desc}\nThe player tries: {player_action}"
        return self._chat(system, user, config.MAX_TOKENS_SHORT, 0.9, think=False)

    def lore_entry(self, topic, seed_text):
        """Expand a fragment into a codex/lore entry."""
        system = ("You write lore codex entries for a dark-fantasy dungeon "
                  "crawle r. Turn the fragment into a 2-3 sentence codex "
                  "entry with an air of discovery. No lists, no heading.")
        user = f"Topic: {topic}\nFragment: {seed_text}"
        return self._chat(system, user, config.MAX_TOKENS_MED, 0.85, think=False)

    def death_scene(self, player_name, how_died, depth, monster_name):
        """A dramatic 2-4 sentence depiction of the player's death."""
        system = ("You are the narrator of a dark-fantasy dungeon crawler. "
                  "The player has just died. Write a grim, memorable 2-4 "
                  "sentence death scene. Present tense shifting to past. No "
                  "lists. End on a haunting note about their gear being lost "
                  "but their knowledge surviving.")
        user = (f"The player died at depth {depth} to {monster_name}. "
                f"How it happened: {how_died}")
        return self._chat(system, user, config.MAX_TOKENS_LONG, 0.9, think=False)

    def victory_scene(self, player_name, depth, boss_name):
        system = ("You are the narrator of a dark-fantasy dungeon crawler. "
                  "The player has conquered the dungeon. Write a triumphant "
                  "2-3 sentence victory scene. Present tense, no lists.")
        user = f"Depth {depth}. The final boss {boss_name} is slain."
        return self._chat(system, user, config.MAX_TOKENS_MED, 0.9, think=False)

    def shop_blurb(self, npc_name, persona, stock_names):
        system = ("You are a shopkeeper in a dark-fantasy dungeon. Greet the "
                  "player in 1-2 sentences in character and hint at your "
                  "wares. No lists.")
        user = (f"You are {npc_name}. Persona: {persona}. "
                f"For sale: {', '.join(stock_names)}. Greet the player.")
        return self._chat(system, user, config.MAX_TOKENS_SHORT, 0.9, think=False)


_shared = None
def get_llm(enabled=None, verbose=False):
    global _shared
    if _shared is None or _shared.verbose != verbose or (enabled is not None and _shared.enabled != enabled):
        _shared = LLM(enabled=enabled, verbose=verbose)
    return _shared
