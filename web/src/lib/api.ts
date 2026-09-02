import type {
  Effects, EffectsFile, ModelInfo, SearchIndex, SpellHit, SpellRecord,
  TreePayload, ViewerIndex,
} from "./types";

/** Everything the browser reads comes from the Python service, through the rewrites
 *  in next.config.ts, so these are all same-origin. */

const cache = new Map<string, Promise<unknown>>();

async function get<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    cache.set(path, fetch(path).then((r) => {
      if (!r.ok) throw new Error(`${path}: ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(path) as Promise<T>;
}

export const viewerIndex = () => get<ViewerIndex>("/data/index.json");
export const searchIndex = () => get<SearchIndex>("/data/search.json");
export const tree = (dir: string, file: string) => get<TreePayload>(`/data/${dir}/${file}`);
export const effectsFile = (file: string) => get<EffectsFile>(`/data/${file}`);
export const spell = (id: number) => get<SpellRecord>(`/_spell/${id}`);

export const modelInfo = (path: string) =>
  get<ModelInfo>(`/_model/${encodeURI(path.replace(/\\/g, "/"))}`);

/** Search is not cached: the query changes every keystroke. */
export async function searchSpells(query: string, limit = 40): Promise<SpellHit[]> {
  const r = await fetch(`/_spells?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!r.ok) return [];
  return (await r.json()).results as SpellHit[];
}

/* Asset addresses -------------------------------------------------------------- */

export const assetUrl = (root: string, path: string) =>
  `/data/${root}/${path.replace(/\\/g, "/")}`;

export const textureUrl = (path: string) =>
  `/_texture/${encodeURI(path.replace(/\\/g, "/"))}`;

/** A spell's icon comes from Spell.dbc as a texture path without its extension. */
export const iconUrl = (icon: string | null) =>
  icon ? `${textureUrl(icon)}.blp` : null;

export const spellBundle = (id: number) => `/_bundle/spell/${id}.zip`;
export const talentBundle = (realm: string, cls: string, spellId: number) =>
  `/_bundle/${realm}/${cls}/${spellId}.zip`;
export const classBundle = (realm: string, cls: string) => `/_bundle/${realm}/${cls}.zip`;

/** Whether a file made it out of the archives. Cheap enough to ask the server, and
 *  always right, which a generated manifest would stop being. */
const probes = new Map<string, Promise<boolean>>();
export function probe(url: string): Promise<boolean> {
  if (!probes.has(url)) {
    probes.set(url, fetch(url, { method: "HEAD" }).then((r) => r.ok).catch(() => false));
  }
  return probes.get(url)!;
}

/** The tables name some models .mdx for files stored as .m2; try both, as the client
 *  does, and report which one actually exists. */
export async function resolveAsset(root: string, path: string): Promise<string | null> {
  const direct = assetUrl(root, path);
  if (await probe(direct)) return direct;
  const swapped = /\.mdx$/i.test(path)
    ? path.replace(/\.mdx$/i, ".m2")
    : /\.m2$/i.test(path)
      ? path.replace(/\.m2$/i, ".mdx")
      : null;
  if (swapped) {
    const alt = assetUrl(root, swapped);
    if (await probe(alt)) return alt;
  }
  return null;
}

/* Ordering ---------------------------------------------------------------------- */

/** Effect slots are moments in a cast. This is their order in time. */
export const MOMENTS = [
  "precast", "cast", "channel", "missile_targeting", "impact",
  "caster_impact", "target_impact", "instant_area", "impact_area",
  "persistent_area", "state", "state_done",
] as const;

/** Attachment points, head down then outward, so a column reads like a body. */
export const ATTACHMENTS = [
  "head", "chest", "base", "left_hand", "right_hand",
  "left_weapon", "right_weapon", "breath", "world",
  "special_0", "special_1", "special_2",
] as const;

export const orderedSlots = (fx: Effects) => [
  ...MOMENTS.filter((m) => fx.kits.some((k) => k.slot === m)),
  ...fx.kits.map((k) => k.slot).filter((s) => !MOMENTS.includes(s as never)),
];

export const orderedAttachments = (fx: Effects) => {
  const used = new Set(fx.kits.flatMap((k) => Object.keys(k.models)));
  return [
    ...ATTACHMENTS.filter((a) => used.has(a)),
    ...[...used].filter((a) => !ATTACHMENTS.includes(a as never)),
  ];
};

export const label = (slot: string) => slot.replace(/_/g, " ");
export const fileName = (path: string) => path.split(/[\\/]/).pop() ?? path;
