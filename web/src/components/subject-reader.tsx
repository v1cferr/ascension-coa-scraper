"use client";

import { useCallback, useMemo } from "react";
import { Download, Pin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { GrantedBy } from "@/components/granted-by";
import { SpriteIcon, TextureIcon } from "@/components/icon";
import { gameText } from "@/lib/game-text";
import { cn } from "@/lib/utils";
import { resolveAsset, spellBundle, talentBundle } from "@/lib/api";
import { useLoaded } from "@/lib/use-loaded";
import type { Effects } from "@/lib/types";
import type { Subject } from "@/lib/subject";

/** Everything about one subject, in one column, in the order you want it: what it is,
 *  who grants it, what it does, and the files behind it. */
export function SubjectReader({
  subject, realm, sheet, assetRoot, pinned, onPin,
}: {
  subject: Subject | null;
  realm: string;
  sheet: string | null;
  assetRoot: string;
  pinned: boolean;
  onPin: () => void;
}) {
  if (!subject) {
    return (
      <div className="text-dim">
        <p className="mb-1.5 text-[13px] font-semibold text-foreground">Pick a talent or a spell</p>
        <p className="max-w-[46ch] text-[13px] leading-relaxed">
          Choose one from the navigator. Its description, cost and prerequisites appear
          here, with the models and sounds the client plays for it — and you can pin it
          to the compare board.
        </p>
      </div>
    );
  }

  const isTalent = subject.kind === "talent";
  const fx = subject.fx;
  const bundleHref = fx
    ? isTalent
      ? talentBundle(realm, subject.cls.slug, fx.spell_id)
      : spellBundle(subject.id)
    : null;

  return (
    <>
      <div className="flex items-start gap-4">
        {isTalent
          ? <SpriteIcon icon={subject.talent.icon} sheet={sheet} className="size-14 shrink-0 rounded" />
          : <TextureIcon path={subject.icon} className="size-14 shrink-0 rounded" />}
        <div className="min-w-0 flex-1">
          <h2 className="display text-[22px] font-bold leading-tight">
            {isTalent ? subject.talent.name : subject.name}
          </h2>
          <p className="mt-1 font-mono text-[11px] text-dim">
            {isTalent
              ? `${subject.talent.entry_type}${subject.talent.is_passive ? " · passive" : ""} · ${subject.cls.name} · ${subject.tree.tree.name}`
              : [subject.rank, "from the client's spell table"].filter(Boolean).join(" · ")}
          </p>
        </div>
        <Button
          variant="outline" size="sm" onClick={onPin} aria-pressed={pinned}
          className={cn(
            "shrink-0 gap-2 text-[11.5px]",
            pinned
              ? "border-class bg-[color-mix(in_srgb,var(--class)_14%,transparent)] text-foreground"
              : "border-line2 bg-sunk text-dim hover:border-class hover:text-foreground",
          )}
        >
          <Pin className="size-3.5" />
          {pinned ? "On the board" : "Pin to compare"}
        </Button>
      </div>

      {!isTalent && (
        <section className="mt-6">
          <h3 className="eyebrow mb-2.5">Granted by</h3>
          <GrantedBy owners={subject.owners} />
        </section>
      )}

      <Chips subject={subject} />

      {(isTalent ? subject.talent.description_html : subject.description) && (
        <section className="mt-6">
          <h3 className="eyebrow mb-2.5 flex items-center gap-2.5">
            Description <Separator className="flex-1" />
          </h3>
          {isTalent
            ? <div
                className="max-w-[68ch] text-[13.5px] leading-relaxed [&_.item-number]:font-semibold [&_.item-number]:text-class"
                dangerouslySetInnerHTML={{ __html: sanitize(subject.talent.description_html) }}
              />
            : <div className="max-w-[68ch] text-[13.5px] leading-relaxed">
                {gameText(subject.description!)}
              </div>}
        </section>
      )}

      {fx && <FileList fx={fx} bundleHref={bundleHref} assetRoot={assetRoot} />}
    </>
  );
}

function Chips({ subject }: { subject: Subject }) {
  const chips: [string, number, boolean?][] = [];
  if (subject.kind === "talent") {
    const t = subject.talent;
    if (t.spell_id) chips.push(["spell", t.spell_id, true]);
    if (t.costs.talent_essence) chips.push(["TE", t.costs.talent_essence]);
    if (t.costs.ability_essence) chips.push(["AE", t.costs.ability_essence]);
    if (t.max_ranks > 1) chips.push(["ranks", t.max_ranks]);
    if (t.requirements.tree_talent_essence) {
      chips.push(["needs TE in tree", t.requirements.tree_talent_essence]);
    }
    if (t.requirements.level) chips.push(["level", t.requirements.level]);
  } else {
    chips.push(["spell", subject.id, true]);
    if (subject.fx?.visual_id) chips.push(["visual", subject.fx.visual_id]);
  }
  if (!chips.length) return null;

  return (
    <div className="mt-4 flex flex-wrap gap-1.5">
      {chips.map(([term, value, accent]) => (
        <Badge
          key={term} variant="outline"
          className={cn("gap-1 rounded-sm font-mono text-[11px] font-normal",
            accent
              ? "border-[color-mix(in_srgb,var(--class)_40%,transparent)] text-foreground"
              : "border-line2 text-dim")}
        >
          {term} <strong className="font-medium text-foreground">{value}</strong>
        </Badge>
      ))}
    </div>
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

  // Keyed by the file set, so switching subject shows "checking" rather than the
  // previous subject's answers.
  const load = useCallback(
    async (key: string) => new Map(await Promise.all(
      key.split("\n").filter(Boolean).map(
        async (p) => [p, await resolveAsset(assetRoot, p)] as const),
    )),
    [assetRoot],
  );
  const { value: urls } = useLoaded<Map<string, string | null>>(
    paths.length ? paths.join("\n") : null, load);

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
          const url = urls?.get(path);
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
