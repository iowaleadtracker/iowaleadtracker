// The built site in a real browser: the landing page, the staged page, the monitor-placement
// brief, the 404 page, and a map page on its own. Run after a build (`make_map_picker.py
// --build`, or CI's build job), with `pnpm test:site`; without a build, these tests skip.
//
// A small server serves outputs/site with the headers from its _headers file, as Cloudflare
// does, so the Content-Security-Policy is in force: anything it blocks shows up as a console
// error and fails the test. Requests to other sites (map tiles, analytics) are blocked.
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { createServer } from "node:http";
import { existsSync, readFileSync, readdirSync, statSync, createReadStream } from "node:fs";
import { extname, join, normalize } from "node:path";

const SITE = process.env.SITE_DIR || new URL("../../scenarios/iowa-aap-lead-azide/outputs/site/", import.meta.url).pathname;
const BUILT = existsSync(join(SITE, "index.html"));
const STAGED = BUILT ? readdirSync(SITE).find((n) => n.startsWith("s-")) : "";
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".ico": "image/x-icon", ".json": "application/json", ".txt": "text/plain; charset=utf-8",
  ".xml": "application/xml" };

// _headers: "/path/*" lines, each followed by indented "Name: value" lines.
function headerRules() {
  const rules = [];
  for (const line of readFileSync(join(SITE, "_headers"), "utf8").split("\n")) {
    if (/^\S/.test(line)) rules.push({ pattern: line.trim(), headers: {} });
    else if (line.trim() && rules.length) {
      const i = line.indexOf(":");
      rules[rules.length - 1].headers[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    }
  }
  return rules;
}
const matches = (pattern, path) => (pattern.endsWith("*") ? path.startsWith(pattern.slice(0, -1)) : path === pattern);

let server, origin;
test.beforeAll(async () => {
  if (!BUILT) return;
  const rules = headerRules();
  server = createServer((req, res) => {
    const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
    let file = normalize(join(SITE, path));
    if (!file.startsWith(normalize(SITE))) { res.writeHead(403); return res.end(); }
    if (existsSync(file) && statSync(file).isDirectory()) file = join(file, "index.html");
    let status = 200;
    if (!existsSync(file)) { status = 404; file = join(SITE, "404.html"); }   // as Cloudflare's 404-page handling
    const headers = { "content-type": TYPES[extname(file)] || "application/octet-stream" };
    for (const r of rules) if (matches(r.pattern, path)) Object.assign(headers, r.headers);
    delete headers["Strict-Transport-Security"];
    // upgrade-insecure-requests would send this http:// test server's requests to https
    if (headers["Content-Security-Policy"]) headers["Content-Security-Policy"] = headers["Content-Security-Policy"].replace(/;\s*upgrade-insecure-requests/, "");
    res.writeHead(status, headers);
    createReadStream(file).pipe(res);
  });
  await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
  origin = `http://localhost:${server.address().port}`;
});
test.afterAll(() => server && server.close());
test.skip(!BUILT, "no built site: run make_map_picker.py --build first");

// Open a page of the site; return the errors it (and its map frame) logs.
async function open(page, path) {
  const errors = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const t = m.text();
    // outside requests are blocked on purpose; anything else (CSP refusals included) is an error
    if (t.startsWith("Failed to load resource: net::ERR_FAILED")) return;
    errors.push(`console: ${t}`);
  });
  await page.route((url) => url.origin !== origin, (r) => r.abort());
  await page.goto(origin + path);
  return errors;
}
const mapFrame = (page) => page.frameLocator("iframe#map");
// Wait until the map frame shows its current src, decoded and drawn (a missing file would
// get the 404 page, which never gets there). Switching maps before that abandons the
// decode, which WebKit logs as errors, so each step waits for it, as a reader would.
async function mapReady(page, base) {
  const src = await page.locator("iframe#map").getAttribute("src");
  const want = new URL(src, base).href.split("#")[0];
  // say what was seen, so a failure tells a missing frame from a slow one
  const state = async () => {
    const f = page.frames().find((fr) => fr.url().split("#")[0] === want);
    if (!f) return `no frame at ${want} (frames: ${page.frames().map((fr) => fr.url()).join(", ")})`;
    return f.evaluate(() => (document.getElementById("loading") ? `loading: ${document.getElementById("loading").textContent}`
      : document.getElementById("title")?.textContent ? "ready" : "no map on the page")).catch((e) => `frame busy: ${e.message.split("\n")[0]}`);
  };
  await expect.poll(state, { message: `the map ${src} loads`, timeout: 20000 }).toBe("ready");
}
// Pick a menu value as a reader does: only when it changes. (Setting a menu to its current
// value still fires "change", and two map loads back to back are more than WebKit handles.)
async function choose(page, sel, value) {
  if ((await page.locator(sel).inputValue()) !== value) await page.selectOption(sel, value);
}
const noSideScroll = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test.describe("landing page", () => {
  test("opens with About on top, focus on its heading, and the map loaded", async ({ page }) => {
    const errors = await open(page, "/");
    const note = page.locator("dialog#note");
    await expect(note).toHaveAttribute("open", "");                       // first visit: About opens
    await expect(page.locator("#note-h")).toBeFocused();
    expect(await note.evaluate((d) => d.scrollTop)).toBe(0);
    await page.keyboard.press("Escape");
    await expect(note).not.toHaveAttribute("open", "");
    await mapReady(page, origin + "/");                                    // the map frame drew a map
    await page.reload();                                                  // seen this build: stays closed
    await expect(page.locator("dialog#note")).not.toHaveAttribute("open", "");
    expect(errors).toEqual([]);
  });

  test("the dialogs open at the top with focus on the heading, and close", async ({ page }) => {
    const errors = await open(page, "/");
    await page.keyboard.press("Escape");
    for (const [button, dialog] of [["#about", "#note"], ["#cites", "#cite"]]) {
      await page.locator(button).click();
      await expect(page.locator(dialog)).toHaveAttribute("open", "");
      await expect(page.locator(`${dialog}-h`)).toBeFocused();
      expect(await page.locator(dialog).evaluate((d) => d.scrollTop)).toBe(0);
      await page.keyboard.press("Escape");
      await expect(page.locator(dialog)).not.toHaveAttribute("open", "");
    }
    expect(errors).toEqual([]);
  });

  test("every combination of weather, case and time loads a map", async ({ page }) => {
    test.setTimeout(120000);   // loads every map, one at a time
    const errors = await open(page, "/");
    await page.keyboard.press("Escape");
    await mapReady(page, origin + "/");
    const choices = async (sel) => ((await page.locator(sel).isVisible())   // a hidden menu has one choice
      ? page.locator(`${sel} option`).evaluateAll((os) => os.map((o) => o.value)) : [null]);
    let n = 0;
    for (const w of await choices("#w")) for (const c of await choices("#c")) for (const t of await choices("#t")) {
      for (const [sel, v] of [["#w", w], ["#c", c], ["#t", t]]) {
        if (v !== null) await choose(page, sel, v);
        await mapReady(page, origin + "/");   // one map at a time, as a reader sees them
      }
      n++;
    }
    expect(n).toBeGreaterThan(1);
    expect(errors).toEqual([]);
  });

  test("#references opens the references, after the About note on a first visit", async ({ page }) => {
    const errors = await open(page, "/#references");
    await expect(page.locator("dialog#note")).toHaveAttribute("open", "");   // first visit: the note first
    await expect(page.locator("dialog#cite")).not.toHaveAttribute("open", "");
    await page.keyboard.press("Escape");
    await expect(page.locator("dialog#cite")).toHaveAttribute("open", "");   // then the references
    await page.keyboard.press("Escape");
    await page.goto(origin + "/#references");                               // a later visit: straight there
    await expect(page.locator("dialog#cite")).toHaveAttribute("open", "");
    await expect(page.locator("dialog#note")).not.toHaveAttribute("open", "");
    expect(errors).toEqual([]);
  });

  test("the map's detection-limit link opens the references on the page around it", async ({ page }) => {
    const errors = await open(page, "/");
    await page.keyboard.press("Escape");
    await mapReady(page, origin + "/");
    const map = mapFrame(page);
    test.skip(!(await map.locator("#siteswrap").isVisible()), "the opening map has no EPA sites");
    await map.locator("#showSites").check();
    await map.locator("#sitepick").selectOption("AS01");
    const link = map.locator("#legsite a.reflink").first();
    await expect(link).toHaveAttribute("href", "/#references");
    const tabs = page.context().pages().length;
    await link.click();
    await expect(page.locator("dialog#cite")).toHaveAttribute("open", "");
    expect(page.context().pages().length).toBe(tabs);   // in place, not a new tab
    await expect(page.locator("dialog#cite")).toContainText("McFate, L., 2026d");
    expect(errors).toEqual([]);
  });

  test("the U.S./metric switch reaches the map", async ({ page }) => {
    const errors = await open(page, "/");
    await page.keyboard.press("Escape");
    await mapReady(page, origin + "/");
    await page.locator('#sys button[data-v="metric"]').click();
    await expect(mapFrame(page).locator('#sysseg button[data-v="metric"]')).toHaveAttribute("aria-pressed", "true");
    await page.locator('#sys button[data-v="us"]').click();
    await expect(mapFrame(page).locator('#sysseg button[data-v="us"]')).toHaveAttribute("aria-pressed", "true");
    expect(errors).toEqual([]);
  });

  test("the summary and questions are there, and the page fits the screen", async ({ page, isMobile }) => {
    const errors = await open(page, "/");
    await page.keyboard.press("Escape");
    await page.locator("#tosummary").click();
    await expect(page.locator("#summary-h")).toBeInViewport();
    await expect(page.locator("#faq-h")).toHaveCount(1);
    expect(await noSideScroll(page)).toBe(true);
    if (isMobile) await expect(page.locator(".bottomnav")).toBeVisible();   // the phone's section bar
    expect(errors).toEqual([]);
  });
});

test("every day, case and time on the staged page, and its buttons, load maps", async ({ page }) => {
  test.setTimeout(120000);   // loads every map, one at a time
  const errors = await open(page, `/${STAGED}/`);
  const loads = () => mapReady(page, `${origin}/${STAGED}/`);
  await loads();
  const choices = (sel) => page.locator(`${sel} option`).evaluateAll((os) => os.map((o) => o.value));
  for (const d of await choices("#d")) {
    await choose(page, "#d", d);   // each day has its own times
    await loads();
    for (const c of await choices("#c")) for (const t of await choices("#t")) {
      await choose(page, "#c", c);
      await loads();
      await choose(page, "#t", t);
      await loads();
    }
  }
  await page.locator("#prev").click(); await loads();
  await page.locator("#next").click(); await loads();
  expect(await noSideScroll(page)).toBe(true);
  expect(errors).toEqual([]);
});

test("the monitor-placement brief shows its map image", async ({ page }) => {
  const errors = await open(page, "/monitor-placement/");
  const img = page.locator("main img").first();
  await expect(img).toBeVisible();
  expect(await img.evaluate((i) => i.complete && i.naturalWidth > 0)).toBe(true);
  expect(await noSideScroll(page)).toBe(true);
  expect(errors).toEqual([]);
});

test("a missing address gets the 404 page, which links home", async ({ page }) => {
  const errors = await open(page, "/no-such-page");
  const res = await page.request.get(`${origin}/no-such-page`);
  expect(res.status()).toBe(404);
  await expect(page.locator('a[href="/"]').first()).toBeVisible();
  // the browser logs the 404 status of the page itself; nothing else may fail
  expect(errors.filter((e) => !e.includes("status of 404"))).toEqual([]);
});

test("a map opened on its own works, including the HYSPLIT file download", async ({ page, isMobile }) => {
  const name = readdirSync(join(SITE, "m")).find((n) => n.startsWith("archived-mid-"));
  const errors = await open(page, `/m/${name}`);
  await expect(page.locator("#standalone")).toBeVisible();
  const button = page.locator("#hysplit button").first();
  if (!isMobile) await page.locator("#techdetails > summary").click().catch(() => {});
  if (await button.isVisible()) {
    const download = page.waitForEvent("download");
    await button.click();
    expect((await download).suggestedFilename()).toMatch(/\S/);
  }
  expect(errors).toEqual([]);
});

// A reader who changes two menus before the first map has loaded must end up on the map
// the menus show. (Safari could drop the second change; the pages now load one map at a
// time.) WebKit may log the abandoned first decode; that's allowed here, nothing else.
const abandonedDecode = (e) => /NotReadableError|due to access control checks/.test(e);
const otherChoice = async (page, sel) => page.locator(`${sel} option`).evaluateAll(
  (os, cur) => os.map((o) => o.value).find((v) => v !== cur), await page.locator(sel).inputValue());
// Wait until the frame's src is the file `fileExpr` names (evaluated in the page), then
// until that map has loaded.
async function endsOn(page, base, fileExpr) {
  const file = await page.evaluate(fileExpr);
  expect(file, "the menus name a map").toBeTruthy();
  await expect.poll(async () => (await page.locator("iframe#map").getAttribute("src")).split("#")[0],
    { message: "the frame moves to the map the menus show", timeout: 20000 }).toContain(file);
  await mapReady(page, base);
}

test("two quick menu changes on the landing page end on the right map", async ({ page }) => {
  const errors = await open(page, "/");
  await page.keyboard.press("Escape");
  await mapReady(page, origin + "/");
  const [weather, cas] = [await otherChoice(page, "#w"), await otherChoice(page, "#c")];
  await page.selectOption("#w", weather);   // no wait: the second change comes while the first loads
  await page.selectOption("#c", cas);
  // the key the page's show() builds from the menus
  await endsOn(page, origin + "/", `MAP_FILES[(document.getElementById("w").value === "forecast" ? "" : document.getElementById("w").value + "-")
    + document.getElementById("d").value + "-" + document.getElementById("c").value + "-" + document.getElementById("t").value.replace(":", "")]`);
  expect(errors.filter((e) => !abandonedDecode(e))).toEqual([]);
});

test("two quick menu changes on the staged page end on the right map", async ({ page }) => {
  const errors = await open(page, `/${STAGED}/`);
  await mapReady(page, `${origin}/${STAGED}/`);
  const [cas, time] = [await otherChoice(page, "#c"), await otherChoice(page, "#t")];
  await page.selectOption("#c", cas);
  await page.selectOption("#t", time);
  await endsOn(page, `${origin}/${STAGED}/`, `FILES[document.getElementById("d").value + "-" + document.getElementById("c").value + "-"
    + document.getElementById("t").value.replace(":", "")]`);
  expect(errors.filter((e) => !abandonedDecode(e))).toEqual([]);
});

test("the Content-Security-Policy is in force in these tests", async ({ page }) => {
  const errors = await open(page, "/404.html");
  // a data: image, which the policy no longer allows: the browser must refuse it
  await page.evaluate(() => { const i = new Image(); i.src = "data:image/gif;base64,R0lGODlhAQABAAAAACw="; document.body.append(i); });
  await expect.poll(() => errors.some((e) => /Content Security Policy|img-src/.test(e))).toBe(true);
});

test.describe("accessibility (axe, WCAG 2.1 A and AA)", () => {
  const PAGES = [["landing, About open", "/", true], ["landing", "/", false], ["staged", () => `/${STAGED}/`],
    ["monitor-placement brief", "/monitor-placement/"], ["404", "/no-such-page"]];
  for (const [name, path, keepAbout] of PAGES) {
    test(name, async ({ page }) => {
      await open(page, typeof path === "function" ? path() : path);
      if (path === "/" && !keepAbout) await page.keyboard.press("Escape");
      const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      expect(r.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length}): ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
    });
  }
});
