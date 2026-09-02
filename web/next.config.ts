import type { NextConfig } from "next";

/**
 * The Python service is the engine: it reads the MPQ archives, decodes BLP textures,
 * parses M2 models and answers the spellbook. None of that is reimplemented here;
 * src/middleware.ts forwards its paths, so the browser sees one origin and the two
 * processes stay separately deployable.
 */
const nextConfig: NextConfig = {
  // Forwarding to the Python service is done in src/middleware.ts, not here: a
  // rewrites() entry is baked into the build, and this image has to be able to point
  // at a different address than the machine that built it.

  // The archive is served from disk beside the app; no remote image hosts.
  images: { unoptimized: true },
  output: "standalone",
};

export default nextConfig;
