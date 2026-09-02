import { NextResponse, type NextRequest } from "next/server";

/**
 * Forward the archive's own paths to the Python service.
 *
 * This is middleware rather than a `rewrites()` entry because rewrites are resolved
 * during `next build` and written into routes-manifest.json, so the destination is
 * whatever the build machine had — which for a container image is a localhost that
 * holds nothing. Middleware runs per request, so the address can be a deployment
 * decision instead of a build one, and the same image works anywhere.
 */
export const config = {
  matcher: ["/data/:path*", "/_spell/:path*", "/_spells", "/_model/:path*",
            "/_texture/:path*", "/_bundle/:path*"],
  runtime: "nodejs",
};

export function middleware(request: NextRequest) {
  const api = process.env.ASCENSION_API ?? "http://127.0.0.1:8000";
  const target = new URL(request.nextUrl.pathname + request.nextUrl.search, api);
  return NextResponse.rewrite(target);
}
