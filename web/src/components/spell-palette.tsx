"use client";

import { useEffect, useMemo, useState } from "react";
import { Sparkles, Swords, Wand2 } from "lucide-react";
import {
  Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@/components/ui/command";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { searchIndex, searchSpells } from "@/lib/api";
import type { SearchIndex, SpellHit, ViewerIndex } from "@/lib/types";

export type TalentHit = {
  name: string; talentId: number; spellId: number;
  realm: string; cls: string; tree: string; colour?: string; className?: string;
};

/**
 * One palette, two kinds of answer. Talents sit in a tree and come first, because a
 * name that is both is almost always being looked for as a talent. Behind them, every
 * spell in the client — 232,000 named ones, searched by the server.
 */
export function SpellPalette({
  open, onOpenChange, index, onTalent, onSpell,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  index: ViewerIndex | null;
  onTalent: (hit: TalentHit) => void;
  onSpell: (id: number) => void;
}) {
  const [query, setQuery] = useState("");
  const [talentIndex, setTalentIndex] = useState<SearchIndex | null>(null);
  const [answer, setAnswer] = useState<{ query: string; hits: SpellHit[] } | null>(null);

  // The talent index is the largest thing the viewer reads, so it waits for a search.
  useEffect(() => {
    if (open && !talentIndex) searchIndex().then(setTalentIndex, () => {});
  }, [open, talentIndex]);

  // Results carry the query they answer, so a stale set is filtered out by comparison
  // rather than cleared with a synchronous setState inside the effect.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    let live = true;
    const t = setTimeout(() => {
      searchSpells(q, 40).then(
        (r) => { if (live) setAnswer({ query: q, hits: r }); },
        () => { if (live) setAnswer({ query: q, hits: [] }); },
      );
    }, 140);
    return () => { live = false; clearTimeout(t); };
  }, [query]);

  const spells = answer?.query === query.trim() ? answer.hits : [];

  const classesBySlug = useMemo(() => {
    const map = new Map<string, { name: string; color: string }>();
    for (const realm of index?.realms ?? []) {
      for (const c of realm.classes) map.set(`${realm.slug}/${c.slug}`, { name: c.name, color: c.color });
    }
    return map;
  }, [index]);

  const talents: TalentHit[] = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2 || !talentIndex) return [];
    const numeric = /^\d+$/.test(q);
    return talentIndex.rows
      .filter(([name, , spellId]) =>
        numeric ? String(spellId).startsWith(q) : name.toLowerCase().includes(q))
      .slice(0, 40)
      .map(([name, talentId, spellId, realm, cls, tree]) => {
        const meta = classesBySlug.get(`${realm}/${cls}`);
        return { name, talentId, spellId, realm, cls, tree,
                 colour: meta?.color, className: meta?.name ?? cls };
      });
  }, [query, talentIndex, classesBySlug]);

  const seen = new Set(talents.map((t) => t.spellId));
  const rest = spells.filter((s) => !seen.has(s.id));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 sm:max-w-[640px]">
        <DialogHeader className="sr-only">
          <DialogTitle>Find a talent or spell</DialogTitle>
          <DialogDescription>
            Search every talent in both realms and every spell in the client
          </DialogDescription>
        </DialogHeader>
        {/* Filtering happens here and on the server, so cmdk must not also filter. */}
        <Command shouldFilter={false} className="[&_[cmdk-input-wrapper]]:border-b [&_[cmdk-input-wrapper]]:border-line">
      <CommandInput placeholder="Name or spell id…" value={query} onValueChange={setQuery} />
      <CommandList className="max-h-[60vh]">
        {query.trim().length >= 2 && !talents.length && !rest.length && (
          <CommandEmpty>Nothing matches “{query}”.</CommandEmpty>
        )}

        {talents.length > 0 && (
          <CommandGroup heading={`Talents (${talents.length})`}>
            {talents.map((hit) => (
              <CommandItem key={`${hit.realm}-${hit.cls}-${hit.talentId}`}
                           value={`t-${hit.realm}-${hit.cls}-${hit.talentId}`}
                           onSelect={() => { onTalent(hit); onOpenChange(false); }}>
                <span aria-hidden className="mr-1 h-4 w-[3px] rounded-sm"
                      style={{ background: hit.colour ?? "var(--line-2)" }} />
                <Swords className="size-3.5 text-faint" />
                <span className="truncate">{hit.name}</span>
                <span className="ml-auto truncate font-mono text-[11px] text-dim">
                  {hit.className} · {hit.tree}
                </span>
                <span className="font-mono text-[11px] text-faint">{hit.spellId || "—"}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {rest.length > 0 && (
          <CommandGroup heading={`Elsewhere in the client (${rest.length})`}>
            {rest.map((hit) => {
              const owner = hit.owners[0];
              return (
                <CommandItem key={hit.id} value={`s-${hit.id}`}
                             onSelect={() => { onSpell(hit.id); onOpenChange(false); }}>
                  <span aria-hidden className="mr-1 h-4 w-[3px] rounded-sm bg-line2" />
                  {owner ? <Wand2 className="size-3.5 text-faint" />
                         : <Sparkles className="size-3.5 text-faint" />}
                  <span className="truncate">{hit.name}</span>
                  {owner && (
                    <Badge variant="outline"
                           className="border-line2 font-mono text-[9px] uppercase tracking-wider">
                      {owner.type}
                    </Badge>
                  )}
                  <span className="ml-auto truncate font-mono text-[11px] text-dim">
                    {owner ? `${owner.class}${owner.tab ? " · " + owner.tab : ""}`
                           : `${hit.model_count} models · ${hit.sound_count} sounds`}
                  </span>
                  <span className="font-mono text-[11px] text-faint">{hit.id}</span>
                </CommandItem>
              );
            })}
          </CommandGroup>
        )}
      </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
