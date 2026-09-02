import { cn } from "@/lib/utils";
import type { Owner } from "@/lib/types";

/**
 * Who grants a spell, and as what.
 *
 * The same effect is often a class's own ability and again a talent that upgrades it.
 * Both are worth seeing: one says the class has it from the start, the other that it is
 * something you choose. That distinction is the whole reason this panel exists.
 */
export function GrantedBy({ owners }: { owners: Owner[] }) {
  if (!owners.length) {
    return (
      <p className="text-[12.5px] text-dim">
        No class grants this spell — it belongs to a creature, an item, or the server&apos;s
        own machinery.
      </p>
    );
  }
  return (
    <ul className="grid gap-1.5">
      {owners.map((owner, i) => (
        <li key={i}
            className="flex flex-wrap items-baseline gap-2 rounded-sm border border-line border-l-2 border-l-class bg-sunk px-2.5 py-1.5">
          <span className={cn(
            "rounded-sm px-1.5 py-px text-[9px] font-semibold uppercase tracking-[0.1em]",
            owner.type === "Ability" ? "bg-class text-ink"
              : owner.type === "TalentAbility"
                ? "bg-[color-mix(in_srgb,var(--class)_40%,transparent)] text-foreground"
                : "bg-line text-dim",
          )}>
            {owner.type}
          </span>
          <span className="text-[13px] font-semibold">{owner.class}</span>
          {owner.tab && <span className="font-mono text-[10.5px] text-dim">{owner.tab}</span>}
          {owner.name && owner.name !== owner.class && (
            <span className="font-mono text-[10.5px] text-dim">{owner.name}</span>
          )}
          {owner.level && (
            <span className="ml-auto font-mono text-[10.5px] text-faint">level {owner.level}</span>
          )}
        </li>
      ))}
    </ul>
  );
}
