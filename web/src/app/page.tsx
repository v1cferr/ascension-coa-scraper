"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, LayoutGrid, Network, Search, SquareStack } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CastScore } from "@/components/cast-score";
import { CastStage } from "@/components/cast-stage";
import { CompareBoard } from "@/components/compare-board";
import { EffectInspector } from "@/components/effect-inspector";
import { Navigator } from "@/components/navigator";
import { SoundPlayer, type PlayerHandle } from "@/components/sound-player";
import { SpellPalette, type TalentHit } from "@/components/spell-palette";
import { SubjectReader } from "@/components/subject-reader";
import { TreeCanvas } from "@/components/tree-canvas";
import * as address from "@/lib/address";
import { cn } from "@/lib/utils";
import {
  classBundle, effectsFile, spell as fetchSpell, tree as fetchTree, viewerIndex,
} from "@/lib/api";
import {
  effectsFor, subjectKey, subjectName, toPin, type Pin, type Subject,
} from "@/lib/subject";
import type {
  ClassRef, Effects, RealmRef, SpellHit, Talent, TreePayload, TreeRef, ViewerIndex,
} from "@/lib/types";

/** Three ways to look at the same archive, in one pane. */
type View = "subject" | "tree" | "compare";

const VIEWS: { id: View; label: string; icon: typeof Network }[] = [
  { id: "subject", label: "Subject", icon: SquareStack },
  { id: "tree", label: "Tree", icon: Network },
  { id: "compare", label: "Compare", icon: LayoutGrid },
];

export default function Viewer() {
  const [index, setIndex] = useState<ViewerIndex | null>(null);
  const [realm, setRealm] = useState<RealmRef | null>(null);
  const [cls, setCls] = useState<ClassRef | null>(null);
  const [treeRef, setTreeRef] = useState<TreeRef | null>(null);
  const [payload, setPayload] = useState<TreePayload | null>(null);
  const [effects, setEffects] = useState<Map<number, Effects>>(new Map());
  const [subject, setSubject] = useState<Subject | null>(null);
  const [pins, setPins] = useState<Pin[]>([]);
  const [view, setView] = useState<View>("subject");
  const [inspecting, setInspecting] = useState<string | null>(null);
  const [beat, setBeat] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const player = useRef<PlayerHandle>(null);
  const arrival = useRef<address.Address>(null);

  /* Loading ------------------------------------------------------------------ */

  const openSpell = useCallback(async (id: number) => {
    try {
      const record = await fetchSpell(id);
      setSubject({
        kind: "spell", id: record.id, name: record.name, rank: record.rank,
        description: record.description, icon: record.icon, owners: record.owners,
        fx: record.effects,
      });
      setInspecting(null);
      setView("subject");
    } catch { /* the spellbook may not have been built */ }
  }, []);

  useEffect(() => {
    viewerIndex().then((i) => {
      setIndex(i);
      const want = address.read(window.location.hash);
      arrival.current = want;

      if (want?.kind === "spell") {
        setRealm(i.realms[0]);
        setCls(i.realms[0].classes[0]);
        void openSpell(want.id);
        return;
      }
      const r = (want && i.realms.find((x) => x.slug === want.realm)) ?? i.realms[0];
      setRealm(r);
      setCls(
        (want && r.classes.find((c) => c.slug === want.cls))
        ?? r.classes.find((c) => c.slug === "stormbringer") ?? r.classes[0],
      );
    }, () => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The class colour ships in the dataset and is the only saturated thing on screen.
  useEffect(() => {
    if (cls) document.documentElement.style.setProperty("--class", cls.color);
  }, [cls]);

  useEffect(() => {
    if (!cls) return;
    const want = arrival.current?.kind === "tree" ? arrival.current : null;
    setTreeRef(cls.trees.find((t) => t.slug === want?.tree) ?? cls.trees[0] ?? null);
    setInspecting(null);
    if (!cls.effects_file) { setEffects(new Map()); return; }
    effectsFile(cls.effects_file).then(
      (file) => setEffects(new Map(file.spells.map((s) => [s.spell_id, s]))),
      () => setEffects(new Map()),
    );
  }, [cls]);

  useEffect(() => {
    if (!cls || !treeRef) return;
    fetchTree(cls.dir, treeRef.file).then((loaded) => {
      setPayload(loaded);

      // Only the address the page opened with is honoured, once. Afterwards the URL
      // follows the reader rather than steering them.
      const want = arrival.current;
      if (want?.kind !== "tree" || !want.talent) return;
      arrival.current = null;
      const talent = loaded.tree.talents.find((t) => t.id === want.talent);
      if (!talent) return;
      setSubject({ kind: "talent", talent, tree: loaded, cls, fx: effectsFor(talent, effects) });
      if (want.model) setInspecting(want.model);
    }, () => setPayload(null));
  }, [cls, treeRef, effects]);

  useEffect(() => {
    if (!realm || !cls) return;
    if (subject?.kind === "spell") address.put({ kind: "spell", id: subject.id });
    else if (treeRef) {
      address.put({
        kind: "tree", realm: realm.slug, cls: cls.slug, tree: treeRef.slug,
        talent: subject?.kind === "talent" ? subject.talent.id : undefined,
        model: inspecting ?? undefined,
      });
    }
  }, [realm, cls, treeRef, subject, inspecting]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === "k" && (e.metaKey || e.ctrlKey))
          || (e.key === "/" && !(e.target as HTMLElement)?.closest("input,textarea"))) {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  /* Choosing ----------------------------------------------------------------- */

  const pickTalent = useCallback((talent: Talent, from?: TreePayload, into?: ClassRef) => {
    const tree = from ?? payload;
    const owner = into ?? cls;
    if (!tree || !owner) return;
    setSubject({ kind: "talent", talent, tree, cls: owner, fx: effectsFor(talent, effects) });
    setInspecting(null);
    setView("subject");
  }, [payload, cls, effects]);

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
    setSubject({ kind: "talent", talent, tree: loaded, cls: nextClass, fx: effectsFor(talent, map) });
    setView("subject");
  }, [index]);

  /* Pinning ------------------------------------------------------------------ */

  const pin = useCallback((next: Pin) => {
    setPins((current) =>
      current.some((p) => p.key === next.key)
        ? current.filter((p) => p.key !== next.key)     // pinning again unpins
        : [...current, next]);
  }, []);

  const pinFromNavigator = useCallback(
    async (what: { kind: "talent"; talent: Talent } | { kind: "spell"; hit: SpellHit }) => {
      if (!payload || !cls) return;
      if (what.kind === "talent") {
        pin(toPin(
          { kind: "talent", talent: what.talent, tree: payload, cls, fx: effectsFor(what.talent, effects) },
          cls.color,
        ));
        return;
      }
      // A spell row carries no effects yet; fetch before pinning so the card is complete.
      try {
        const record = await fetchSpell(what.hit.id);
        pin(toPin({
          kind: "spell", id: record.id, name: record.name, rank: record.rank,
          description: record.description, icon: record.icon, owners: record.owners,
          fx: record.effects,
        }, cls.color));
      } catch { /* nothing to pin */ }
    }, [payload, cls, effects, pin]);

  /* Derived ------------------------------------------------------------------ */

  const fx = subject?.fx ?? null;
  const pinnedKeys = useMemo(() => new Set(pins.map((p) => p.key)), [pins]);
  const currentKey = subject ? subjectKey(subject) : null;
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
    <div className="flex h-dvh flex-col overflow-hidden">
      <header className="flex h-[65px] shrink-0 items-center gap-6 border-b border-line bg-panel px-5">
        <div className="min-w-0">
          <p className="display text-[15px] font-bold leading-none">Conquest of Azeroth</p>
          <p className="eyebrow !text-[9.5px]">talent and effect record</p>
        </div>

        <Button
          variant="outline" onClick={() => setPaletteOpen(true)}
          className="h-8 gap-2 border-line2 bg-sunk text-[12.5px] text-dim hover:text-foreground"
        >
          <Search className="size-3.5" />
          Find anything
          <kbd className="ml-1 rounded-sm border border-line2 px-1 font-mono text-[10px]">⌘K</kbd>
        </Button>

        <select
          aria-label="Realm" value={realm.slug}
          onChange={(e) => {
            const next = index.realms.find((r) => r.slug === e.target.value)!;
            setRealm(next);
            setCls(next.classes.find((c) => c.slug === cls.slug) ?? next.classes[0]);
            setSubject(null);
          }}
          className="h-8 rounded-sm border border-line2 bg-sunk px-2 text-[12.5px]"
        >
          {index.realms.map((r) => <option key={r.slug} value={r.slug}>{r.name}</option>)}
        </select>

        <dl className="ml-auto hidden gap-5 lg:flex">
          {[["Captured", index.captured?.slice(0, 10) ?? "—"],
            ["Classes", String(totals.classes)],
            ["Talents", totals.talents.toLocaleString()]].map(([term, value]) => (
            <div key={term} className="flex flex-col gap-0.5">
              <dt className="eyebrow !text-[9px]">{term}</dt>
              <dd className="font-mono text-[12px]">{value}</dd>
            </div>
          ))}
        </dl>
      </header>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Navigator
          realm={realm} cls={cls} treeRef={treeRef} payload={payload}
          selectedKey={currentKey} pinnedKeys={pinnedKeys}
          onPickClass={(next) => { setCls(next); setSubject(null); }}
          onPickTree={(next) => { setTreeRef(next); setView("tree"); }}
          onPickTalent={(talent) => pickTalent(talent)}
          onPickSpell={openSpell}
          onPin={pinFromNavigator}
        />

        <ScrollArea className="h-full min-h-0">
          <main className="min-w-0 px-6 pb-12 pt-5">
            <nav aria-label="View" className="mb-5 inline-flex rounded-sm border border-line2 bg-sunk p-0.5">
              {VIEWS.map(({ id, label, icon: Glyph }) => (
                <button
                  key={id} type="button" role="tab" aria-selected={view === id}
                  onClick={() => setView(id)}
                  className={cn(
                    "flex items-center gap-2 rounded-[3px] px-3 py-1.5 text-[12.5px] transition-colors",
                    view === id
                      ? "bg-[color-mix(in_srgb,var(--class)_16%,transparent)] font-medium text-foreground"
                      : "text-dim hover:text-foreground",
                  )}
                >
                  <Glyph className={cn("size-3.5", view === id && "text-class")} />
                  {label}
                  {id === "compare" && pins.length > 0 && (
                    <span className="rounded-sm bg-class px-1 font-mono text-[9.5px] text-ink">
                      {pins.length}
                    </span>
                  )}
                </button>
              ))}
            </nav>

            {view === "subject" && (
              <>
                <SubjectReader
                  subject={subject} realm={realm.slug} sheet={index.sprite_sheet}
                  assetRoot={index.asset_root}
                  pinned={!!currentKey && pinnedKeys.has(currentKey)}
                  onPin={() => subject && pin(toPin(subject, cls.color))}
                />
                {fx && (
                  <section className="mt-8 border-t border-line pt-5">
                    <h2 className="eyebrow mb-1">Cast score</h2>
                    <p className="mb-3.5 max-w-[62ch] text-[12px] text-dim">
                      Columns are moments in the cast, rows are where the effect attaches.
                      Sounds play on the beat they fire.
                    </p>
                    <CastStage
                      fx={fx} onBeat={setBeat}
                      onSound={(file) => player.current?.playFile(file) ?? Promise.resolve(0)}
                      soundDuration={() => player.current?.duration() ?? 0}
                    />
                    <CastScore
                      fx={fx} beat={beat} onInspect={setInspecting}
                      onPlaySound={(file) => void player.current?.playFile(file)}
                    />
                    {inspecting && (
                      <EffectInspector path={inspecting} onClose={() => setInspecting(null)} />
                    )}
                  </section>
                )}
              </>
            )}

            {view === "tree" && payload && (
              <>
                <div className="mb-4 flex flex-wrap items-baseline justify-between gap-4">
                  <div>
                    <h1 className="display text-[26px] font-bold leading-none text-class">{cls.name}</h1>
                    <p className="mt-1.5 font-mono text-[11px] text-dim">
                      {treeRef?.name} · {treeRef?.talent_count} talents
                      {treeRef?.is_shared && " · shared"}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-5">
                    {[["Talent essence", cls.max_talent_essence],
                      ["Ability essence", cls.max_ability_essence],
                      ["Spells with effects", cls.effects_spell_count]].map(([term, value]) => (
                      <div key={term} className="flex flex-col gap-0.5">
                        <dt className="eyebrow !text-[9px]">{term}</dt>
                        <dd className="font-mono text-[13px]">{value}</dd>
                      </div>
                    ))}
                    {cls.effects_file && (
                      <Button asChild variant="outline" size="sm"
                        className="gap-2 border-line2 bg-sunk text-[11.5px] text-dim hover:border-class hover:text-foreground">
                        <a href={classBundle(realm.slug, cls.slug)}>
                          <Download className="size-3.5" /> Every {cls.name} asset
                        </a>
                      </Button>
                    )}
                  </div>
                </div>

                <TreeCanvas
                  talents={payload.tree.talents} sheet={index.sprite_sheet}
                  selected={subject?.kind === "talent" ? subject.talent.id : null}
                  onSelect={(t) => pickTalent(t)}
                />

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
              </>
            )}

            {view === "compare" && (
              <CompareBoard
                pins={pins} sheet={index.sprite_sheet}
                onRemove={(key) => setPins((c) => c.filter((p) => p.key !== key))}
                onClear={() => setPins([])}
                onPlaySound={(file) => void player.current?.playFile(file)}
              />
            )}
          </main>
        </ScrollArea>
      </div>

      <SoundPlayer ref={player} fx={fx} title={subjectName(subject)} assetRoot={index.asset_root} />

      <SpellPalette
        open={paletteOpen} onOpenChange={setPaletteOpen} index={index}
        onTalent={jumpToTalent} onSpell={openSpell}
      />
    </div>
  );
}
