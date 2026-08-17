// Display helpers: rarity colors, icon mapping, stat formatting.

export function rarityColor(r: string): string {
  switch (r) {
    case "Common":
      return "#9a9a9a";
    case "Uncommon":
      return "#5cb85c";
    case "Rare":
      return "#4a90d9";
    case "Epic":
      return "#b06ad0";
    case "Legendary":
      return "#e0912f";
    default:
      return "#9a9a9a";
  }
}

// Equipment slot -> icon file (weapon varies by name for flavor).
export function itemIcon(slot: string, name?: string): string {
  switch (slot) {
    case "weapon": {
      const n = (name || "").toLowerCase();
      if (n.includes("dagger")) return "dagger";
      if (n.includes("axe")) return "axe";
      if (n.includes("mace")) return "mace";
      if (n.includes("staff")) return "staff";
      return "sword";
    }
    case "armor":
      return "armor";
    case "helm":
      return "helm";
    case "boots":
      return "boots";
    case "trinket":
      return "trinket";
    case "consumable":
      return "potion";
    case "tome":
      return "tome";
    default:
      return "tome";
  }
}

// Monster display name -> icon file (names come from data.MONSTERS).
const MONSTER_ICONS: Record<string, string> = {
  "Giant Dungeon Rat": "dungeon_rat",
  "Cave Bat": "cave_bat",
  "Goblin Raider": "goblin",
  "Restless Skeleton": "skeleton",
  "Orc Brute": "orc",
  "Dark Mage": "dark_mage",
  "Wraith": "wraith",
  "Harpy": "harpy",
  "Troll": "troll",
  "Minotaur": "minotaur",
  "Lich": "lich",
  "Stone Golem": "stone_golem",
  "Bone Colossus": "bone_colossus",
  "Abyssal Horror": "abyssal_horror",
  "The Goblin King": "goblin_king",
  "Ogre Shaman": "ogre_shaman",
  "The Wraith Lord": "wraith_lord",
  "The Hollow King": "the_hollow_king",
};

export function monsterIcon(name: string): string {
  return MONSTER_ICONS[name] || "skeleton";
}

export function statLine(stats: Record<string, number> | undefined): string {
  if (!stats) return "";
  const parts: string[] = [];
  if (stats.atk) parts.push(`+${stats.atk} atk`);
  if (stats.defense) parts.push(`+${stats.defense} def`);
  if (stats.hp) parts.push(`+${stats.hp} hp`);
  if (stats.mana) parts.push(`+${stats.mana} mana`);
  if (stats.sp) parts.push(`+${stats.sp} sp`);
  return parts.join(", ");
}

export function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}
