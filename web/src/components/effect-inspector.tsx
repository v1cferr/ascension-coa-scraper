"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { modelInfo, textureUrl } from "@/lib/api";
import type { ModelInfo } from "@/lib/types";

/**
 * What a model actually draws. Not a render — the client's effects are particle
 * systems, and drawing those properly means writing a renderer. These are the two
 * things that do say what an effect looks like: the sprites it composites, and how it
 * is built. For a particle effect the sprites are very nearly the whole of it.
 */
export function EffectInspector({ path, onClose }: { path: string; onClose: () => void }) {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setInfo(null);
    setFailed(false);
    modelInfo(path).then(
      (i) => live && setInfo(i),
      () => live && setFailed(true),
    );
    return () => { live = false; };
  }, [path]);

  const facts: [string, string][] = [];
  if (info) {
    const c = info.counts;
    if (info.is_particle_only) facts.push(["built from", "particles only — no geometry"]);
    else if (c.vertices) facts.push(["geometry", `${c.vertices.toLocaleString()} vertices`]);
    if (c.particle_emitters) facts.push(["particle emitters", String(c.particle_emitters)]);
    if (c.ribbon_emitters) facts.push(["ribbon emitters", String(c.ribbon_emitters)]);
    if (c.lights) facts.push(["lights", String(c.lights)]);
    if (c.animations) facts.push(["animations", String(c.animations)]);
    if (c.bones) facts.push(["bones", String(c.bones)]);
    const modes = [...new Set([...info.blend_modes, ...info.emitters.map((e) => e.blend)])];
    if (modes.length) facts.push(["blending", modes.join(", ")]);
    const kinds = [...new Set(info.emitters.map((e) => e.kind))];
    if (kinds.length) facts.push(["emitter shape", kinds.join(", ")]);
  }

  // An emitter names the texture it throws, so each sprite carries its own blending.
  const blendFor = new Map(
    (info?.emitters ?? []).map((e) => [info?.textures[e.texture]?.path, e.blend]),
  );
  const shown = info?.textures.filter((t) => t.available) ?? [];
  const absent = info?.textures.filter((t) => !t.available) ?? [];

  return (
    <section className="mt-5 rounded border border-line2 bg-panel p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="display text-[17px] font-bold">{info?.name ?? path.split(/[\\/]/).pop()}</h3>
          <p className="mt-1 break-all font-mono text-[11px] text-faint">{path}</p>
        </div>
        <Button size="icon" variant="outline" aria-label="Close" onClick={onClose}
                className="size-6 shrink-0 border-line2 bg-sunk text-dim hover:border-class hover:text-foreground">
          <X className="size-3.5" />
        </Button>
      </div>

      {failed && (
        <p className="mt-4 text-[13px] text-dim">
          This model is not in the extracted assets, so there is nothing to show.
          Run <code className="font-mono">ascension-coa client extract</code>.
        </p>
      )}

      {!info && !failed && (
        <div className="mt-5 grid grid-cols-[repeat(auto-fill,minmax(132px,1fr))] gap-2.5">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-[116px]" />)}
        </div>
      )}

      {info && (
        <>
          <dl className="mt-4 flex flex-wrap gap-x-7 gap-y-2">
            {facts.map(([term, value]) => (
              <div key={term} className="flex flex-col gap-0.5">
                <dt className="eyebrow !text-[9.5px] !tracking-[0.12em]">{term}</dt>
                <dd className="font-mono text-[12.5px]">{value}</dd>
              </div>
            ))}
          </dl>

          {shown.length > 0 ? (
            <>
              <h4 className="eyebrow mt-6 mb-2.5">Textures ({shown.length})</h4>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(132px,1fr))] gap-2.5">
                {shown.map((texture) => (
                  <figure key={texture.path}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={textureUrl(texture.path)}
                      alt={texture.path}
                      loading="lazy"
                      className="block h-[116px] w-full rounded-sm border border-line bg-black object-contain"
                      onError={(e) => {
                        const el = e.currentTarget;
                        el.replaceWith(Object.assign(document.createElement("div"), {
                          className:
                            "grid h-[116px] place-items-center rounded-sm border border-dashed " +
                            "border-line2 bg-sunk px-2 text-center font-mono text-[10px] text-faint",
                          textContent: "format not decodable",
                        }));
                      }}
                    />
                    <figcaption className="mt-1.5 break-all font-mono text-[10px] text-dim">
                      {texture.path.split("/").pop()}
                    </figcaption>
                    {blendFor.get(texture.path) && (
                      <Badge variant="outline"
                             className="mt-1 border-line2 font-mono text-[9px] uppercase tracking-wider text-class">
                        {blendFor.get(texture.path)}
                      </Badge>
                    )}
                  </figure>
                ))}
              </div>
              <p className="mt-3 text-[12.5px] text-dim">
                Sprites are shown on black, which is how the game composites them.
              </p>
            </>
          ) : (
            <p className="mt-4 text-[13px] text-dim">This model names no textures of its own.</p>
          )}

          {absent.length > 0 && (
            <p className="mt-2 text-[12.5px] text-dim">
              {absent.length} texture{absent.length > 1 ? "s are" : " is"} referenced but not extracted.
            </p>
          )}
        </>
      )}
    </section>
  );
}
