"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronRight, Pin, Search, Sparkles } from "lucide-react";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { searchSpells } from "@/lib/api";
import type { ClassRef, RealmRef, SpellHit, Talent, TreePayload, TreeRef } from "@/lib/types";

/**
 * One navigator for everything the archive holds.
 *
 * The old rail listed 21 classes and nothing else, so a spell that belongs to no talent
 * tree — which is most of the 232,000 the client ships — had nowhere to live and had to
 * borrow the reader while an unrelated class sat behind it. Here both are rows in the
 * same list: classes and their trees above, spells from the client's own table below,
 * and one search field filters both.
 */
export function Navigator({
  realm, cls, treeRef, payload, selectedKey, pinnedKeys,
  onPickClass, onPickTree, onPickTalent, onPickSpell, onPin,
}: {
  realm: RealmRef;
  cls: ClassRef | null;
  treeRef: TreeRef | null;
  payload: TreePayload | null;
  selectedKey: string | null;
  pinnedKeys: Set<string>;
  onPickClass: (cls: ClassRef) => void;
  onPickTree: (tree: TreeRef) => void;
  onPickTalent: (talent: Talent) => void;
  onPickSpell: (id: number) => void;
  onPin: (what: { kind: "talent"; talent: Talent } | { kind: "spell"; hit: SpellHit }) => void;
}) {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<{ query: string; hits: SpellHit[] } | null>(null);

  // The results carry the query they answer, so "searching" is derived rather than a
  // second piece of state set synchronously inside the effect.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    let live = true;
    const timer = setTimeout(() => {
      searchSpells(q, 25).then(
        (hits) => { if (live) setAnswer({ query: q, hits }); },
        () => { if (live) setAnswer({ query: q, hits: [] }); },
      );
    }, 160);
    return () => { live = false; clearTimeout(timer); };
  }, [query]);

  const needleForSpells = query.trim();
  const spells = answer?.query === needleForSpells ? answer.hits : [];
  const searching = needleForSpells.length >= 2 && answer?.query !== needleForSpells;

  const needle = query.trim().toLowerCase();
  const classes = useMemo(
    () => realm.classes.filter((c) => !needle || c.name.toLowerCase().includes(needle)),
    [realm, needle],
  );
  const talents = useMemo(() => {
    const all = payload?.tree.talents ?? [];
    return needle ? all.filter((t) => t.name.toLowerCase().includes(needle)) : all;
  }, [payload, needle]);

  return (
    <div className="flex h-[calc(100vh-var(--masthead))] flex-col border-r border-line">
      <div className="border-b border-line p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-faint" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter classes, talents, spells…"
            aria-label="Filter"
            className="h-8 border-line2 bg-sunk pl-8 text-[13px]"
          />
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="pb-6">
          <h2 className="eyebrow px-4 pb-1.5 pt-4">{realm.name}</h2>

          {classes.map((entry) => {
            const open = entry.slug === cls?.slug;
            return (
              <div key={entry.slug}>
                <button
                  type="button"
                  onClick={() => onPickClass(entry)}
                  aria-expanded={open}
                  className={cn(
                    "grid w-full grid-cols-[3px_auto_minmax(0,1fr)_auto] items-center gap-2.5 py-[7px] pr-3 text-left transition-colors",
                    open ? "bg-panel font-medium text-foreground" : "text-dim hover:bg-panel hover:text-foreground",
                  )}
                >
                  <span aria-hidden className="h-4 w-[3px]" style={{ background: entry.color }} />
                  <ChevronRight className={cn("size-3 text-faint transition-transform", open && "rotate-90")} />
                  <span className="truncate text-[13px]">{entry.name}</span>
                  <span className="font-mono text-[10.5px] text-faint">{entry.talent_count}</span>
                </button>

                {open && (
                  <div className="pb-1">
                    {entry.trees.map((tree) => {
                      const current = tree.slug === treeRef?.slug;
                      return (
                        <div key={tree.slug}>
                          <button
                            type="button"
                            onClick={() => onPickTree(tree)}
                            aria-expanded={current}
                            className={cn(
                              "flex w-full items-center gap-2 py-1 pl-[26px] pr-3 text-left text-[12px] transition-colors",
                              current ? "text-foreground" : "text-dim hover:text-foreground",
                            )}
                          >
                            <ChevronRight className={cn("size-3 text-faint transition-transform", current && "rotate-90")} />
                            <span className="truncate">{tree.name}</span>
                            <span className="ml-auto font-mono text-[10px] text-faint">{tree.talent_count}</span>
                          </button>

                          {current && talents.map((talent) => (
                            <Row
                              key={talent.id}
                              label={talent.name}
                              meta={talent.spell_id ? String(talent.spell_id) : "—"}
                              indent
                              selected={selectedKey === `talent:${entry.slug}:${talent.id}`}
                              pinned={pinnedKeys.has(`talent:${entry.slug}:${talent.id}`)}
                              onSelect={() => onPickTalent(talent)}
                              onPin={() => onPin({ kind: "talent", talent })}
                            />
                          ))}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          {/* The client's own spell table. Most of these belong to no tree at all. */}
          <h2 className="eyebrow flex items-center gap-2 px-4 pb-1.5 pt-6">
            <Sparkles className="size-3" />
            Elsewhere in the client
          </h2>
          {needle.length < 2 ? (
            <p className="px-4 text-[12px] leading-snug text-faint">
              Type at least two characters to search the 232,000 spells the client ships.
            </p>
          ) : searching ? (
            <p className="px-4 font-mono text-[11px] text-faint">searching…</p>
          ) : spells.length === 0 ? (
            <p className="px-4 text-[12px] text-faint">Nothing matches.</p>
          ) : (
            spells.map((hit) => (
              <Row
                key={hit.id}
                label={hit.name}
                meta={hit.owners[0]?.class ?? String(hit.id)}
                selected={selectedKey === `spell:${hit.id}`}
                pinned={pinnedKeys.has(`spell:${hit.id}`)}
                onSelect={() => onPickSpell(hit.id)}
                onPin={() => onPin({ kind: "spell", hit })}
              />
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

/** A leaf: click the label to read it, click the pin to put it on the board. */
function Row({
  label, meta, indent, selected, pinned, onSelect, onPin,
}: {
  label: string; meta: string; indent?: boolean;
  selected: boolean; pinned: boolean;
  onSelect: () => void; onPin: () => void;
}) {
  return (
    <div
      className={cn(
        "group flex items-center gap-2 pr-2 transition-colors",
        selected ? "bg-[color-mix(in_srgb,var(--class)_14%,transparent)]" : "hover:bg-panel",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected}
        className={cn(
          "flex min-w-0 flex-1 items-baseline gap-2 py-[5px] pr-1 text-left text-[12.5px]",
          indent ? "pl-[42px]" : "pl-4",
          selected ? "text-foreground" : "text-dim group-hover:text-foreground",
        )}
      >
        <span className="truncate">{label}</span>
        <span className="ml-auto shrink-0 font-mono text-[10px] text-faint">{meta}</span>
      </button>
      <button
        type="button"
        onClick={onPin}
        aria-label={pinned ? `${label} is on the board` : `Pin ${label} to the board`}
        aria-pressed={pinned}
        className={cn(
          "grid size-5 shrink-0 place-items-center rounded-full border transition-all",
          pinned
            ? "border-class bg-[color-mix(in_srgb,var(--class)_18%,transparent)] text-class"
            : "border-transparent text-faint opacity-0 group-hover:border-line2 group-hover:opacity-100 hover:!text-class focus-visible:opacity-100",
        )}
      >
        <Pin className="size-2.5" />
      </button>
    </div>
  );
}
