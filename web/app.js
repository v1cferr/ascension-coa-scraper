/* Conquest of Azeroth — talent and effect record.
 *
 * Reads the JSON this repository produces: data/index.json for what exists, one file
 * per talent tree, and one resolved-effects file per class. No build step and no
 * dependencies, because the machine this runs on has no Node and because a viewer for
 * an archive should keep working long after its toolchain would have rotted.
 */

const ROOT = "../";
const DATA = ROOT + "data/";

/* Effect slots are moments in a cast. This is their order in time, which is what the
 * score is laid out along; anything the client emits outside this list is appended so
 * an unknown slot is shown rather than dropped. */
const MOMENTS = [
  "precast", "cast", "channel", "missile_targeting", "impact",
  "caster_impact", "target_impact", "instant_area", "impact_area",
  "persistent_area", "state", "state_done",
];

/* Attachment points, ordered head-down then outward, so a column reads like a body. */
const ATTACHMENTS = [
  "head", "chest", "base", "left_hand", "right_hand",
  "left_weapon", "right_weapon", "breath", "world",
  "special_0", "special_1", "special_2",
];

const CELL = 78;
const NODE = 54;

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

const state = {
  index: null,
  realm: null,
  cls: null,
  tree: null,
  trees: new Map(),      // tree slug -> payload
  effects: new Map(),    // spell id -> effect record
  search: null,          // lazily loaded
  audio: null,
};

/* Data ---------------------------------------------------------------------- */

const cache = new Map();
async function getJSON(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(DATA + path).then((r) => {
      if (!r.ok) throw new Error(`${path}: ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(path);
}

/** Whether a file was extracted. Cheap enough to ask the server directly, and always
 *  right, which a generated manifest would stop being the moment one is re-extracted. */
const probes = new Map();
function probe(url) {
  if (!probes.has(url)) {
    probes.set(url, fetch(url, { method: "HEAD" }).then((r) => r.ok).catch(() => false));
  }
  return probes.get(url);
}

const assetURL = (p) => DATA + state.index.asset_root + "/" + p.replace(/\\/g, "/");

/** The tables name some models .mdx for files stored as .m2; try both, as the client does. */
async function resolveAsset(path) {
  const direct = assetURL(path);
  if (await probe(direct)) return direct;

  const swapped = /\.mdx$/i.test(path) ? path.replace(/\.mdx$/i, ".m2")
                : /\.m2$/i.test(path)  ? path.replace(/\.m2$/i, ".mdx")
                : null;
  if (swapped && (await probe(assetURL(swapped)))) return assetURL(swapped);
  return null;
}

/* Icons --------------------------------------------------------------------- */

/* The dataset addresses icons as cells of one sheet. CSS percentage positioning puts
 * cell i at i/(N-1) of the way across, which is the inverse of how the site encodes it. */
function iconStyle(icon) {
  const s = icon && icon.sprite;
  if (!s || !state.index.sprite_sheet) return {};
  return {
    "--sheet": `url("${DATA}${state.index.sprite_sheet}")`,
    "--sheet-size": `${s.columns * 100}% ${s.rows * 100}%`,
    "--sheet-pos": `${(s.column / (s.columns - 1)) * 100}% ${(s.row / (s.rows - 1)) * 100}%`,
  };
}

const applyStyle = (node, vars) => {
  for (const [k, v] of Object.entries(vars)) node.style.setProperty(k, v);
};

/* Chrome -------------------------------------------------------------------- */

function renderRealms() {
  const sel = $("realm");
  sel.replaceChildren(...state.index.realms.map((r) => {
    const o = el("option", null, r.name);
    o.value = r.slug;
    return o;
  }));
  sel.value = state.realm.slug;
  sel.addEventListener("change", () => {
    state.realm = state.index.realms.find((r) => r.slug === sel.value);
    selectClass(state.realm.classes[0]);
    renderRoster();
  });
}

function renderRoster() {
  const list = $("roster");
  list.replaceChildren(...state.realm.classes.map((c) => {
    const li = el("li");
    const b = el("button", "roster-item");
    b.type = "button";
    b.style.setProperty("--swatch", c.color);
    b.setAttribute("aria-current", String(c.slug === state.cls?.slug));
    b.append(
      el("span", "roster-swatch"),
      el("span", "roster-name", c.name),
      el("span", "roster-count", c.talent_count),
    );
    b.addEventListener("click", () => selectClass(c));
    li.append(b);
    return li;
  }));
}

function renderClassHead() {
  const c = state.cls;
  document.documentElement.style.setProperty("--class", c.color);
  $("class-name").textContent = c.name;
  $("class-talents").textContent = c.talent_count;
  $("class-te").textContent = c.max_talent_essence;
  $("class-ae").textContent = c.max_ability_essence;
  $("class-fx").textContent = c.effects_spell_count || "0";

  const slot = $("class-download");
  slot.replaceChildren();
  if (c.effects_file) {
    const a = el("a", "bundle-button bundle-button-quiet");
    a.href = `${ROOT}_bundle/${state.realm.slug}/${c.slug}.zip`;
    a.append(el("span", "bundle-icon", "\u2193"),
             el("span", null, `Every ${c.name} asset`));
    a.title = "One zip: every model, texture, sound and icon this class references. "
            + "Tens of megabytes, and it takes a moment to build.";
    slot.append(a);
  }
}

function renderTreeTabs() {
  const nav = $("trees");
  nav.replaceChildren(...state.cls.trees.map((t) => {
    const b = el("button", "tree-tab");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", String(t.slug === state.tree?.slug));
    b.append(el("span", null, t.name), el("span", "n", t.talent_count));
    if (t.is_shared) b.append(el("span", "shared", "shared"));
    b.addEventListener("click", () => selectTree(t));
    return b;
  }));
}

/* Tree ---------------------------------------------------------------------- */

function renderTree(payload) {
  const talents = payload.tree.talents;
  const byId = new Map(talents.map((t) => [t.id, t]));

  const maxX = Math.max(...talents.map((t) => t.position.x));
  const maxY = Math.max(...talents.map((t) => t.position.y));
  const width = (maxX + 1) * CELL;
  const height = (maxY + 1) * CELL;

  const canvas = $("canvas");
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const centre = (t) => ({
    x: t.position.x * CELL + CELL / 2,
    y: t.position.y * CELL + CELL / 2,
  });

  const wires = $("wires");
  wires.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const lines = [];
  for (const t of talents) {
    for (const other of t.connections || []) {
      const target = byId.get(other);
      if (!target) continue;
      const a = centre(t);
      const b = centre(target);
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
      line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
      line.setAttribute("class", "wire");
      line.dataset.pair = `${t.id}:${target.id}`;
      lines.push(line);
    }
  }
  wires.replaceChildren(...lines);

  const nodes = $("nodes");
  nodes.style.height = `${height}px`;
  const buttons = talents.map((t, i) => {
    const b = el("button", "node");
    b.type = "button";
    b.dataset.id = t.id;
    b.dataset.shape = t.node_shape;
    b.dataset.passive = String(!!t.is_passive);
    b.setAttribute("aria-pressed", "false");
    b.setAttribute("aria-label",
      `${t.name}, ${t.entry_type}${t.is_passive ? ", passive" : ""}`);
    b.title = t.name;
    b.style.left = `${t.position.x * CELL + (CELL - NODE) / 2}px`;
    b.style.top = `${t.position.y * CELL + (CELL - NODE) / 2}px`;
    b.style.setProperty("--delay", `${Math.min(i * 8, 320)}ms`);

    const art = el("span", "node-art");
    applyStyle(art, iconStyle(t.icon));
    b.append(art);
    if (t.max_ranks > 1) b.append(el("span", "node-ranks", `×${t.max_ranks}`));

    b.addEventListener("click", () => selectTalent(t, payload));
    b.addEventListener("mouseenter", () => lightWires(t.id, true));
    b.addEventListener("mouseleave", () => lightWires(t.id, false));
    b.addEventListener("focus", () => lightWires(t.id, true));
    b.addEventListener("blur", () => lightWires(t.id, false));
    return b;
  });

  // A choice group is one decision, so its members are bracketed as one unit.
  const groups = new Map();
  for (const t of talents) {
    if (!t.choice_group) continue;
    if (!groups.has(t.choice_group)) groups.set(t.choice_group, []);
    groups.get(t.choice_group).push(t);
  }
  const braces = [...groups.values()].filter((g) => g.length > 1).map((g) => {
    const xs = g.map((t) => t.position.x * CELL + (CELL - NODE) / 2);
    const ys = g.map((t) => t.position.y * CELL + (CELL - NODE) / 2);
    const pad = 6;
    const d = el("div", "choice-brace");
    d.style.left = `${Math.min(...xs) - pad}px`;
    d.style.top = `${Math.min(...ys) - pad}px`;
    d.style.width = `${Math.max(...xs) - Math.min(...xs) + NODE + pad * 2}px`;
    d.style.height = `${Math.max(...ys) - Math.min(...ys) + NODE + pad * 2}px`;
    return d;
  });

  nodes.replaceChildren(...braces, ...buttons);
}

function lightWires(id, on) {
  for (const line of $("wires").querySelectorAll(".wire")) {
    const [a, b] = line.dataset.pair.split(":");
    if (a === String(id) || b === String(id)) line.classList.toggle("lit", on);
  }
}

/* Readout ------------------------------------------------------------------- */

function selectTalent(talent, payload) {
  for (const b of $("nodes").querySelectorAll(".node")) {
    b.setAttribute("aria-pressed", String(b.dataset.id === String(talent.id)));
  }
  renderReadout(talent, payload);
  writeHash(talent.id);
}

function renderReadout(talent, payload) {
  const out = $("readout");
  const frag = document.createDocumentFragment();

  const head = el("div", "talent-head");
  const icon = el("div", "talent-icon");
  applyStyle(icon, iconStyle(talent.icon));
  const titles = el("div");
  titles.append(el("h2", "talent-name", talent.name));
  titles.append(el("p", "talent-kind",
    `${talent.entry_type}${talent.is_passive ? " · passive" : ""} · ${payload.tree.name}`));
  head.append(icon, titles);
  frag.append(head);

  const chips = el("div", "chips");
  const chip = (label, value, accent) => {
    const c = el("span", accent ? "chip accent" : "chip");
    c.append(document.createTextNode(label + " "), el("strong", null, value));
    return c;
  };
  if (talent.spell_id) chips.append(chip("spell", talent.spell_id, true));
  if (talent.costs.talent_essence) chips.append(chip("TE", talent.costs.talent_essence));
  if (talent.costs.ability_essence) chips.append(chip("AE", talent.costs.ability_essence));
  if (talent.max_ranks > 1) chips.append(chip("ranks", talent.max_ranks));
  if (talent.requirements.tree_talent_essence) {
    chips.append(chip("needs TE in tree", talent.requirements.tree_talent_essence));
  }
  if (talent.requirements.level) chips.append(chip("level", talent.requirements.level));
  if (talent.choice_group) chips.append(chip("choice", "pick one"));
  frag.append(chips);

  if (talent.description_html) {
    const s = el("section", "section");
    s.append(el("h3", "section-title", "Description"));
    const d = el("div", "desc");
    d.innerHTML = sanitize(talent.description_html);
    s.append(d);
    frag.append(s);
  }

  if ((talent.ranks || []).length > 1) {
    const s = el("section", "section");
    s.append(el("h3", "section-title", "Ranks"));
    const ul = el("ul", "ranks");
    for (const r of talent.ranks) {
      const li = el("li", "rank");
      li.append(el("span", "rank-n", r.rank), el("span", "rank-text", r.description));
      ul.append(li);
    }
    s.append(ul);
    frag.append(s);
  }

  const ids = [...new Set([talent.spell_id, ...(talent.spell_ids || [])].filter(Boolean))];
  const fx = ids.map((id) => state.effects.get(id)).find(Boolean);

  if (fx) frag.append(fileList(fx, talent));
  out.replaceChildren(frag);
  out.scrollTop = 0;

  renderScoreBand(fx, talent);
}

/** The score is the widest thing a talent has to say, so it gets the stage rather than
 *  the side panel, where five moments would have to scroll through a 400px column. */
function renderScoreBand(fx, talent) {
  const band = $("score-band");
  const body = $("score-body");
  band.hidden = false;
  body.replaceChildren(renderEffects(fx, talent));
}

/** Upstream ships pre-rendered tooltip HTML. Render it, but only the inline formatting
 *  it actually uses -- this is third-party markup and it goes into innerHTML. */
function sanitize(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const allowed = new Set(["SPAN", "BR", "B", "I", "EM", "STRONG", "DIV", "P"]);
  for (const node of [...doc.body.querySelectorAll("*")]) {
    if (!allowed.has(node.tagName)) {
      node.replaceWith(...node.childNodes);
      continue;
    }
    for (const attr of [...node.attributes]) {
      if (attr.name === "class") continue;
      if (attr.name === "style") {
        node.setAttribute("style", safeStyle(attr.value));
        continue;
      }
      node.removeAttribute(attr.name);
    }
  }
  return doc.body.innerHTML;
}

/** Keep only the declarations upstream tooltips actually carry, with literal values.
 *  A charset test is not enough: url(...) and gradients survive one. */
const STYLE_PROPS = new Set(["color", "display"]);
function safeStyle(value) {
  return value.split(";")
    .map((d) => d.split(":"))
    .filter(([prop, val]) => prop && val
      && STYLE_PROPS.has(prop.trim().toLowerCase())
      && /^[\w\s#(),.%-]+$/.test(val) && !/url|expression|image/i.test(val))
    .map(([prop, val]) => `${prop.trim()}:${val.trim()}`)
    .join(";");
}

/* The cast score ------------------------------------------------------------ */

function renderEffects(fx, talent) {
  const out = document.createDocumentFragment();

  if (!fx || !fx.kits.length) {
    out.append(el("p", "note", talent.is_passive
      ? "Passive — the client plays no visual or sound for it."
      : "No visual or sound data for this spell in the client."));
    return out;
  }

  const slots = [
    ...MOMENTS.filter((m) => fx.kits.some((k) => k.slot === m)),
    ...fx.kits.map((k) => k.slot).filter((m) => !MOMENTS.includes(m)),
  ];
  const kitFor = (slot) => fx.kits.find((k) => k.slot === slot);

  const used = new Set(fx.kits.flatMap((k) => Object.keys(k.models)));
  const rows = [
    ...ATTACHMENTS.filter((a) => used.has(a)),
    ...[...used].filter((a) => !ATTACHMENTS.includes(a)),
  ];

  const grid = el("div", "score-grid");
  grid.style.gridTemplateColumns = `auto repeat(${slots.length}, minmax(104px, 1fr))`;

  grid.append(el("div", "score-cell rowhead score-moment", ""));
  for (const slot of slots) {
    grid.append(el("div", "score-cell score-moment", slot.replace(/_/g, " ")));
  }

  for (const attach of rows) {
    grid.append(el("div", "score-cell rowhead score-attach", attach.replace(/_/g, " ")));
    for (const slot of slots) {
      const model = kitFor(slot)?.models[attach];
      const cell = el("div", model ? "score-cell filled" : "score-cell");
      if (model) cell.append(modelChip(model));
      grid.append(cell);
    }
  }

  grid.append(el("div", "score-cell rowhead score-attach", "sound"));
  for (const slot of slots) {
    const sound = kitFor(slot)?.sound;
    const cell = el("div", sound ? "score-cell filled" : "score-cell");
    if (sound) cell.append(soundChip(sound));
    grid.append(cell);
  }

  const wrap = el("div", "score");
  wrap.append(grid);
  out.append(wrap);

  if (fx.missile_model) {
    const m = el("p", "score-missile");
    m.append(el("span", "score-missile-label", "missile "));
    m.append(modelChip(fx.missile_model));
    out.append(m);
  }
  return out;
}

function modelChip(path) {
  const n = el("div", "score-model");
  const file = path.split(/[\\/]/).pop();
  const dot = file.lastIndexOf(".");
  n.append(el("span", "stem", dot > 0 ? file.slice(0, dot) : file));
  if (dot > 0) n.append(el("span", "ext", file.slice(dot)));
  n.title = path;
  return n;
}

function soundChip(sound) {
  const wrap = el("div", "score-sound");
  const file = (sound.files[0] || "").split(/[\\/]/).pop();
  const btn = el("button", "play");
  btn.type = "button";
  btn.setAttribute("aria-label", `Play ${file}`);
  btn.innerHTML = '<svg viewBox="0 0 8 8" aria-hidden="true"><path d="M1 0l7 4-7 4z"/></svg>';
  btn.dataset.state = "idle";

  if (!sound.files.length) {
    btn.dataset.state = "missing";
    btn.disabled = true;
  } else {
    const url = assetURL(sound.files[0]);
    probe(url).then((ok) => {
      if (!ok) {
        btn.dataset.state = "missing";
        btn.disabled = true;
        btn.title = "Not extracted — run: ascension-coa client extract";
      }
    });
    btn.addEventListener("click", () => play(url, btn));
  }

  wrap.append(btn, el("span", "score-sound-name", file || "—"));
  return wrap;
}

function play(url, btn) {
  if (state.audio) {
    state.audio.pause();
    document.querySelectorAll('.play[data-state="playing"]')
      .forEach((b) => (b.dataset.state = "idle"));
  }
  const audio = new Audio(url);
  state.audio = audio;
  btn.dataset.state = "playing";
  audio.addEventListener("ended", () => (btn.dataset.state = "idle"));
  audio.addEventListener("error", () => (btn.dataset.state = "missing"));
  audio.play().catch(() => (btn.dataset.state = "missing"));
}

function fileList(fx, talent) {
  const s = el("section", "section");
  s.append(el("h3", "section-title", "Files"));

  const paths = [...(fx.models || []), ...(fx.sounds || [])];
  if (fx.icon) paths.push(fx.icon + ".blp");

  if (paths.length) {
    s.append(bundleLink(
      `${ROOT}_bundle/${state.realm.slug}/${state.cls.slug}/${fx.spell_id}.zip`,
      "Download this spell's assets",
      "Models with their .skin geometry and .blp textures, the sounds, and the icon.",
    ));
  }

  const ul = el("ul", "files");
  for (const p of paths) {
    const li = el("li", "file");
    const label = el("span", null, p);
    li.append(label);
    const badge = el("span", "file-state", "checking");
    badge.dataset.have = "false";
    li.append(badge);
    resolveAsset(p).then((url) => {
      badge.textContent = url ? "download" : "not extracted";
      badge.dataset.have = String(!!url);
      if (!url) return;
      // Only linked once it is known to be there, so a link never leads to a 404.
      const link = el("a", "file-link");
      link.href = url;
      link.download = p.split(/[\\/]/).pop();
      link.textContent = p;
      label.replaceWith(link);
      badge.replaceWith(withHref(badge, url, link.download));
    });
    ul.append(li);
  }
  if (!paths.length) ul.append(el("li", "file", "none"));
  s.append(ul);
  return s;
}

function withHref(badge, url, filename) {
  const a = el("a", "file-state", badge.textContent);
  a.dataset.have = badge.dataset.have;
  a.href = url;
  a.download = filename;
  return a;
}

/** A prominent download, with what it contains said plainly beneath it. */
function bundleLink(href, label, note) {
  const wrap = el("div", "bundle");
  const a = el("a", "bundle-button");
  a.href = href;
  a.append(el("span", "bundle-icon", "\u2193"), el("span", null, label));
  wrap.append(a);
  if (note) wrap.append(el("p", "bundle-note", note));
  return wrap;
}

/* Search -------------------------------------------------------------------- */

async function runSearch(query) {
  const box = $("results");
  const note = $("search-note");
  const list = $("results-list");
  const q = query.trim().toLowerCase();

  if (q.length < 2) { box.hidden = true; return; }
  box.hidden = false;

  if (!state.search) {
    note.textContent = "Loading the talent index…";
    list.replaceChildren();
    state.search = await getJSON("search.json");
  }

  const numeric = /^\d+$/.test(q);
  const hits = state.search.rows.filter(([name, , spell]) =>
    numeric ? String(spell).startsWith(q) : name.toLowerCase().includes(q)).slice(0, 60);

  note.textContent = hits.length
    ? `${hits.length}${hits.length === 60 ? "+" : ""} matches across both realms`
    : `Nothing matches “${query}”.`;

  list.replaceChildren(...hits.map(([name, talentId, spell, realm, cls, tree]) => {
    const entry = state.index.realms.find((r) => r.slug === realm)
      ?.classes.find((c) => c.slug === cls);
    const li = el("li");
    const b = el("button", "result");
    b.type = "button";
    const sw = el("span", "result-swatch");
    sw.style.background = entry?.color || "var(--faint)";
    b.append(
      sw,
      el("span", "result-name", name),
      el("span", "result-where", `${entry?.name || cls} · ${tree}`),
      el("span", "result-id", spell || "—"),
    );
    b.addEventListener("click", () => jumpTo(realm, cls, tree, talentId));
    li.append(b);
    return li;
  }));
}

async function jumpTo(realmSlug, clsSlug, treeSlug, talentId) {
  const realm = state.index.realms.find((r) => r.slug === realmSlug);
  const cls = realm.classes.find((c) => c.slug === clsSlug);
  if (realm !== state.realm) { state.realm = realm; $("realm").value = realm.slug; }
  await selectClass(cls, treeSlug);

  const node = $("nodes").querySelector(`.node[data-id="${talentId}"]`);
  if (node) {
    node.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    node.focus();
    node.click();
  }
  $("results").hidden = true;
  $("search").value = "";
}

/* Addresses ----------------------------------------------------------------- */

/* #realm/class/tree/talentId -- so a talent can be linked to, and so reloading keeps
 * your place. Written on selection, read on load and on back/forward. */
function writeHash(talentId) {
  const parts = [state.realm.slug, state.cls.slug, state.tree.slug];
  if (talentId) parts.push(talentId);
  const next = "#" + parts.join("/");
  if (location.hash !== next) history.replaceState(null, "", next);
}

function readHash() {
  const [realm, cls, tree, talent] = location.hash.replace(/^#/, "").split("/");
  return realm && cls ? { realm, cls, tree, talent: talent ? Number(talent) : null } : null;
}

async function applyHash() {
  const want = readHash();
  if (!want) return false;
  const realm = state.index.realms.find((r) => r.slug === want.realm);
  const cls = realm?.classes.find((c) => c.slug === want.cls);
  if (!cls) return false;
  state.realm = realm;
  $("realm").value = realm.slug;
  await selectClass(cls, want.tree);
  if (want.talent) {
    const node = $("nodes").querySelector(`.node[data-id="${want.talent}"]`);
    if (node) { node.click(); node.scrollIntoView({ block: "center", inline: "center" }); }
  }
  return true;
}

/* Wiring -------------------------------------------------------------------- */

async function selectTree(tree) {
  state.tree = tree;
  renderTreeTabs();
  if (!state.trees.has(tree.slug)) {
    state.trees.set(tree.slug, await getJSON(`${state.cls.dir}/${tree.file}`));
  }
  renderTree(state.trees.get(tree.slug));
  writeHash(null);
}

async function selectClass(cls, treeSlug) {
  state.cls = cls;
  state.trees = new Map();
  state.effects = new Map();
  renderClassHead();
  renderRoster();

  if (cls.effects_file) {
    const payload = await getJSON(cls.effects_file);
    state.effects = new Map(payload.spells.map((s) => [s.spell_id, s]));
  }
  const tree = cls.trees.find((t) => t.slug === treeSlug) || cls.trees[0];
  await selectTree(tree);
}

async function main() {
  state.index = await getJSON("index.json");
  state.realm = state.index.realms[0];

  const classes = state.index.realms.reduce((n, r) => n + r.classes.length, 0);
  const talents = state.realm.classes.reduce((n, c) => n + c.talent_count, 0);
  $("stat-classes").textContent = classes;
  $("stat-talents").textContent = talents.toLocaleString();
  $("captured").textContent = (state.index.captured || "").slice(0, 10) || "—";

  renderRealms();
  if (!(await applyHash())) {
    await selectClass(state.realm.classes.find((c) => c.slug === "stormbringer")
      || state.realm.classes[0]);
  }
  window.addEventListener("hashchange", applyHash);

  let timer;
  $("search").addEventListener("input", (e) => {
    clearTimeout(timer);
    const v = e.target.value;
    timer = setTimeout(() => runSearch(v), 140);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { $("results").hidden = true; }
    if (e.key === "/" && e.target !== $("search")) { e.preventDefault(); $("search").focus(); }
  });
}

main().catch((err) => {
  document.body.innerHTML =
    `<p style="padding:40px;font-family:monospace">Could not load the dataset: ${err.message}
     <br><br>Serve the repository root, then open /web/ :
     <br>python -m http.server 8000</p>`;
});
