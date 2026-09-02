"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { ClassRail } from "@/components/class-rail";
import { CastScore } from "@/components/cast-score";
import { CastStage } from "@/components/cast-stage";
import { EffectInspector } from "@/components/effect-inspector";
import { GrantedBy } from "@/components/granted-by";
import { SpriteIcon, TextureIcon } from "@/components/icon";
import { SoundPlayer, type PlayerHandle } from "@/components/sound-player";
import { SpellPalette, type TalentHit } from "@/components/spell-palette";
import { gameText } from "@/lib/game-text";
import { cn } from "@/lib/utils";
import {
  classBundle, effectsFile, resolveAsset, spell as fetchSpell, spellBundle,
  talentBundle, tree as fetchTree, viewerIndex,
} from "@/lib/api";
import type {
  ClassRef, Effects, RealmRef, SpellRecord, Talent, TreePayload, TreeRef, ViewerIndex,
} from "@/lib/types";

/** What the right-hand panel is showing: a talent in a tree, or a bare spell. */
type Subject =
  | { kind: "talent"; talent: Talent; tree: TreePayload; fx: Effects | null }
  | { kind: "spell"; record: SpellRecord }
  | null;

export default function Viewer() {
  const [index, setIndex] = useState<ViewerIndex | null>(null);
  const [realm, setRealm] = useState<RealmRef | null>(null);
  const [cls, setCls] = useState<ClassRef | null>(null);
  const [treeRef, setTreeRef] = useState<TreeRef | null>(null);
  const [payload, setPayload] = useState<TreePayload | null>(null);
  const [effects, setEffects] = useState<Map<number, Effects>>(new Map());
  const [subject, setSubject] = useState<Subject>(null);
  const [inspecting, setInspecting] = useState<string | null>(null);
  const [beat, setBeat] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const player = useRef<PlayerHandle>(null);

  useEffect(() => {
    viewerIndex().then((i) => {
      setIndex(i);
      const first = i.realms[0];
      setRealm(first);
      setCls(first.classes.find((c) => c.slug === "stormbringer") ?? first.classes[0]);
    }, () => {});
  }, []);

  // The class colour ships in the dataset and is the only saturated thing on screen.
  useEffect(() => {
    if (cls) document.documentElement.style.setProperty("--class", cls.color);
  }, [cls]);

  useEffect(() => {
    if (!cls) return;
    setTreeRef(cls.trees[0] ?? null);
    setSubject(null);
    setInspecting(null);
    if (!cls.effects_file) { setEffects(new Map()); return; }
    effectsFile(cls.effects_file).then(
      (file) => setEffects(new Map(file.spells.map((s) => [s.spell_id, s]))),
      () => setEffects(new Map()),
    );
  }, [cls]);

  useEffect(() => {
    if (!cls || !treeRef) return;
    fetchTree(cls.dir, treeRef.file).then(setPayload, () => setPayload(null));
  }, [cls, treeRef]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); setPaletteOpen(true); }
      if (e.key === "/" && !(e.target as HTMLElement)?.closest("input,textarea")) {
        e.preventDefault(); setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const pickTalent = useCallback((talent: Talent, from?: TreePayload) => {
    const source = from ?? payload;
    if (!source) return;
    const ids = [...new Set([talent.spell_id, ...talent.spell_ids].filter(Boolean))] as number[];
    const fx = ids.map((id) => effects.get(id)).find(Boolean) ?? null;
    setSubject({ kind: "talent", talent, tree: source, fx });
    setInspecting(null);
  }, [payload, effects]);

  const openSpell = useCallback(async (id: number) => {
    try {
      const record = await fetchSpell(id);
      setSubject({ kind: "spell", record });
      setInspecting(null);
    } catch { /* the spellbook may not be built */ }
  }, []);

  const jumpToTalent = useCallback(async (hit: TalentHit) => {
    if (!index) return;
    const nextRealm = index.realms.find((r) => r.slug === hit.realm);
    const nextClass = nextRealm?.classes.find((c) => c.slug === hit.cls);
    if (!nextRealm || !nextClass) return;
    setRealm(nextRealm);
    setCls(nextClass);
    const ref = nextClass.trees.find((t) => t.slug === hit.tree) ?? nextClass.trees[0];
    setTreeRef(ref);
    const loaded = await fetchTree(nextClass.dir, ref.file);
    setPayload(loaded);
    const talent = loaded.tree.talents.find((t) => t.id === hit.talentId);
    if (!talent) return;
    const file = nextClass.effects_file ? await effectsFile(nextClass.effects_file) : null;
    const map = new Map((file?.spells ?? []).map((s) => [s.spell_id, s]));
    setEffects(map);
    const ids = [...new Set([talent.spell_id, ...talent.spell_ids].filter(Boolean))] as number[];
    setSubject({
      kind: "talent", talent, tree: loaded,
      fx: ids.map((id) => map.get(id)).find(Boolean) ?? null,
    });
  }, [index]);

  const fx = subject?.kind === "talent" ? subject.fx
           : subject?.kind === "spell" ? subject.record.effects
           : null;
  const subjectName = subject?.kind === "talent" ? subject.talent.name
                    : subject?.kind === "spell" ? subject.record.name
                    : "";

  const totals = useMemo(() => ({
    classes: index?.realms.reduce((n, r) => n + r.classes.length, 0) ?? 0,
    talents: realm?.classes.reduce((n, c) => n + c.talent_count, 0) ?? 0,
  }), [index, realm]);

  if (!index || !realm || !cls) {
    return (
      <main className="grid min-h-screen place-items-center text-dim">
        <p className="font-mono text-sm">Reading the archive…</p>
      </main>
    );
  }

  return (
    <div className="[--masthead:79px]">
      <header className="flex flex-wrap items-center gap-8 border-b border-line bg-gradient-to-b from-panel to-ink px-6 py-4">
        <div className="min-w-0">
          <p className="display text-[19px] font-bold leading-tight">Conquest of Azeroth</p>
          <p className="eyebrow !text-[11px] !tracking-[0.13em]">talent and effect record</p>
        </div>

        <Button variant="outline" onClick={() => setPaletteOpen(true)}
                className="gap-2 border-line2 bg-sunk text-dim hover:text-foreground">
          <Search className="size-3.5" />
          Find a talent or spell
          <kbd className="ml-2 rounded-sm border border-line2 px-1.5 font-mono text-[10px]">⌘K</kbd>
        </Button>

        <select
          aria-label="Realm"
          value={realm.slug}
          onChange={(e) => {
            const next = index.realms.find((r) => r.slug === e.target.value)!;
            setRealm(next);
            setCls(next.classes.find((c) => c.slug === cls.slug) ?? next.classes[0]);
          }}
          className="rounded-sm border border-line2 bg-sunk px-2.5 py-1.5 text-[13px]"
        >
          {index.realms.map((r) => <option key={r.slug} value={r.slug}>{r.name}</option>)}
        </select>

        <dl className="ml-auto flex gap-6 border-l border-line pl-6">
          {[["Captured", index.captured?.slice(0, 10) ?? "—"],
            ["Classes", String(totals.classes)],
            ["Talents", totals.talents.toLocaleString()]].map(([term, value]) => (
            <div key={term} className="flex flex-col gap-0.5">
              <dt className="eyebrow">{term}</dt>
              <dd className="font-mono text-[13px]">{value}</dd>
            </div>
          ))}
        </dl>
      </header>

      <div className="grid items-start lg:grid-cols-[232px_minmax(0,1fr)_400px]">
        <ClassRail classes={realm.classes} current={cls.slug} onSelect={setCls} />

        <main className="min-w-0 px-7 pb-10 pt-6">
          <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-3 border-b border-line pb-4">
            <h1 className="display text-[34px] font-bold leading-none text-class">{cls.name}</h1>
            <dl className="flex flex-wrap gap-6">
              {[["Talents", cls.talent_count], ["Talent essence", cls.max_talent_essence],
                ["Ability essence", cls.max_ability_essence],
                ["Spells with effects", cls.effects_spell_count]].map(([term, value]) => (
                <div key={term} className="flex flex-col gap-0.5">
                  <dt className="eyebrow">{term}</dt>
                  <dd className="font-mono text-[14px]">{value}</dd>
                </div>
              ))}
            </dl>
            {cls.effects_file && (
              <Button asChild variant="outline" size="sm"
                      className="gap-2 border-line2 bg-sunk text-[11.5px] text-dim hover:border-class hover:text-foreground">
                <a href={classBundle(realm.slug, cls.slug)}>
                  <Download className="size-3.5" /> Every {cls.name} asset
                </a>
              </Button>
            )}
          </div>

          <nav aria-label="Talent trees" className="my-5 flex flex-wrap gap-0.5">
            {cls.trees.map((t) => (
              <button
                key={t.slug} type="button" role="tab"
                aria-selected={t.slug === treeRef?.slug}
                onClick={() => setTreeRef(t)}
                className={cn(
                  "flex items-baseline gap-2 border-b-2 px-3.5 pb-2 pt-1.5 text-[13.5px] transition-colors",
                  t.slug === treeRef?.slug
                    ? "border-class font-semibold text-foreground"
                    : "border-transparent text-dim hover:text-foreground",
                )}
              >
                {t.name}
                <span className="font-mono text-[11px] text-faint">{t.talent_count}</span>
                {t.is_shared && (
                  <Badge variant="outline" className="border-line2 text-[9px] uppercase tracking-wider text-faint">
                    shared
                  </Badge>
                )}
              </button>
            ))}
          </nav>

          {payload && (
            <TreeCanvasLoader
              payload={payload}
              sheet={index.sprite_sheet}
              selected={subject?.kind === "talent" ? subject.talent.id : null}
              onSelect={(t) => pickTalent(t)}
            />
          )}

          <p className="mt-5 flex flex-wrap gap-x-6 gap-y-1.5 border-t border-line pt-3.5 text-[11.5px] text-dim">
            {[["Talent", "rounded-full"], ["Ability", "rounded-sm"],
              ["Capstone", "[clip-path:polygon(50%_0,100%_25%,100%_75%,50%_100%,0_75%,0_25%)]"],
              ["Choice pair — pick one", "rounded-sm border-dashed"]].map(([text, shape]) => (
              <span key={text} className="inline-flex items-center gap-2">
                <i aria-hidden className={cn("inline-block size-2.5 border border-faint", shape)} />
                {text}
              </span>
            ))}
            <span className="inline-flex items-center gap-2">
              <i aria-hidden className="inline-block size-2.5 rounded-full bg-faint" />Passive
            </span>
          </p>

          {fx && (
            <section className="mt-7 border-t border-line pt-5">
              <h2 className="eyebrow mb-1">Cast score</h2>
              <p className="mb-3.5 max-w-[62ch] text-[12px] text-dim">
                Columns are moments in the cast, rows are where the effect attaches.
                Sounds play on the beat they fire.
              </p>
              <CastStage
                fx={fx}
                onBeat={setBeat}
                onSound={(file) => player.current?.playFile(file) ?? Promise.resolve(0)}
                soundDuration={() => player.current?.duration() ?? 0}
              />
              <CastScore
                fx={fx} beat={beat}
                onInspect={setInspecting}
                onPlaySound={(file) => void player.current?.playFile(file)}
              />
              {inspecting && (
                <EffectInspector path={inspecting} onClose={() => setInspecting(null)} />
              )}
            </section>
          )}
        </main>

        <ScrollArea className="h-[calc(100vh-var(--masthead))] border-l border-line bg-panel">
          <aside className="px-6 pb-10 pt-6">
            <Readout
              subject={subject}
              realm={realm.slug}
              cls={cls.slug}
              sheet={index.sprite_sheet}
              assetRoot={index.asset_root}
            />
          </aside>
        </ScrollArea>
      </div>

      <SoundPlayer ref={player} fx={fx} title={subjectName} assetRoot={index.asset_root} />

      <SpellPalette
        open={paletteOpen} onOpenChange={setPaletteOpen} index={index}
        onTalent={jumpToTalent} onSpell={openSpell}
      />
    </div>
  );
}

/* Split out so the tree only re-renders when its own inputs change. */
import { TreeCanvas } from "@/components/tree-canvas";
function TreeCanvasLoader(props: {
  payload: TreePayload; sheet: string | null; selected: number | null;
  onSelect: (t: Talent) => void;
}) {
  return (
    <TreeCanvas
      talents={props.payload.tree.talents}
      sheet={props.sheet}
      selected={props.selected}
      onSelect={props.onSelect}
    />
  );
}

function Readout({
  subject, realm, cls, sheet, assetRoot,
}: {
  subject: Subject; realm: string; cls: string; sheet: string | null; assetRoot: string;
}) {
  if (!subject) {
    return (
      <div className="text-dim">
        <p className="mb-1.5 text-[13px] font-semibold text-foreground">Pick a talent</p>
        <p className="max-w-[30ch] text-[13px]">
          Its description, cost and prerequisites appear here, with the models and
          sounds the client plays for it.
        </p>
      </div>
    );
  }

  const isTalent = subject.kind === "talent";
  const fx = isTalent ? subject.fx : subject.record.effects;
  const bundleHref = fx
    ? isTalent ? talentBundle(realm, cls, fx.spell_id) : spellBundle(subject.record.id)
    : null;

  return (
    <>
      <div className="grid grid-cols-[52px_minmax(0,1fr)] gap-3.5">
        {isTalent
          ? <SpriteIcon icon={subject.talent.icon} sheet={sheet} className="size-[52px] rounded-sm" />
          : <TextureIcon path={subject.record.icon} className="size-[52px] rounded-sm" />}
        <div>
          <h2 className="display text-[20px] font-bold leading-tight">
            {isTalent ? subject.talent.name : subject.record.name}
          </h2>
          <p className="mt-1 font-mono text-[11px] text-dim">
            {isTalent
              ? `${subject.talent.entry_type}${subject.talent.is_passive ? " · passive" : ""} · ${subject.tree.tree.name}`
              : [subject.record.rank, "from the client's spell table"].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>

      {!isTalent && (
        <section className="mt-6">
          <h3 className="eyebrow mb-2.5">Granted by</h3>
          <GrantedBy owners={subject.record.owners} />
        </section>
      )}

      <div className="mt-4 flex flex-wrap gap-1.5">
        {(isTalent
          ? ([
              subject.talent.spell_id && ["spell", subject.talent.spell_id, true],
              subject.talent.costs.talent_essence && ["TE", subject.talent.costs.talent_essence],
              subject.talent.costs.ability_essence && ["AE", subject.talent.costs.ability_essence],
              subject.talent.max_ranks > 1 && ["ranks", subject.talent.max_ranks],
              subject.talent.requirements.level && ["level", subject.talent.requirements.level],
            ] as const)
          : ([
              ["spell", subject.record.id, true],
              subject.record.visual_id && ["visual", subject.record.visual_id],
            ] as const)
        ).filter(Boolean).map((chip) => {
          const [term, value, accent] = chip as [string, number, boolean?];
          return (
            <Badge key={term} variant="outline"
                   className={cn("gap-1 rounded-sm font-mono text-[11px] font-normal",
                                 accent ? "border-[color-mix(in_srgb,var(--class)_40%,transparent)] text-foreground"
                                        : "border-line2 text-dim")}>
              {term} <strong className="font-medium text-foreground">{value}</strong>
            </Badge>
          );
        })}
      </div>

      {(isTalent ? subject.talent.description_html : subject.record.description) && (
        <section className="mt-6">
          <h3 className="eyebrow mb-2.5 flex items-center gap-2.5">
            Description <Separator className="flex-1" />
          </h3>
          {isTalent
            ? <div className="text-[13.5px] leading-relaxed [&_.item-number]:font-semibold [&_.item-number]:text-class"
                   dangerouslySetInnerHTML={{ __html: sanitize(subject.talent.description_html) }} />
            : <div className="text-[13.5px] leading-relaxed">{gameText(subject.record.description!)}</div>}
        </section>
      )}

      {fx && <FileList fx={fx} bundleHref={bundleHref} assetRoot={assetRoot} />}
    </>
  );
}

function FileList({ fx, bundleHref, assetRoot }: {
  fx: Effects; bundleHref: string | null; assetRoot: string;
}) {
  const paths = useMemo(() => {
    const list = [...fx.models, ...fx.sounds];
    if (fx.icon) list.push(fx.icon + ".blp");
    return list;
  }, [fx]);
  const [urls, setUrls] = useState<Map<string, string | null>>(new Map());

  useEffect(() => {
    let live = true;
    setUrls(new Map());
    Promise.all(paths.map(async (p) => [p, await resolveAsset(assetRoot, p)] as const))
      .then((pairs) => live && setUrls(new Map(pairs)));
    return () => { live = false; };
  }, [paths, assetRoot]);

  if (!paths.length) return null;

  return (
    <section className="mt-6">
      <h3 className="eyebrow mb-2.5 flex items-center gap-2.5">Files <Separator className="flex-1" /></h3>
      {bundleHref && (
        <div className="mb-3.5">
          <Button asChild
                  className="gap-2 border border-[color-mix(in_srgb,var(--class)_40%,transparent)] bg-[color-mix(in_srgb,var(--class)_9%,var(--sunk))] text-foreground hover:bg-[color-mix(in_srgb,var(--class)_18%,var(--sunk))]">
            <a href={bundleHref}><Download className="size-3.5 text-class" /> Download this spell&apos;s assets</a>
          </Button>
          <p className="mt-2 max-w-[38ch] text-[11.5px] leading-snug text-dim">
            Models with their .skin geometry and .blp textures, the sounds, and the icon.
          </p>
        </div>
      )}
      <ul className="grid gap-1">
        {paths.map((path) => {
          const url = urls.get(path);
          return (
            <li key={path}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-2.5 border-b border-line py-1 font-mono text-[11px] text-dim last:border-0">
              {url
                ? <a href={url} download className="break-all hover:text-foreground hover:underline">{path}</a>
                : <span className="break-all">{path}</span>}
              {url === undefined
                ? <span className="text-[9.5px] uppercase tracking-wider text-faint">checking</span>
                : url
                  ? <a href={url} download className="text-[9.5px] uppercase tracking-wider text-class hover:underline">download</a>
                  : <span className="text-[9.5px] uppercase tracking-wider text-faint">not extracted</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Upstream ships pre-rendered tooltip HTML. Render it, but only the inline formatting
 *  it actually uses — this is third-party markup going into innerHTML. */
function sanitize(html: string): string {
  if (typeof window === "undefined") return "";
  const doc = new DOMParser().parseFromString(html, "text/html");
  const allowed = new Set(["SPAN", "BR", "B", "I", "EM", "STRONG", "DIV", "P"]);
  for (const node of [...doc.body.querySelectorAll("*")]) {
    if (!allowed.has(node.tagName)) { node.replaceWith(...node.childNodes); continue; }
    for (const attr of [...node.attributes]) {
      if (attr.name === "class") continue;
      if (attr.name === "style") {
        node.setAttribute("style", attr.value.split(";")
          .map((d) => d.split(":"))
          .filter(([prop, val]) => prop && val
            && ["color", "display"].includes(prop.trim().toLowerCase())
            && /^[\w\s#(),.%-]+$/.test(val) && !/url|expression|image/i.test(val))
          .map(([prop, val]) => `${prop.trim()}:${val.trim()}`).join(";"));
        continue;
      }
      node.removeAttribute(attr.name);
    }
  }
  return doc.body.innerHTML;
}
