/** The shapes the Python service returns. Kept in one place so a change upstream
 *  surfaces as a type error rather than as an undefined at runtime. */

export type Sprite = {
  sheet_url: string;
  column: number;
  row: number;
  columns: number;
  rows: number;
};

export type Icon = {
  source_path: string;
  key: string;
  sprite: Sprite | null;
  file: string | null;
};

export type Talent = {
  id: number;
  name: string;
  slug: string;
  entry_type: "talent" | "ability";
  node_shape: "circle" | "square" | "hex";
  is_passive: boolean;
  max_ranks: number;
  position: { x: number; y: number };
  costs: { talent_essence: number; ability_essence: number };
  requirements: {
    tree_talent_essence: number;
    tree_ability_essence: number;
    level: number;
    talent_ids: number[];
  };
  spell_id: number | null;
  spell_ids: number[];
  description_html: string;
  description: string;
  ranks: { rank: number; description: string }[];
  connections: number[];
  choice_group: number | null;
  icon: Icon;
};

export type TreePayload = {
  tree: { id: number; name: string; slug: string; is_shared: boolean; talents: Talent[] };
};

export type TreeRef = {
  id: number;
  name: string;
  slug: string;
  file: string;
  talent_count: number;
  is_shared: boolean;
  sort_order: number;
};

export type ClassRef = {
  id: number;
  name: string;
  slug: string;
  color: string;
  talent_count: number;
  max_talent_essence: number;
  max_ability_essence: number;
  dir: string;
  trees: TreeRef[];
  effects_file: string | null;
  effects_spell_count: number;
};

export type RealmRef = { slug: string; name: string; id: number; classes: ClassRef[] };

export type ViewerIndex = {
  schema_version: number;
  sprite_sheet: string | null;
  asset_root: string;
  captured: string | null;
  realms: RealmRef[];
};

export type SoundRef = { id: number; name: string; files: string[] };

/** One moment of a cast: what it draws, where, and what it plays. */
export type Kit = {
  slot: string;
  kit_id: number;
  anim_id: number | null;
  models: Record<string, string>;
  sound: SoundRef | null;
};

export type Effects = {
  spell_id: number;
  name: string;
  rank: string | null;
  icon: string | null;
  visual_id: number;
  models: string[];
  sounds: string[];
  kits: Kit[];
  missile_model: string | null;
  missile_sound: SoundRef | null;
};

export type EffectsFile = {
  source_archives: Record<string, string>;
  spell_count: number;
  missing_spell_ids: number[];
  spells: Effects[];
};

/** Which class grants a spell, and as what. */
export type Owner = {
  name: string | null;
  class: string;
  tab: string | null;
  type: "Ability" | "Talent" | "TalentAbility" | "Trait" | string;
  level: number | null;
};

export type SpellRecord = {
  id: number;
  name: string;
  rank: string | null;
  description: string | null;
  icon: string | null;
  visual_id: number;
  owners: Owner[];
  effects: Effects | null;
};

export type SpellHit = {
  id: number;
  name: string;
  rank: string | null;
  icon: string | null;
  model_count: number;
  sound_count: number;
  owners: Owner[];
};

export type TextureRef = { path: string; available: boolean };

export type Emitter = { index: number; texture: number; blend: string; kind: string };

export type ModelInfo = {
  name: string;
  version: number;
  views: number;
  counts: Record<string, number>;
  textures: TextureRef[];
  blend_modes: string[];
  emitters: Emitter[];
  is_particle_only: boolean;
  glows: boolean | null;
  /** Every emitter, read far enough to run it. Empty when the file could not be read. */
  particles: ParticleEmitter[];
};

/** A key on a curve sampled across one particle's life, 0 at birth and 1 at death. */
export type Key<T> = [number, T];

/**
 * One emitter's full description. The motion fields are nullable because the reader
 * reports a track it could not resolve as null rather than substituting a default —
 * an invented gravity is indistinguishable from a real one once it is on screen.
 */
export type ParticleEmitter = {
  index: number;
  position: [number, number, number];
  bone: number;
  kind: string;
  blend: string;
  /** Already resolved to a fetchable path; null when the index names nothing. */
  texture: string | null;
  rows: number;
  cols: number;
  tiles: number;
  /** How many rotations the sheet declares; not a tile count. */
  tile_rotation: number;
  speed: number | null;
  speed_variation: number | null;
  vertical_range: number | null;
  horizontal_range: number | null;
  gravity: number | null;
  lifespan: number | null;
  lifespan_variation: number;
  emission_rate: number | null;
  emission_rate_variation: number;
  area_length: number | null;
  area_width: number | null;
  z_source: number | null;
  /** Colour channels arrive 0..255, not 0..1. */
  colors: Key<[number, number, number]>[];
  alphas: Key<number>[];
  scales: Key<[number, number]>[];
  /** Which cell of the sprite sheet to show, keyed across the particle's life. */
  head_cells: Key<number>[];
  resolved: boolean;
};

export type SearchIndex = {
  schema_version: number;
  fields: string[];
  /** [name, talentId, spellId, realm, class, tree] — arrays because there are 7,232. */
  rows: [string, number, number, string, string, string][];
};
