// Browser tests for the map page (template.html): `pnpm test:map`.
// They load the template with saved map data (tests/frontend/fixtures), so no build is needed.
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "tests/frontend",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: { trace: "off" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
});
