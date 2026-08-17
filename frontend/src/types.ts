export interface SaveSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  essence: number;
  runs: number;
  deaths: number;
  best_depth: number;
  spells: number;
  lore: number;
}

export interface Upgrade {
  stat: string;
  level: number;
  cost: number;
}

export interface GrimoireSpell {
  id: string;
  name: string;
  element: string;
  tier: number;
  attuned: number;
  cost: number;
  power: number;
  desc: string;
  attune_cost: number;
  attune_max: boolean;
}

export interface CodexEntry {
  key: string;
  title: string;
  text: string;
}

export interface Meta {
  essence: number;
  runs: number;
  deaths: number;
  best_depth: number;
  total_essence: number;
  upgrades: Upgrade[];
  grimoire: GrimoireSpell[];
  codex: CodexEntry[];
}

export interface Door {
  n: number;
  type: string;
  label: string;
  discovered: boolean;
}

export interface RoomMonster {
  name: string;
  is_boss: boolean;
}

export interface RoomNpc {
  name: string;
  role: string;
}

export interface Room {
  depth: number;
  type: string;
  label: string;
  scene: string;
  monsters: RoomMonster[];
  npcs: RoomNpc[];
  item_count: number;
  tome_count: number;
  has_lore: boolean;
  doors: Door[];
  is_exit: boolean;
  has_stairs: boolean;
}

export interface MapRoom {
  id: string;
  type: string;
  label: string;
  cleared: boolean;
  is_current: boolean;
  is_exit: boolean;
  is_boss: boolean;
  connections: string[];
}

export interface FloorMap {
  depth: number;
  start: string;
  current: string;
  rooms: MapRoom[];
}

export interface EquipItem {
  name: string;
  rarity: string;
  stats: Record<string, number>;
}

export interface InvItem {
  n: number;
  name: string;
  rarity: string;
  slot: string;
  stats?: Record<string, number>;
  effect?: string;
  power?: number | string;
}

export interface Spell {
  id: string;
  name: string;
  element: string;
  tier: number;
  cost: number;
  power: number;
  attuned: number;
  desc: string;
  aoe: boolean;
  kind: string;
}

export interface Status {
  kind: string;
  turns: number;
  power: number;
}

export interface Player {
  hp: number;
  max_hp: number;
  mana: number;
  max_mana: number;
  atk: number;
  def: number;
  sp: number;
  gold: number;
  essence_run: number;
  shield: number;
  equipment: Record<string, EquipItem | null>;
  inventory: InvItem[];
  status: Status[];
  spells: Spell[];
}

export interface CombatMonster {
  n: number;
  name: string;
  hp: number;
  max_hp: number;
  is_boss: boolean;
  status: string[];
}

export interface Combat {
  turn: number;
  defending: boolean;
  monsters: CombatMonster[];
}

export interface FeedItem {
  kind: string;
  text: string;
}

export type Screen = "hub" | "explore" | "combat" | "dead" | "victory";

export interface Snapshot {
  screen: Screen;
  meta: Meta;
  feed: FeedItem[];
  ended: string | null;
  llm: boolean;
  room?: Room;
  player?: Player;
  combat?: Combat | null;
  map?: FloorMap;
}

export interface Action {
  type: string;
  n?: number;
  spell?: string;
  stat?: string;
  arg?: string;
  slot?: string;
  text?: string;
}
