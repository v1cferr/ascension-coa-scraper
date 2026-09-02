import type { NextConfig } from "next";

/**
 * The Python service is the engine: it reads the MPQ archives, decodes BLP textures,
 * parses M2 models and answers the spellbook. None of that is reimplemented here.
 * Everything under the API's own paths is proxied to it, so the browser sees one
 * origin and the two processes stay separately deployable.
 */
const API = process.env.ASCENSION_API ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/data/:path*", destination: `${API}/data/:path*` },
      { source: "/_spell/:path*", destination: `${API}/_spell/:path*` },
      { source: "/_spells", destination: `${API}/_spells` },
      { source: "/_model/:path*", destination: `${API}/_model/:path*` },
      { source: "/_texture/:path*", destination: `${API}/_texture/:path*` },
      { source: "/_bundle/:path*", destination: `${API}/_bundle/:path*` },
    ];
  },
  // The archive is served from disk beside the app; no remote image hosts.
  images: { unoptimized: true },
  output: "standalone",
};

export default nextConfig;
