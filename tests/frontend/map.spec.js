// The map page in a real browser: template.html with saved map data put in the way
// dispersal/output.py does it. No build, no server: the page is served from memory and
// every other request (map tiles) is blocked.
//
// Fixtures: tests/frontend/fixtures/forecast.json (sky layer, Army outlines, model spread)
// and archived.json (NOAA HYSPLIT overlay). Remake with tools/refresh_map_fixtures.py.
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";

const TEMPLATE = readFileSync(new URL("../../template.html", import.meta.url), "utf8");
const fixture = (name) => JSON.parse(readFileSync(new URL(`fixtures/${name}.json`, import.meta.url), "utf8"));
const URL_ = "http://map.test/map.html";

// As dispersal/output.py write_html: no string in the data can close the <script>.
const embed = (data) => TEMPLATE.replace("/*__DATA__*/null", JSON.stringify(data)
  .replace(/</g, "\\u003c").replace(/>/g, "\\u003e").replace(/&/g, "\\u0026")
  .replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029"));

// Open the map; return the errors it logs (blocked tiles aside).
async function openMap(page, data, hash = "") {
  const errors = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().startsWith("Failed to load resource")) errors.push(`console: ${m.text()}`);
  });
  const html = embed(data);
  await page.route("**/*", (r) => (r.request().url().split("#")[0] === URL_
    ? r.fulfill({ contentType: "text/html", body: html }) : r.abort()));
  await page.goto(URL_ + hash);
  await expect(page.locator("#loading")).toHaveCount(0);   // decoded and drawn
  return errors;
}

const num = (text) => parseFloat(text.replace(/,/g, ""));
const visible = async (loc) => (await loc.count()) > 0 && loc.isVisible();

for (const name of ["forecast", "archived"]) {
  test(`${name}: loads and every control works without errors`, async ({ page }) => {
    const data = fixture(name);
    const errors = await openMap(page, data);
    await expect(page.locator("#title")).toHaveText(data.meta.title);
    await page.locator("#hour").fill(String(data.hours.length));
    await page.locator("#hour").fill("2");
    for (const v of ["peak", "snap", "dep", "zones", "conc"]) await page.locator(`#fieldseg button[data-v="${v}"]`).click();
    for (const v of ["metric", "us"]) await page.locator(`#sysseg button[data-v="${v}"]`).click();
    for (const u of await page.locator("#units option").evaluateAll((os) => os.map((o) => o.value))) await page.selectOption("#units", u);
    if (await visible(page.locator("#modelseg"))) {
      await page.locator('#modelseg button[data-v="hysplit"]').click();
      await page.locator("#ownbtn").click();
    }
    for (const b of ["imagery", "topo", "none", "dark", "light", "auto"]) await page.selectOption("#basemap", b);
    for (const cb of await page.locator('input[type="checkbox"]').all()) {
      if (await cb.isVisible()) { await cb.click(); await cb.click(); }
    }
    await page.locator("#decades").fill("7");
    await page.locator("#play").click();
    await page.waitForTimeout(400);
    await page.locator("#play").click();
    for (const z of ["#zin", "#zout", "#zfit"]) await page.locator(z).click();
    const box = await page.locator("#map").boundingBox();
    const [cx, cy] = [box.x + box.width / 2, box.y + box.height / 2];
    await page.mouse.move(cx, cy);
    await page.mouse.down();
    await page.mouse.move(cx + 60, cy + 30);
    await page.mouse.up();
    await page.mouse.move(cx - 20, cy);   // hover: the value under the pointer
    expect(errors).toEqual([]);
  });
}

test("each fixture shows only the layers its data has", async ({ page }) => {
  await openMap(page, fixture("forecast"));
  await expect(page.locator("#skywrap")).toBeVisible();
  await expect(page.locator("#refwrap")).toBeVisible();     // the Army's zones
  await expect(page.locator("#envwrap")).toBeVisible();     // the model spread
  await expect(page.locator("#modelseg")).toBeHidden();     // no saved HYSPLIT run
  await expect(page.locator("#siteswrap")).toBeVisible();   // EPA's sampling sites
  await openMap(page, fixture("archived"));
  await expect(page.locator("#skywrap")).toBeHidden();      // built without the weather layer
  await expect(page.locator("#modelseg")).toBeVisible();    // NOAA HYSPLIT
});

test("HYSPLIT is off until chosen, and labeled an estimate, not a NOAA forecast", async ({ page }) => {
  const data = fixture("archived");
  await openMap(page, data);
  await expect(page.locator("#ownbtn")).toHaveText(data.meta.homeName);   // the site's own model
  await expect(page.locator("#ownbtn")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#hynote")).toBeHidden();
  await page.locator('#modelseg button[data-v="hysplit"]').click();
  await expect(page.locator("#hynote")).toBeVisible();
  await expect(page.locator("#legtitle")).toHaveText(/^NOAA HYSPLIT: /);
  await expect(page.locator("#leghytext")).toContainText("Not a NOAA forecast.");
  await expect(page.locator("#budgetsec")).toBeHidden();
  for (const v of ["peak", "snap", "zones"]) await expect(page.locator(`#fieldseg button[data-v="${v}"]`)).toBeDisabled();
  for (const v of ["conc", "dep"]) await expect(page.locator(`#fieldseg button[data-v="${v}"]`)).toBeEnabled();
  await page.locator("#ownbtn").click();
  await expect(page.locator("#hynote")).toBeHidden();
  await expect(page.locator("#legtitle")).not.toHaveText(/HYSPLIT/);
});

test("the Army's zones are off until ticked", async ({ page }) => {
  await openMap(page, fixture("forecast"));
  await expect(page.locator("#showRef")).not.toBeChecked();
  await expect(page.locator("#legref")).toBeHidden();
  await page.locator("#showRef").check();
  await expect(page.locator("#legref")).toBeVisible();
});

test("EPA's sites are off until ticked, with a key, and open in the legend when tapped", async ({ page, isMobile }) => {
  const data = fixture("forecast"), sites = data.meta.sites;
  const errors = await openMap(page, data);
  await expect(page.locator("#showSites")).not.toBeChecked();
  await expect(page.locator("#legsites")).toBeHidden();
  await page.locator("#showSites").check();
  await expect(page.locator("#legsites")).toBeVisible();
  for (const k of Object.values(sites.kinds)) await expect(page.locator("#legsites")).toContainText(k.label);
  await expect(page.locator("#legsites")).toContainText("A reading near zero doesn't show");
  // from the list: the map centers on the site and its details open
  const as01 = sites.sites.find((s) => s.id === "AS01");
  await page.selectOption("#sitepick", "AS01");
  const detail = page.locator("#legsite");
  await expect(detail).toBeVisible();
  await expect(detail).toContainText("Continuous lead monitor");
  const xact = as01.readings.xact;
  await expect(detail).toContainText(`${xact.max.v.toFixed(3)} ${xact.unit}`);
  await expect(detail).toContainText(`${xact.posted} total, ${xact.zero} posted as 0`);
  // "Measurements collected" links to EPA's map, filtered to this site, in a new tab
  const src = detail.locator("dt a.srclink");
  await expect(src).toHaveText("Measurements collected · on EPA's map ↗");   // says where it goes, for phones without hover text
  await expect(src).toHaveAttribute("href", xact.url);
  await expect(src).toHaveAttribute("target", "_blank");
  expect(xact.url).toContain("data_filter=");
  expect(xact.url).toContain("%27AS01%27");
  // beside the air results: the published limit, linked to where its source is listed
  await expect(detail).toContainText("Army's published detection limit0.18 µg/m³");   // whose, in plain sight
  const limit = detail.locator("a.reflink");
  await expect(limit).toHaveAttribute("href", sites.instruments.xact.limit.url);
  await expect(limit).toHaveAttribute("title", /^Source: the Army's lead air sampling method/);
  await expect(limit).toHaveAttribute("target", "_blank");   // opened on its own; in the site, the dialog
  await expect(detail.locator(".insthead").first()).toHaveText(sites.instruments.xact.name);   // the kind's own instrument first
  await expect(detail.locator(".insthead svg")).toHaveCount(1);   // with its symbol
  await expect(detail).toContainText(sites.instruments.xact.text);
  await expect(detail).toContainText("Also here, no results posted: DustTrak, AreaRAE, Air cassette, Summa canister.");   // the rest (null), named
  await expect(detail).not.toContainText(sites.instruments.dusttrak.text);
  await expect(detail).toContainText("Measurements, not model estimates.");
  await page.locator("#siteclose").click();
  await expect(detail).toBeHidden();
  // a click or tap on the site (now at the map's center) opens it again; a drag doesn't
  await page.locator("#map").scrollIntoViewIfNeeded();
  const box = await page.locator("#map").boundingBox();
  const [cx, cy] = [box.x + box.width / 2, box.y + box.height / 2];
  if (isMobile) await page.touchscreen.tap(cx, cy);   // one finger scrolls the page: no drag here
  else {
    await page.mouse.move(cx, cy); await page.mouse.down(); await page.mouse.move(cx + 40, cy + 20); await page.mouse.up();
    await expect(detail).toBeHidden();
    await page.mouse.move(cx + 40, cy + 20); await page.mouse.down(); await page.mouse.move(cx, cy); await page.mouse.up();   // and back
    await page.mouse.click(cx, cy);
  }
  await expect(detail).toBeVisible();
  await expect(detail.locator(".sitehead")).toContainText("AS01");
  await page.locator("#showSites").uncheck();
  await expect(detail).toBeHidden();
  expect(errors).toEqual([]);
});

test("a site shows each instrument's results, and says which have none", async ({ page }) => {
  // made-up lab results for one air cassette, to stand in for results EPA hasn't posted
  const data = fixture("forecast"), sites = data.meta.sites;
  const as06 = sites.sites.find((s) => s.id === "AS06"), as01 = sites.sites.find((s) => s.id === "AS01");
  expect(as06.readings.cassette).toBeNull();
  as06.readings.cassette = { unit: "µg/m³", posted: 1, zero: 0, max: { v: 0.123, t: "2026-11-25T21:00Z" }, maxBefore: null, first: "2026-11-25T21:00Z", last: { v: 0.123, t: "2026-11-25T21:00Z" } };
  as01.readings.cassette = { unit: "µg/m³", posted: 1, zero: 1, max: { v: 0, t: "2026-11-25T21:00Z" }, maxBefore: null, first: "2026-11-25T21:00Z", last: { v: 0, t: "2026-11-25T21:00Z" } };
  const errors = await openMap(page, data);
  await page.locator("#showSites").check();
  const detail = page.locator("#legsite");
  // a filter site: the cassette is its own sample, so its results come right after its description
  await page.selectOption("#sitepick", "AS06");
  await expect(detail.locator(".insthead").first()).toHaveText("Air cassette");
  await expect(detail).toContainText("0.123 µg/m³");
  await expect(detail).toContainText("1 total, 0 posted as 0");
  await expect(detail.locator("dt", { hasText: "Measurements collected" }).locator("a")).toHaveCount(0);   // no url: plain text
  await expect(detail).toContainText("Also here, no results posted: DustTrak, AreaRAE, Summa canister.");
  await expect(detail).not.toContainText("No results posted.");
  // a lead monitor with a cassette result too: both instruments' results, the rest named
  await page.locator("#siteclose").click();
  await page.selectOption("#sitepick", "AS01");
  await expect(detail.locator("dl")).toHaveCount(2);
  await expect(detail.locator(".insthead")).toHaveText([sites.instruments.xact.name, "Air cassette"]);   // each result under its symbol and name
  await expect(detail.locator(".insthead svg")).toHaveCount(2);
  await expect(detail.locator("dt", { hasText: "Army's published detection limit" })).toHaveCount(2);   // both are lead in air
  await expect(detail).toContainText(`${as01.readings.xact.posted} total, ${as01.readings.xact.zero} posted as 0`);
  await expect(detail).toContainText("1 total, 1 posted as 0");
  await expect(detail).toContainText("Also here, no results posted: DustTrak, AreaRAE, Summa canister.");
  // a site with nothing posted says so
  await page.locator("#siteclose").click();
  const as12 = sites.sites.find((s) => s.id === "AS12");
  expect(Object.values(as12.readings).every((r) => r === null)).toBe(true);
  await page.selectOption("#sitepick", "AS12");
  await expect(detail).toContainText("No results posted.");
  await expect(detail.locator("dl")).toHaveCount(0);
  await expect(detail).not.toContainText("detection limit");   // only beside results
  expect(errors).toEqual([]);
});

test("closing a site's details: focus goes to the list, Escape closes too, and the × fits a finger", async ({ page, isMobile }) => {
  const errors = await openMap(page, fixture("forecast"));
  await page.locator("#showSites").check();
  await page.selectOption("#sitepick", "AS01");
  const close = page.locator("#siteclose");
  await expect(close).toBeFocused();   // opened from the list: focus on the ×
  const b = await close.boundingBox();
  if (isMobile) expect(Math.min(b.width, b.height)).toBeGreaterThanOrEqual(44);   // touch: a finger-sized target
  else expect(Math.min(b.width, b.height)).toBeGreaterThanOrEqual(24);   // the WCAG minimum
  expect(await page.locator(".legend").evaluate((l) => l.scrollWidth <= l.clientWidth)).toBe(true);   // no sideways scroll
  if (isMobile) { await close.scrollIntoViewIfNeeded(); const c = await close.boundingBox(); await page.touchscreen.tap(c.x + c.width / 2, c.y + c.height / 2); }
  else await close.click();
  await expect(page.locator("#legsite")).toBeHidden();
  await expect(page.locator("#legsites")).toBeVisible();
  await expect(page.locator("#sitepick")).toBeFocused();   // not lost to the page
  await expect(page.locator("#sitepick")).toBeInViewport();   // the key in view, even where the legend shrank
  // the keyboard: pick again, then Escape from inside the details
  await page.selectOption("#sitepick", "AS02");
  await expect(page.locator("#legsite")).toContainText("AS02");
  await page.keyboard.press("Escape");
  await expect(page.locator("#legsite")).toBeHidden();
  await expect(page.locator("#sitepick")).toBeFocused();
  expect(errors).toEqual([]);
});

// Center the map on a site with the list, close its details, put the map at the top of the
// screen, and return the map's center: the site's spot, ready to tap.
async function siteAtCenter(page, id) {
  if (await page.locator("#legsite").isVisible()) await page.locator("#siteclose").click();   // the list is in the key
  await page.selectOption("#sitepick", id);
  await page.locator("#siteclose").click();
  await page.evaluate(() => window.scrollTo(0, 0));
  const m = await page.locator("#map").boundingBox();
  return [m.x + m.width / 2, m.y + m.height / 2];
}

test("on a phone, a tapped site's details scroll into view, and a double tap keeps them open", async ({ page, isMobile }) => {
  test.skip(!isMobile, "taps and the details under the map are for narrow touch screens");
  const errors = await openMap(page, fixture("forecast"));
  await page.locator("#showSites").check();
  const vh = page.viewportSize().height;
  let [x, y] = await siteAtCenter(page, "AS03");
  await page.touchscreen.tap(x, y);
  const head = page.locator("#legsite .sitehead");
  await expect(head).toContainText("AS03");
  await expect.poll(async () => (await head.boundingBox()).y).toBeLessThanOrEqual(vh * 0.6);   // the heading on screen
  expect((await head.boundingBox()).y).toBeGreaterThanOrEqual(0);
  // a double tap: the second tap doesn't close what the first opened
  [x, y] = await siteAtCenter(page, "AS03");
  await page.touchscreen.tap(x, y);
  await page.touchscreen.tap(x, y);
  await page.waitForTimeout(400);
  await expect(page.locator("#legsite")).toBeVisible();
  await expect(head).toContainText("AS03");
  // a later tap on the open site closes it
  await page.evaluate(() => window.scrollTo(0, 0));
  const m = await page.locator("#map").boundingBox();
  await page.touchscreen.tap(m.x + m.width / 2, m.y + m.height / 2);
  await expect(page.locator("#legsite")).toBeHidden();
  expect(errors).toEqual([]);
});

test("crowded labels: some are left out at a wide zoom, all are back zoomed in", async ({ page }) => {
  const errors = await openMap(page, fixture("forecast"));
  await page.locator("#showSites").check();
  await siteAtCenter(page, "AS02");
  for (let i = 0; i < 5; i++) await page.locator("#zout").click();   // the monitors crowd together
  const labels = async () => (await page.locator("#map").getAttribute("data-site-labels")).split("/").map(Number);
  await expect.poll(async () => { const [shown, wanted] = await labels(); return shown < wanted && shown >= 1; }).toBe(true);
  for (let i = 0; i < 7; i++) await page.locator("#zin").click();   // zoomed in: room for every label on screen
  await expect.poll(async () => { const [shown, wanted] = await labels(); return wanted >= 1 && shown === wanted; }).toBe(true);
  expect(errors).toEqual([]);
});

test("every \"Measurements collected\" link opens EPA's map in a new tab, by tap, click or Enter", async ({ page, isMobile }) => {
  const data = fixture("forecast");
  // the new tab is another page: answer EPA's address with a stub, so the test stays offline
  await page.context().route("https://experience.arcgis.com/**", (r) => r.fulfill({ contentType: "text/html", body: "<title>stub</title>" }));
  const errors = await openMap(page, data);
  await page.locator("#showSites").check();
  const linked = data.meta.sites.sites.filter((s) => Object.values(s.readings || {}).some((r) => r && r.url));
  expect(linked.map((s) => s.id)).toEqual(["AS01", "AS02", "AS03", "AS04"]);
  for (const s of linked) {
    for (const how of ["pointer", "Enter"]) {
      if (await page.locator("#legsite").isVisible()) await page.locator("#siteclose").click();
      await page.selectOption("#sitepick", s.id);
      const link = page.locator("#legsite a.srclink");
      await expect(link).toHaveAttribute("target", "_blank");
      await expect(link).toHaveAttribute("rel", /noopener/);
      if (isMobile) for (const a of [link, page.locator("#legsite a.reflink").first()])   // finger-sized, not overlapping
        expect((await a.boundingBox()).height).toBeGreaterThanOrEqual(44);
      await link.scrollIntoViewIfNeeded();
      const before = page.url();
      const act = async () => {
        if (how === "Enter") { await link.focus(); await page.keyboard.press("Enter"); }
        else if (isMobile) { const b = await link.boundingBox(); await page.touchscreen.tap(b.x + b.width / 2, b.y + b.height / 2); }
        else await link.click();
      };
      const [tab] = await Promise.all([page.context().waitForEvent("page"), act()]);
      await tab.waitForLoadState("domcontentloaded");
      expect(tab.url()).toBe(s.readings.xact.url);   // EPA's map, filtered to this site
      expect(page.url()).toBe(before);   // the map stays where it was
      await expect(page.locator("#legsite .sitehead")).toContainText(s.id);   // with the site still open
      await tab.close();
    }
  }
  expect(errors).toEqual([]);
});

test("Escape closes a site opened by a click, and closing from the map keeps keyboard focus", async ({ page, isMobile }) => {
  test.skip(isMobile, "pointer clicks and the keyboard");
  const errors = await openMap(page, fixture("forecast"));
  await page.locator("#showSites").check();
  // opened by a click on the map: focus isn't in the details, Escape still closes them
  let [x, y] = await siteAtCenter(page, "AS02");
  await page.mouse.click(x, y);
  await expect(page.locator("#legsite .sitehead")).toContainText("AS02");
  await page.keyboard.press("Escape");
  await expect(page.locator("#legsite")).toBeHidden();
  // picked from the list (focus on the ×), then closed by a click on the open site: focus to the list
  await page.selectOption("#sitepick", "AS02");
  await expect(page.locator("#siteclose")).toBeFocused();
  [x, y] = await (async () => { const m = await page.locator("#map").boundingBox(); return [m.x + m.width / 2, m.y + m.height / 2]; })();
  await page.waitForTimeout(400);   // past a double click's time
  await page.mouse.click(x, y);
  await expect(page.locator("#legsite")).toBeHidden();
  await expect(page.locator("#sitepick")).toBeFocused();
  // the same with a click on empty map
  await page.selectOption("#sitepick", "AS02");
  await page.mouse.click(x - 200, y - 150 > 0 ? y - 150 : y + 150);
  await expect(page.locator("#legsite")).toBeHidden();
  await expect(page.locator("#sitepick")).toBeFocused();
  expect(errors).toEqual([]);
});

test("a site's counts go into the page as text, not markup", async ({ page }) => {
  const data = fixture("forecast");
  const as01 = data.meta.sites.sites.find((s) => s.id === "AS01");
  as01.readings.xact.posted = "<b id=injected>84</b>";   // the build refuses this; the page must not trust it either
  const errors = await openMap(page, data);
  await page.locator("#showSites").check();
  await page.selectOption("#sitepick", "AS01");
  await expect(page.locator("#legsite")).toContainText("<b id=injected>84</b> total");
  await expect(page.locator("#injected")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("deposition opens at the map's minimum, with a box that brings lower values back", async ({ page }) => {
  await openMap(page, fixture("forecast"));   // built with --dep-scale-min 5ug/ft2
  await page.locator('#fieldseg button[data-v="dep"]').click();
  await expect(page.locator("#fixtopwrap")).toBeVisible();
  await expect(page.locator("#fixtop")).toBeChecked();
  await expect(page.locator("#fixtoplabel")).toHaveText("show only ≥ 5 µg/ft²");
  await page.locator('#fieldseg button[data-v="conc"]').click();   // air has its own minimum
  await expect(page.locator("#fixtoplabel")).toHaveText(/^show only ≥ [\d.]+ µg\/m³$/);
});

test("opened on its own, the map says it's an unofficial estimate", async ({ page }) => {
  const data = fixture("forecast");
  await openMap(page, data);
  await expect(page.locator("#standalone")).toBeVisible();
  await expect(page.locator("#standalone")).toContainText("Unofficial estimate, not from the Army or any government agency");
  await expect(page.locator("#legnote")).toContainText("Unofficial estimate");
});

test("the panel's peak values are the data's, in the units chosen", async ({ page }) => {
  const data = fixture("forecast");
  await openMap(page, data);
  const h = data.hours[0];   // hour 1; kg/m³ and kg/m² in the data
  const dd = (label) => page.locator("#peak dt", { hasText: label }).locator("xpath=following-sibling::dd[1]");
  // the map was built for U.S. units: deposition in µg/ft², air in µg/m³
  await expect(dd("Air, hourly mean")).toHaveText(/µg\/m³$/);
  const air = num(await dd("Air, hourly mean").textContent());
  expect(Math.abs(air / (h.cmax * 1e9) - 1)).toBeLessThan(0.01);
  await expect(dd("Deposition")).toHaveText(/µg\/ft²$/);
  const ugft2 = num(await dd("Deposition").textContent());
  expect(Math.abs(ugft2 / (h.dmax * 1e9 * 0.09290304) - 1)).toBeLessThan(0.01);
  await page.locator('#sysseg button[data-v="metric"]').click();
  await expect(dd("Deposition")).toHaveText(/µg\/m²$/);
  const ugm2 = num(await dd("Deposition").textContent());
  expect(Math.abs(ugm2 / (h.dmax * 1e9) - 1)).toBeLessThan(0.01);
});

test("the levels-of-concern inputs follow the units", async ({ page }) => {
  await openMap(page, fixture("forecast"));   // built for U.S. units
  await page.locator('#fieldseg button[data-v="zones"]').click();
  await page.selectOption("#zmetric", "dep");
  await expect(page.locator("#zonenote")).toContainText("Levels in µg/ft².");
  await page.locator('#sysseg button[data-v="metric"]').click();
  await expect(page.locator("#zonenote")).toContainText("Levels in µg/m².");
  await page.selectOption("#zmetric", "m60");
  await expect(page.locator("#zonenote")).toContainText("Levels in µg/m³.");
  await page.selectOption("#units", "mass");                 // no fixed unit: mg
  await expect(page.locator("#zonenote")).toContainText("Levels in mg/m³.");
});

test("hovering the levels of concern gives mass, even with particle counts chosen", async ({ page, isMobile }) => {
  test.skip(isMobile, "hover needs a mouse");
  await openMap(page, fixture("forecast"));
  await page.selectOption("#units", "count");
  await page.locator('#fieldseg button[data-v="zones"]').click();
  await page.locator("#hour").fill("8");
  const box = await page.locator("#map").boundingBox();
  let text = "";
  // look for a cell the cloud reached: scan the map until the tip shows a value
  for (let y = 0.2; y <= 0.8 && !/so far: \d/.test(text); y += 0.05) {
    for (let x = 0.2; x <= 0.8 && !/so far: \d/.test(text); x += 0.05) {
      await page.mouse.move(box.x + box.width * x, box.y + box.height * y);
      text = (await page.locator("#tip").textContent()) || "";
    }
  }
  expect(text, "no scanned point reached a cell the cloud reached").toMatch(/so far: \d/);
  // a mass in a readable unit (metric, or U.S. ounces, pounds, tons for big amounts), not particles
  // (big numbers may be written ×10⁴ and up; a negative power would mean a too-large unit)
  expect(text).toMatch(/so far: [\d.,]+(?:×10[⁰-⁹]+)? (?:[mµnpfk]?g|t|oz|lb|tons)\/m[²³]/);
  await expect(page.locator("#units")).toHaveValue("count");   // the choice is untouched
});

test("the air minimum's label follows the units", async ({ page }) => {
  await openMap(page, fixture("forecast"));   // built with --scale-min 0.15ug (per m³)
  const label = page.locator("#fixtoplabel");
  await expect(label).toHaveText("show only ≥ 0.15 µg/m³");
  await page.selectOption("#units", "cm3");
  await expect(label).toHaveText("show only ≥ 1.5×10⁻⁷ µg/cm³");   // 1 m³ = 10⁶ cm³
  await page.selectOption("#units", "mass");   // no fixed unit: the legend's, picked by size
  const unit = (await page.locator("#legtitle").textContent()).match(/\(([^)]+)\)$/)[1];
  await expect(label).toHaveText(new RegExp(`^show only ≥ [\\d.,]+ ${unit.replace("/", "\\/")}$`));
  await page.locator('#fieldseg button[data-v="dep"]').click();   // deposition: its own minimum, same rule
  const depUnit = (await page.locator("#legtitle").textContent()).match(/\(([^)]+)\)$/)[1];
  await expect(label).toHaveText(new RegExp(`^show only ≥ [\\d.,]+ ${depUnit.replace("/", "\\/")}$`));
});

test("text from the data can't inject markup or script", async ({ page }) => {
  const data = fixture("forecast");
  const evil = '<img src=x onerror="window.__xss=1">';
  data.meta.title = evil;
  data.meta.outlines.name = evil;
  data.meta.outlines.links = [{ url: "javascript:window.__xss=1", text: evil }];
  data.hours.forEach((h) => { h.stab = evil; });
  if (data.meta.explosionOpts) data.meta.explosionOpts.layers = evil;
  const errors = await openMap(page, data);
  await expect(page.locator("#title")).toHaveText(evil);           // shown as text
  await page.locator("#showRef").check();
  await expect(page.locator("#legref")).toContainText(evil);
  for (const id of ["#legref", "#met", "#expl", "#title"]) await expect(page.locator(`${id} img`)).toHaveCount(0);
  await expect(page.locator('#legref a[href^="javascript:"]')).toHaveCount(0);
  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
  expect(errors).toEqual([]);
});

test("the attribution follows the basemap", async ({ page }) => {
  await openMap(page, fixture("forecast"));
  await page.selectOption("#basemap", "none");
  await expect(page.locator("#attrib")).toHaveText("Weather: Open-Meteo");
  await page.selectOption("#basemap", "light");
  await expect(page.locator("#attrib")).toContainText("©");
  await expect(page.locator("#attrib")).toContainText("Weather: Open-Meteo");
});

test("switching to dark mode redraws the map", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await openMap(page, fixture("forecast"));
  // the canvas's own pixels: a screenshot would change with the page's dark CSS alone
  const pixels = () => page.locator("#map").evaluate((c) => c.toDataURL());
  const light = await pixels();
  await page.emulateMedia({ colorScheme: "dark" });
  await expect.poll(pixels).not.toBe(light);
});

test("saved basemap and unit choices are used", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("puffmap.prefs", JSON.stringify({ base: "none", sys: "metric" })));
  await openMap(page, fixture("forecast"));
  await expect(page.locator("#basemap")).toHaveValue("none");
  await expect(page.locator('#sysseg button[data-v="metric"]')).toHaveAttribute("aria-pressed", "true");
});

test("bad saved data is ignored, and #u= picks the units", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("puffmap.prefs", "{not json"));
  const errors = await openMap(page, fixture("forecast"), "#u=metric");
  await expect(page.locator('#sysseg button[data-v="metric"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#basemap")).toHaveValue("auto");
  expect(errors).toEqual([]);
});

test("the page fits the screen, with the legend below the map on narrow screens", async ({ page, isMobile }) => {
  await openMap(page, fixture("forecast"));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const below = await page.evaluate(() => {
    const legend = document.querySelector(".legend");
    return { cls: legend.classList.contains("below"), inMap: document.getElementById("mapwrap").contains(legend) };
  });
  expect(below).toEqual(isMobile ? { cls: true, inMap: false } : { cls: false, inMap: true });
});

test("no accessibility violations (axe, WCAG 2.1 A and AA)", async ({ page }) => {
  for (const name of ["forecast", "archived"]) {
    await openMap(page, fixture(name));
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(r.violations.map((v) => `${name}: ${v.id}: ${v.help} (${v.nodes.length}): ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  }
});
