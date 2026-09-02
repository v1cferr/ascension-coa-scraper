/**
 * The viewer's addresses.
 *
 * A talent, an effect within it, or a bare spell is a place, so it gets a URL you can
 * send rather than describe. Kept in the hash rather than the path because the whole
 * viewer is one page and the server has nothing to route on.
 *
 *   #<realm>/<class>/<tree>
 *   #<realm>/<class>/<tree>/<talentId>
 *   #<realm>/<class>/<tree>/<talentId>/<model path, encoded>
 *   #spell/<id>
 */

export type Address =
  | { kind: "tree"; realm: string; cls: string; tree: string; talent?: number; model?: string }
  | { kind: "spell"; id: number }
  | null;

export function read(hash: string): Address {
  const raw = hash.replace(/^#/, "");
  if (!raw) return null;

  const spell = raw.match(/^spell\/(\d+)$/);
  if (spell) return { kind: "spell", id: Number(spell[1]) };

  const [realm, cls, tree, talent, model] = raw.split("/");
  if (!realm || !cls || !tree) return null;
  return {
    kind: "tree",
    realm, cls, tree,
    talent: talent ? Number(talent) : undefined,
    // Asset paths contain slashes and backslashes, so the segment is encoded.
    model: model ? decodeURIComponent(model) : undefined,
  };
}

export function write(address: Address): string {
  if (!address) return "";
  if (address.kind === "spell") return `#spell/${address.id}`;
  const parts = [address.realm, address.cls, address.tree];
  if (address.talent) parts.push(String(address.talent));
  if (address.talent && address.model) parts.push(encodeURIComponent(address.model));
  return "#" + parts.join("/");
}

/** Replace rather than push: choosing a talent is not a navigation you want to have
 *  to press Back through twelve times. */
export function put(address: Address): void {
  const next = write(address);
  if (typeof window !== "undefined" && window.location.hash !== next) {
    window.history.replaceState(null, "", next || window.location.pathname);
  }
}
