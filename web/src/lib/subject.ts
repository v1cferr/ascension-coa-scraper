import type { ClassRef, Effects, Icon, Owner, Talent, TreePayload } from "./types";

/**
 * What the reader is reading.
 *
 * Two shapes arrive here from different places — a talent, which lives in a tree, and a
 * spell, which the client's own table knows about and no tree may name. The reader,
 * the score, the player and the board all take the same thing, so the difference is
 * flattened once, here, rather than in every component.
 */
export type Subject =
  | { kind: "talent"; talent: Talent; tree: TreePayload; cls: ClassRef; fx: Effects | null }
  | {
      kind: "spell";
      id: number;
      name: string;
      rank: string | null;
      description: string | null;
      icon: string | null;
      owners: Owner[];
      fx: Effects | null;
    };

/**
 * A subject pinned to the compare board.
 *
 * Deliberately a snapshot, not a reference. A card keeps the accent, the icon and the
 * effects it was pinned with, so putting a Stormbringer talent next to a Pyromancer one
 * shows blue against orange — which is the whole point of the board. Holding a
 * reference would repaint every card to whichever class happened to be open.
 */
export type Pin = {
  key: string;
  name: string;
  spellId: number | null;
  accent: string;
  owners: Owner[];
  meta: string;
  icon: { kind: "sprite"; icon: Icon } | { kind: "texture"; path: string | null };
  fx: Effects | null;
};

export const subjectKey = (subject: Subject): string =>
  subject.kind === "talent"
    ? `talent:${subject.cls.slug}:${subject.talent.id}`
    : `spell:${subject.id}`;

export const subjectName = (subject: Subject | null): string =>
  subject ? (subject.kind === "talent" ? subject.talent.name : subject.name) : "";

export const subjectEffects = (subject: Subject | null): Effects | null =>
  subject?.fx ?? null;

/** Resolve which of a talent's spell ids actually has effects. */
export function effectsFor(talent: Talent, effects: Map<number, Effects>): Effects | null {
  const ids = [...new Set([talent.spell_id, ...talent.spell_ids].filter(Boolean))] as number[];
  return ids.map((id) => effects.get(id)).find(Boolean) ?? null;
}

export function toPin(subject: Subject, fallbackAccent: string): Pin {
  if (subject.kind === "talent") {
    return {
      key: subjectKey(subject),
      name: subject.talent.name,
      spellId: subject.talent.spell_id,
      accent: subject.cls.color,
      owners: [],
      meta: `${subject.cls.name} · ${subject.tree.tree.name}`,
      icon: { kind: "sprite", icon: subject.talent.icon },
      fx: subject.fx,
    };
  }
  return {
    key: subjectKey(subject),
    name: subject.name,
    spellId: subject.id,
    accent: fallbackAccent,
    owners: subject.owners,
    meta: subject.rank ?? "from the client's spell table",
    icon: { kind: "texture", path: subject.icon },
    fx: subject.fx,
  };
}
