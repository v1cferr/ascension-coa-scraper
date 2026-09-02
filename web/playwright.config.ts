import { defineConfig, devices } from "@playwright/test";

/**
 * Two suites against one running stack.
 *
 * `api` drives the Python service directly — the half that reads MPQ archives, decodes
 * textures and answers the spellbook — with request-level checks and no browser.
 * `viewer` drives the page. Both go through the viewer's own origin, because that is
 * what a reader actually talks to, and it exercises the forwarding at the same time.
 *
 * Nothing is started for you: point BASE_URL at `docker compose up` or at a dev
 * server. The tests read a live archive rather than fixtures, so they assert on
 * shapes and invariants rather than on counts that change with every re-extraction.
 */
const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : [["list"]],
  timeout: 60_000,
  expect: { timeout: 15_000 },

  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    { name: "api", testMatch: /api\/.*\.spec\.ts/ },
    {
      name: "viewer",
      testMatch: /viewer\/.*\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
