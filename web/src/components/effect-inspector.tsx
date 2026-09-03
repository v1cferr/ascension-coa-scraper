"use client";

import { useCallback } from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { modelInfo, textureUrl } from "@/lib/api";
import { ParticleStage } from "@/components/particle-stage";
import { useLoaded } from "@/lib/use-loaded";
import type { ModelInfo } from "@/lib/types";

/**
 * What a model actually draws — now by drawing it.
 *
 * The client's effects are particle systems, so this runs them: each emitter's own
 * speed, gravity, lifespan and its colour, alpha and size curves, read out of the
 * model. Below the stage sit the parts a moving image cannot hold still enough to
 * read — the sprites it composites and how it is built.
 *
 * What the stage does NOT have is the caster. There is no character model, no skeleton
 * and no animation here: emitters are placed at their own model-space positions, not on
 * a bone of someone casting. It is the effect, not the scene.
 */
export function EffectInspector({ path, onClose }: { path: string; onClose: () => void }) {
  const load = useCallback((p: string) => modelInfo(p), []);
  const { value: info, failed } = useLoaded<ModelInfo>(path, load);

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
  // Emitters the reader could not fully resolve. Named rather than hidden: a stage that
  // quietly invents the missing half looks exactly like one that read it.
  const unresolved = (info?.particles ?? []).filter((e) => e.texture && !e.resolved).length;
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

          {(info.particles ?? []).some((e) => e.texture) && (
            <>
              <h4 className="eyebrow mt-6 mb-2.5">Running</h4>
              <ParticleStage emitters={info.particles} />
              <p className="mt-2 text-[12.5px] text-dim">
                {unresolved > 0
                  ? `Driven by each emitter's own motion, except ${unresolved} of ${info.particles.length}
                     whose tracks did not resolve — those fall back to a plain throw and are not
                     the client's numbers.`
                  : "Driven by each emitter's own speed, gravity, lifespan and colour, straight out of the model."}
              </p>
            </>
          )}

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
                The frames above, held still. Shown on black, which is how the game composites them.
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
