"use client";

import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ClassRef } from "@/lib/types";

export function ClassRail({
  classes, current, onSelect,
}: {
  classes: ClassRef[];
  current: string | null;
  onSelect: (cls: ClassRef) => void;
}) {
  return (
    <ScrollArea className="h-[calc(100vh-var(--masthead))] border-r border-line">
      <nav aria-label="Classes" className="py-5">
        <h2 className="eyebrow px-5 pb-2.5">Classes</h2>
        <ul>
          {classes.map((cls) => (
            <li key={cls.slug}>
              <button
                type="button"
                onClick={() => onSelect(cls)}
                aria-current={cls.slug === current}
                className={cn(
                  "grid w-full grid-cols-[3px_minmax(0,1fr)_auto] items-center gap-3 py-[7px] pr-5 text-left transition-colors",
                  cls.slug === current
                    ? "bg-panel font-semibold text-foreground"
                    : "text-dim hover:bg-panel hover:text-foreground",
                )}
              >
                <span
                  aria-hidden
                  className={cn("h-full min-h-5 transition-opacity",
                                cls.slug === current ? "opacity-100" : "opacity-55")}
                  style={{ background: cls.color }}
                />
                <span className="text-[13.5px]">{cls.name}</span>
                <span className="font-mono text-[11px] text-faint">{cls.talent_count}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </ScrollArea>
  );
}
