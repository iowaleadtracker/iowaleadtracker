// Browser tests for the map page (template.html): `pnpm test:map`.
// They load the template with saved map data (tests/frontend/fixtures), so no build is needed.
// Three engines: Chromium (Chrome, Edge), Firefox, and WebKit (Safari's engine). Locally,
// `pnpm test:map --project=chromium-desktop` runs one; `pnpm exec playwright install
// firefox webkit` adds the others.
import { defineConfig, devices } from "@playwright/test";

const desktop = { viewport: { width: 1280, height: 900 } };

export default defineConfig({
  testDir: "tests/frontend",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: { trace: "off" },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"], ...desktop } },
    { name: "chromium-phone", use: { ...devices["Pixel 7"] } },
    { name: "firefox-desktop", use: { ...devices["Desktop Firefox"], ...desktop } },
    { name: "webkit-desktop", use: { ...devices["Desktop Safari"], ...desktop } },
    { name: "webkit-phone", use: { ...devices["iPhone 13"] } },
  ],
});
