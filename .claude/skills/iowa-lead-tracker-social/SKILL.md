---
name: "iowa-lead-tracker-social"
description: "Make Instagram Story videos, a Facebook image and a comparison caption from the latest Iowa Lead Tracker (iowaleadtracker.com) forecast update."
---

# Iowa Lead Tracker social assets

The social media manager posts for iowaleadtracker.com, an unofficial open model of where lead from the Army's lead azide detonation at the Iowa Army Ammunition Plant could travel and settle. After each site update the social media manager wants three files plus a caption:

1. **Close-up Story video** (1080×1920): "Levels of concern" near the plant, 1, 2 and 3 p.m., then a hold labeled 8 p.m.
2. **Zoomed-out Story video** (1080×1920): "Levels of concern" with weather-model spread on, 1 to 8 p.m.
3. **Facebook image** (1080×1350): the 8 p.m. spread map plus a "What changed" table comparing the previous update with this one.
4. **Caption** that compares the two updates, with at most 5 hashtags.
5. **Optional three-case post**, when the social media manager asks to compare airborne-share assumptions (e.g. EPA permit 100%, high 55%, middle 20%): a Story video and a Facebook image from one forecast. See "Three-case comparison post" below.
6. **Optional side-by-side day post**, when the site models more than one blast day (e.g. Monday vs. Tuesday): a Story video with both days in one frame, plus a Facebook image. Use the weather-model spread view. See "Side-by-side day comparison" below.

## Requirements
- The workspace must reach iowaleadtracker.com and Esri's tile servers (server.arcgisonline.com, services.arcgisonline.com). The social media manager has set Settings > Capabilities > Allowed websites to "Any website". If a request is refused, tell the social media manager which domain and stop. Don't try another route.
- Headless Chrome is at /usr/bin/google-chrome, and Python Playwright is installed. If either is missing, `pip install --break-system-packages playwright`, then use the system Chrome.
- Don't run code from the iowaleadtracker GitHub repo. Capture the live site instead.

## Steps

1. **Read the update.** Write `sitetext.py` (below) and run it. Note: update time, forecast-pulled time, number of models, default model, wind and direction, miles by 8 p.m., the EPA permit row of the table (yellow, orange and red reach), peak one-hour air for the EPA permit case, towns in the yellow area, and the court/timing paragraph.
2. **Get the previous numbers** from the last caption or Facebook table in the conversation (or ask). Build up to 6 comparison rows: wind, path, yellow reach, orange reach, red reach, peak air near the plant.
3. **Check the status line.** Always search the news first: timing has been changing day to day. As of Nov. 22: the Army told the 8th Circuit it plans to act by Tue., Nov. 24 under an emergency rule even with EPA's permit on hold, and the court ordered EPA to respond by noon Sunday. Default: `Army says it will act by Tue., Nov. 24. Court ruling pending.` If a court ruling or Army announcement changed things, rewrite it. Keep it to one line, about 60 characters.
4. **Write `config.json`** with: outdir (a new folder per run), stamp (e.g. `nov22-0615am`), updated (e.g. `Nov. 22, 6:15 a.m.`), status_line, scenario (the Facebook subtitle, matching the day and time the site models, e.g. `Where lead could settle if it happens Mon., Nov. 23, at about noon`), models, direction (the site's "cloud heads ..." wording, e.g. `southeast`), fb_kicker (e.g. `UPDATED SUN., NOV. 22, 6:15 A.M.`), prev_label, new_label, rows.
5. **Run** `python3 make_assets.py config.json`. It takes about 1 minute. Use `--no-capture` to recompose without re-capturing.
6. **Check before sending.** Open `frames/story_wide_8.png`, `frames/story_close_3.png` and the Facebook PNG. Check that the release point and plume are fully in frame and no text covers the plume. Compare `frames/close_3.jpg` and `frames/close_8.jpg`. If the close-up still changes after 3 p.m. (the path is slow or short), change the hold label instead of saying "no change here after 3 p.m.".
7. **Send** the two MP4s and the PNG with SendUserFile, then give the caption.

## Voice and tone (social media manager's feedback)
- **Plain, local and active voice.** Write like a neighbor explaining the map, not a press release or an AI. Make the wind and the cloud the subjects: "A 12 mph northwest wind pushes the cloud southeast." "Lead on the ground hits the red level out to 10 miles." Keep sentences short.
- **Neutral third person.** Never write "I", "my" or "we". Call the site "the Iowa Lead Tracker, a community model". The disclaimer reads: "This is an unofficial estimate, not the Army's or any agency's."
- **Avoid AI-sounding patterns:** "changes everything", "Here's", "In plain English:", "Why is X? ..." setups, "not a line, a range"-style contrasts, "Treat this as...", and stacked labels with colons.
- **Keep the emojis at the start of lines** so the caption is copy-paste ready: 🌬️ on the hook, 📅 for each day, 🔴 🟠 🟡 for the zones, 🌫️ for lead in the air, 🧭 for the explanation, ⚠️ for the disclaimer.
- **Explain the why in one or two plain sentences.** For example: a strong wind spreads lead thin over a long distance, while a light wind leaves more close to home. When the wind barely blows, small differences between forecasts turn the cloud different ways, so the models fan out.
- **Deliver the final caption as one clean block** with nothing inside it but the post. Put any notes for the social media manager after a divider.

## Caption rules
- Open with a hook line that fits before Instagram's "more" cutoff, e.g. "Monday or Tuesday makes a big difference. 🌬️". Don't name a single day the Army hasn't committed to; as of Nov. 22 say "Monday or Tuesday". Say which day and time the map models (the site's day and blast-time settings).
- Say when the site updated, when the forecast was pulled, how many models it uses and which is the default. If the default model changed since last time, say so: part of the change comes from the switch.
- Give each comparison point its own emoji line, written as a plain active sentence (📅 wind and path, 🔴 red, 🟠 orange, 🟡 yellow, 🌫️ peak air), then one plain sentence on what it means.
- Give the current timing and court status from the site and news, attributed (Iowa HHS, the 8th Circuit, the Justice Department). Never say the blast will or won't happen.
- Always include: unofficial estimate, EPA permit worst case (100% of the lead airborne), don't use it to judge your safety, follow the Army, county emergency management and Iowa HHS.
- End with `Map: iowaleadtracker.com (updated <time>)` and at most 5 hashtags. Default: #IowaArmyAmmunitionPlant #Burlington #SoutheastIowa #WesternIllinois #StLouis. Swap regional tags if the path changes, e.g. #Quincy or #Hannibal for a southward path.
- Stay under Instagram's 2,200-character limit (aim for about 1,200).

## sitetext.py
```python
import asyncio, re, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = await b.new_page()
        await pg.goto("https://iowaleadtracker.com/?nc=t", wait_until="networkidle", timeout=60000)
        t = await pg.locator("body").inner_text()
        g = lambda pat: (re.search(pat, t) or [None])[0]
        out = {
          "updated": g(r"Last updated [^.]*?\d{4}, at [\d:]+ [ap]\.m\."),
          "forecast": g(r"Forecast pulled [^;]*?models?; the map shows \w+"),
          "winds": g(r"Winds near the ground at blast time are forecast from [^.]+\.[^.]*\."),
          "by8": g(r"by 8:00 p\.m\. about [\d,]+ miles[^.(]*"),
          "towns": g(r"In the EPA permit case \(the map’s default\), the model’s yellow area reaches[^.]*\."),
          "air": g(r"The highest one-hour average of lead in the air is about [^.]*\."),
          "timing": g(r"As of this update \([^)]*\), the Army [^.]*\."),
          "court": g(r"Late on Nov\. 19[^.]*\.[^.]*\.[^.]*\.")}
        for tb in await pg.locator("table").all():
            x = await tb.inner_text()
            if "Yellow" in x: out["table"] = x.replace("\n", " | ")
        print(json.dumps(out, indent=1, ensure_ascii=False)); await b.close()
asyncio.run(main())
```

## make_assets.py
How it works: it opens the site at a 720×1280 phone viewport in dark mode and hides the zoom buttons. It finds the bright-red release marker by pixel color and drags the map so the release point lands where the plume fits, based on `direction`. Wide view: Fit plume, zoom out 1, spread on. Close-up: Fit plume, center the plant, zoom in 2, spread off. It sets the hour slider directly and captures JPEGs. Then it composes Story frames that keep all text inside Instagram's safe zone (nothing above y≈260 or below y≈1700) and renders with ffmpeg crossfades.

```python
#!/usr/bin/env python3
import asyncio, json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

URL = "https://iowaleadtracker.com/"
VW, VH = 720, 1280
MAP_BOTTOM = 950

def _font(names, size):
    for n in names:
        for d in ("/usr/share/fonts/opentype/inter/", "/usr/share/fonts/truetype/dejavu/"):
            p = d + n
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()
bold = lambda s: _font(["Inter-Bold.otf", "DejaVuSans-Bold.ttf"], s)
semi = lambda s: _font(["Inter-SemiBold.otf", "DejaVuSans-Bold.ttf"], s)
reg = lambda s: _font(["Inter-Regular.otf", "DejaVuSans.ttf"], s)

BG, AMBER, GOLD, GREY = (31, 31, 29), (240, 150, 100), (255, 210, 120), (205, 205, 205)
LEVELS = [("Red", (187, 77, 64), "≥100"), ("Orange", (213, 140, 99), "≥40"), ("Yellow", (233, 182, 57), "≥5 µg/ft²")]

COMPASS = {"north": 0, "north-northeast": 22.5, "northeast": 45, "east-northeast": 67.5, "east": 90,
           "east-southeast": 112.5, "southeast": 135, "south-southeast": 157.5, "south": 180,
           "south-southwest": 202.5, "southwest": 225, "west-southwest": 247.5, "west": 270,
           "west-northwest": 292.5, "northwest": 315, "north-northwest": 337.5}

def target_for(direction, center, offset):
    ang = math.radians(COMPASS.get(direction.strip().lower(), 180))
    dx, dy = math.sin(ang), -math.cos(ang)
    return (round(center[0] - dx * offset), round(center[1] - dy * offset))

def find_release(path):
    im = Image.open(path).convert("RGB"); px = im.load()
    W, H = im.size
    pts = [(x, y) for y in range(0, min(MAP_BOTTOM, H)) for x in range(W)
           if px[x, y][0] > 210 and px[x, y][1] < 100 and px[x, y][2] < 100]
    if len(pts) < 8:
        return None
    xs = sorted(p[0] for p in pts); ys = sorted(p[1] for p in pts)
    return xs[len(xs) // 2], ys[len(ys) // 2]

async def capture(cfg, fdir):
    from playwright.async_api import async_playwright
    exe = next((p for p in ("/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser") if os.path.exists(p)), None)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=1, color_scheme="dark")
        pg = await ctx.new_page()
        await pg.goto(URL + "?nc=" + cfg["stamp"], wait_until="networkidle", timeout=90000)
        ok = pg.get_by_role("button", name="OK")
        if await ok.count():
            await ok.first.click()
        fr = pg.frame(name="map")

        async def scroll_map():
            top = await pg.locator("main iframe").evaluate("e => e.getBoundingClientRect().top + window.scrollY")
            await pg.evaluate(f"window.scrollTo(0, {top})"); await pg.wait_for_timeout(600)

        async def js_button(name):
            loc = fr.locator(f'button[aria-label="{name}"]')
            if not await loc.count():
                loc = fr.get_by_role("button", name=name, exact=True)
            await loc.first.evaluate("b => b.click()")
            await pg.wait_for_timeout(1500)

        async def shot(name):
            await scroll_map()
            path = os.path.join(fdir, name)
            await pg.screenshot(path=path, type="jpeg", quality=92)
            return path

        async def hour(h):
            await fr.locator("input[type=range]").first.evaluate(
                "(e, v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); }", str(h))
            await pg.wait_for_timeout(1500)

        async def spread(on):
            cb = fr.get_by_label("weather-model spread", exact=False).first
            if (await cb.is_checked()) != on:
                await cb.evaluate("e => e.click()"); await pg.wait_for_timeout(1500)

        async def place_release(target):
            for _ in range(3):
                pos = find_release(await shot("_probe.jpg"))
                if not pos:
                    raise SystemExit("Could not find the release marker on the map.")
                dx, dy = target[0] - pos[0], target[1] - pos[1]
                if abs(dx) < 6 and abs(dy) < 6:
                    return pos
                sx, sy = 360, 520
                await pg.mouse.move(sx, sy); await pg.mouse.down()
                await pg.mouse.move(sx + dx, sy + dy, steps=15); await pg.mouse.up()
                await pg.wait_for_timeout(1200)
            return pos

        await scroll_map(); await pg.wait_for_timeout(1500)
        await fr.evaluate("""() => document.querySelectorAll('button').forEach(b => {
            const l = b.getAttribute('aria-label') || '';
            if (/^(Zoom in|Zoom out|Fit plume)$/.test(l)) b.style.visibility = 'hidden'; })""")
        await js_button("Levels of concern")
        d = cfg.get("direction", "south")
        await js_button("Fit plume"); await js_button("Zoom out")
        await spread(True)
        await place_release(target_for(d, (360, 470), 120))
        for h in range(1, 9):
            await hour(h); await shot(f"wide_{h}.jpg")
        await spread(False)
        await js_button("Fit plume")
        await place_release((360, 475))
        await js_button("Zoom in"); await js_button("Zoom in")
        await place_release(target_for(d, (360, 495), 230))
        for h in (1, 2, 3, 8):
            await hour(h); await shot(f"close_{h}.jpg")
        await b.close()

def small_note(kicker, cfg):
    if kicker.startswith("WEATHER"):
        return f"Shading = highest of {cfg['models']} weather models. Dashed lines = each model's path."
    return "Shading = main forecast model. Dashed line = the cloud's center, by hour."

def story_frame(src, out, kicker, big, small, cfg):
    W, H, X = 1080, 1920, 60
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    s = Image.open(src).convert("RGB")
    mp = s.crop((0, 205, 720, 785)).resize((1080, 870), Image.LANCZOS)
    d.text((X, 272), kicker, font=semi(30), fill=AMBER)
    d.text((X, 310), "Iowa Army Ammunition Plant", font=bold(54), fill="white")
    d.text((X, 374), big, font=bold(66), fill="white")
    d.text((X + d.textlength(big, font=bold(66)) + 22, 398), small, font=reg(32), fill=GREY)
    d.text((X, 456), cfg["status_line"], font=semi(29), fill=GOLD)
    im.paste(mp, (0, 505))
    y, x = 1392, X
    for name, col, lvl in LEVELS:
        d.rounded_rectangle((x, y + 6, x + 26, y + 32), radius=5, fill=col); x += 38
        d.text((x, y), name, font=semi(28), fill="white"); x += d.textlength(name, font=semi(28)) + 10
        d.text((x, y), lvl, font=reg(28), fill=GREY); x += d.textlength(lvl, font=reg(28)) + 34
    d.text((X, y + 44), small_note(kicker, cfg), font=reg(25), fill=GREY)
    y = 1500
    d.text((X, y), "Unofficial estimate — not from the Army or any agency.", font=semi(31), fill=GOLD)
    d.text((X, y + 44), "EPA permit case (100% airborne) · EPA indoor dust-lead levels", font=reg(29), fill=(225, 225, 225))
    d.text((X, y + 82), "Don't use this to judge safety. Follow official instructions.", font=reg(29), fill=(225, 225, 225))
    d.text((X, y + 130), f"iowaleadtracker.com · updated {cfg['updated']} · weather: Open-Meteo", font=reg(24), fill=(165, 165, 165))
    d.text((X, y + 162), "Map tiles © Esri and its data providers, © OpenStreetMap contributors", font=reg(24), fill=(165, 165, 165))
    im.save(out)

def is_shade(p):
    r, g, b = p
    return r > 120 and r - b > 60 and g > 60

def plume_crop(s, h):
    px = s.load()
    ys = [y for y in range(0, MAP_BOTTOM, 4) if any(is_shade(px[x, y]) for x in range(0, VW, 6))]
    if not ys:
        return 232, "left"
    top, bot = min(ys), max(ys)
    y0 = max(0, min(MAP_BOTTOM - h, (top + bot) // 2 - h // 2))
    if bot - top > h - 40:
        y0 = max(0, min(MAP_BOTTOM - h, bot + 30 - h))
    band = range(y0 + h - 120, y0 + h)
    left = sum(1 for y in band for x in range(0, 310, 4) if is_shade(px[x, y]))
    right = sum(1 for y in band for x in range(410, VW, 4) if is_shade(px[x, y]))
    return y0, ("right" if right < left else "left")

def fb_image(src, out, cfg):
    W, H, X = 1080, 1350, 50
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((X, 36), "LEAD PLUME FORECAST · " + cfg["fb_kicker"], font=semi(26), fill=AMBER)
    d.text((X, 72), "Iowa Army Ammunition Plant blast", font=bold(52), fill="white")
    d.text((X, 140), cfg.get("scenario", "Where lead could settle if it happens Mon., Nov. 23, at about noon"), font=reg(28), fill=GREY)
    s = Image.open(src).convert("RGB")
    MY, MH = 192, 699
    y0, side = plume_crop(s, 466)
    im.paste(s.crop((0, y0, 720, y0 + 466)).resize((1080, MH), Image.LANCZOS), (0, MY))
    lw, lh = 420, 146
    lx, ly = (W - lw - 24 if side == "right" else 24), MY + MH - 166
    box = Image.new("RGBA", (lw, lh), (20, 20, 20, 215)); im.paste(box, (lx, ly), box)
    d = ImageDraw.Draw(im); yy = ly + 14
    for name, col, lvl in LEVELS:
        d.rounded_rectangle((lx + 16, yy + 4, lx + 38, yy + 26), radius=4, fill=col)
        d.text((lx + 50, yy), name, font=semi(24), fill="white")
        d.text((lx + 150, yy), lvl.replace("≥", "≥ ") + ("" if "µg" in lvl else " µg/ft²"), font=reg(24), fill=GREY)
        yy += 34
    d.text((lx + 16, yy + 2), f"Shading: highest of {cfg['models']} weather models", font=reg(20), fill=GREY)
    ty = MY + MH + 22; cols = [X, 430, 750]
    d.text((cols[0], ty), "What changed", font=semi(26), fill=AMBER)
    d.text((cols[1], ty), cfg["prev_label"], font=semi(26), fill=GREY)
    d.text((cols[2], ty), cfg["new_label"], font=semi(26), fill="white")
    ry = ty + 44
    for i, (a, b_, c) in enumerate(cfg["rows"][:6]):
        if i % 2 == 0:
            d.rectangle((X - 14, ry - 6, W - X + 14, ry + 34), fill=(40, 40, 38))
        d.text((cols[0], ry), a, font=reg(25), fill=GREY)
        d.text((cols[1], ry), b_, font=reg(25), fill=GREY)
        d.text((cols[2], ry), c, font=semi(25), fill="white")
        ry += 40
    fy = ry + 14
    d.text((X, fy), "Unofficial estimate — not from the Army or any agency. Worst-case EPA permit", font=semi(23), fill=GOLD)
    d.text((X, fy + 30), "case (100% of the lead airborne). Follow official instructions.", font=semi(23), fill=GOLD)
    d.text((X, fy + 68), "iowaleadtracker.com · Map tiles © Esri, © OpenStreetMap contributors · Weather: Open-Meteo", font=reg(19), fill=(150, 150, 150))
    im.save(out)

def render(frames, durs, fades, out):
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for f, t in zip(frames, durs):
        args += ["-framerate", "30", "-loop", "1", "-t", str(t), "-i", f]
    fc, prev, off = [], "[0:v]", 0.0
    for k in range(1, len(frames)):
        off += durs[k - 1] - fades[k - 1]
        fc.append(f"{prev}[{k}:v]xfade=transition=fade:duration={fades[k-1]}:offset={off:.2f}[v{k}]"); prev = f"[v{k}]"
    fc.append(f"{prev}format=yuv420p[out]")
    tmp = out[:-4] + ".tmp.mp4"
    args += ["-filter_complex", ";".join(fc), "-map", "[out]", "-r", "30", "-c:v", "libx264", "-crf", "18",
             "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp]
    subprocess.run(args, check=True); os.replace(tmp, out)

def main():
    cfg = json.load(open(sys.argv[1]))
    od = cfg["outdir"]; fdir = os.path.join(od, "frames"); os.makedirs(fdir, exist_ok=True)
    if "--no-capture" not in sys.argv:
        asyncio.run(capture(cfg, fdir))
    st = cfg["stamp"]
    wide = []
    for h in range(1, 9):
        o = os.path.join(fdir, f"story_wide_{h}.png")
        story_frame(os.path.join(fdir, f"wide_{h}.jpg"), o, f"WEATHER-MODEL SPREAD · {cfg['models']} FORECASTS",
                    f"By {h} p.m.", "where lead could settle", cfg)
        wide.append(o)
    render(wide, [2.0] + [1.5] * 6 + [4.5], [0.6] * 7, os.path.join(od, f"iaap-model-spread-{st}.mp4"))
    close = []
    for h, big, small in [(1, "By 1 p.m.", "where lead could settle"), (2, "By 2 p.m.", "where lead could settle"),
                          (3, "By 3 p.m.", "where lead could settle"), (8, "By 8 p.m.", "no change here after 3 p.m.")]:
        o = os.path.join(fdir, f"story_close_{h}.png")
        story_frame(os.path.join(fdir, f"close_{h}.jpg"), o, "LEVELS OF CONCERN · CLOSE-UP NEAR THE PLANT", big, small, cfg)
        close.append(o)
    render(close, [2.2, 2.2, 2.2, 4.5], [0.9, 0.9, 0.5], os.path.join(od, f"iaap-closeup-timelapse-{st}.mp4"))
    fb_image(os.path.join(fdir, "wide_8.jpg"), os.path.join(od, f"iaap-lead-forecast-fb-{st}.png"), cfg)
    print("done:", od)

if __name__ == "__main__":
    main()
```

## Three-case comparison post
Use when the social media manager wants to show how much the airborne-share assumption matters. All three maps use the same forecast. Each case loads a fresh map with the same default view, so identical steps frame them identically.

1. Run `sitetext.py`. From the table and the "highest one-hour average" sentence, take yellow, orange and red reach plus peak air for each case. Lead airborne: low ~480 lb, middle ~1,400, high ~3,800, EPA permit ~6,900.
2. Write `cases.json`, then save `cases_post.py` (below) in the same folder as `make_assets.py` and run `python3 cases_post.py cases.json`. It takes about 2 minutes. `--no-capture` recomposes only.
3. It outputs `iaap-airborne-cases-story-<stamp>.mp4`: the regional view for each case, then the close-up near the plant for each, all at 8 p.m. It also outputs `iaap-airborne-cases-fb-<stamp>.png`: three maps, a reach table and a "What the Army expects" box.
4. **What the Army expects:** state only what's on record. EPA's permit makes the Army's official maps assume 100% airborne. EPA calls that conservative and says the Army expects the real release to be less. No Army percentage has been published (checked Nov. 22). Search again before each post, and update `army_note` if the Army gives a number.
5. **Caption:** lead with what the Army expects. Then one emoji line per zone showing permit → high → middle (🔴 red, 🟠 orange, 🟡 yellow, 🌫️ peak air), and one sentence on what changes most. Note that soaking and misting aim to keep lead on site, which points toward the lower cases. Add timing/court status, the unofficial-estimate warning, and at most 5 hashtags. Use #LeadAzide in place of #StLouis when the lower cases fall well short of St. Louis.

`cases.json` example:
```json
{"outdir": "/home/claude/out/cases-nov22", "stamp": "nov22-0735am", "updated": "Nov. 22, 7:35 a.m.",
 "status_line": "EPA's permit assumes 100%. The Army expects less.",
 "scenario": "if the blast is Mon. at noon",
 "army_note": ["EPA's permit makes the Army's official maps assume 100% of the lead",
               "gets into the air. EPA calls that conservative and says the Army expects",
               "the real release to be less. The Army hasn't said how much less."],
 "cases": [
  {"key": "permit", "label": "EPA permit", "share": "100%", "yellow": "143 mi", "orange": "27 mi", "red": "13 mi", "air": "908", "lb": "6,900"},
  {"key": "high", "label": "High", "share": "55%", "yellow": "96 mi", "orange": "15 mi", "red": "9.7 mi", "air": "500", "lb": "3,800"},
  {"key": "mid", "label": "Middle", "share": "20%", "yellow": "49 mi", "orange": "9.3 mi", "red": "5.8 mi", "air": "182", "lb": "1,400"}]}
```
Case keys on the site's "Lead in the air" menu: `low`, `mid`, `high`, `permit`.

### cases_post.py
```python
#!/usr/bin/env python3
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_assets import find_release, bold, semi, reg, BG, AMBER, GOLD, GREY, LEVELS, render
from PIL import Image, ImageDraw

async def capture(cfg, fdir):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 720, "height": 1280}, device_scale_factor=1, color_scheme="dark")
        pg = await ctx.new_page()
        await pg.goto("https://iowaleadtracker.com/?nc=" + cfg["stamp"], wait_until="networkidle", timeout=90000)
        ok = pg.get_by_role("button", name="OK")
        if await ok.count():
            await ok.first.click()

        async def scroll():
            top = await pg.locator("main iframe").evaluate("e => e.getBoundingClientRect().top + window.scrollY")
            await pg.evaluate(f"window.scrollTo(0,{top})"); await pg.wait_for_timeout(700)

        async def place(T):
            for _ in range(3):
                await scroll(); await pg.screenshot(path=os.path.join(fdir, "_p.jpg"), type="jpeg", quality=90)
                pos = find_release(os.path.join(fdir, "_p.jpg"))
                if not pos:
                    raise SystemExit("Could not find the release marker.")
                dx, dy = T[0] - pos[0], T[1] - pos[1]
                if abs(dx) < 6 and abs(dy) < 6:
                    return
                await pg.mouse.move(360, 520); await pg.mouse.down()
                await pg.mouse.move(360 + dx, 520 + dy, steps=15); await pg.mouse.up(); await pg.wait_for_timeout(1200)

        for view, zoom, target in (("wide", 1, (300, 330)), ("close", -2, (205, 320))):
            for c in cfg["cases"]:
                await pg.get_by_label("Lead in the air").select_option(c["key"])
                await pg.wait_for_timeout(3500)
                fr = pg.frame(name="map")
                await scroll()
                await fr.evaluate("""() => document.querySelectorAll('button').forEach(b => {
                    const l = b.getAttribute('aria-label') || '';
                    if (/^(Zoom in|Zoom out|Fit plume)$/.test(l)) b.style.visibility = 'hidden'; })""")
                await fr.get_by_role("button", name="Levels of concern", exact=True).first.evaluate("b => b.click()")
                await pg.wait_for_timeout(1200)
                await place((360, 475))
                btn = "Zoom out" if zoom > 0 else "Zoom in"
                for _ in range(abs(zoom)):
                    await fr.locator(f'button[aria-label="{btn}"]').first.evaluate("b => b.click()"); await pg.wait_for_timeout(1500)
                await place(target)
                await fr.locator("input[type=range]").first.evaluate(
                    "(e, v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); }", "8")
                await pg.wait_for_timeout(1500); await scroll()
                await pg.screenshot(path=os.path.join(fdir, f"{view}_{c['key']}.jpg"), type="jpeg", quality=92)
        await b.close()

def story(cfg, src, out, kicker, c):
    X = 60
    im = Image.new("RGB", (1080, 1920), BG); d = ImageDraw.Draw(im)
    mp = Image.open(src).convert("RGB").crop((0, 205, 720, 785)).resize((1080, 870), Image.LANCZOS)
    big, small = f"{c['share']} airborne", f"{c['label']} case"
    d.text((X, 272), kicker, font=semi(30), fill=AMBER)
    d.text((X, 310), "Iowa Army Ammunition Plant", font=bold(54), fill="white")
    d.text((X, 374), big, font=bold(66), fill="white")
    d.text((X + d.textlength(big, font=bold(66)) + 22, 398), small, font=reg(32), fill=GREY)
    d.text((X, 456), cfg["status_line"], font=semi(29), fill=GOLD)
    im.paste(mp, (0, 505))
    y, x = 1392, X
    for name, col, lvl in LEVELS:
        d.rounded_rectangle((x, y + 6, x + 26, y + 32), radius=5, fill=col); x += 38
        d.text((x, y), name, font=semi(28), fill="white"); x += d.textlength(name, font=semi(28)) + 10
        d.text((x, y), lvl, font=reg(28), fill=GREY); x += d.textlength(lvl, font=reg(28)) + 34
    d.text((X, y + 44), f"Reach: yellow {c['yellow']} · orange {c['orange']} · red {c['red']}", font=semi(27), fill="white")
    y = 1500
    d.text((X, y), "Unofficial estimate — not from the Army or any agency.", font=semi(31), fill=GOLD)
    d.text((X, y + 44), "Same forecast for all three; only the airborne share changes.", font=reg(29), fill=(225, 225, 225))
    d.text((X, y + 82), "Don't use this to judge safety. Follow official instructions.", font=reg(29), fill=(225, 225, 225))
    d.text((X, y + 130), f"iowaleadtracker.com · updated {cfg['updated']} · {cfg['scenario']}", font=reg(24), fill=(165, 165, 165))
    d.text((X, y + 162), "Map tiles © Esri and its data providers, © OpenStreetMap contributors", font=reg(24), fill=(165, 165, 165))
    im.save(out)

def fb(cfg, fdir, out):
    W, H, FX = 1080, 1350, 50
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((FX, 34), f"SAME FORECAST · 3 ASSUMPTIONS · UPDATED {cfg['updated'].upper()}", font=semi(25), fill=AMBER)
    d.text((FX, 68), "How much lead gets into the air matters", font=bold(46), fill="white")
    d.text((FX, 128), f"Where lead could settle by 8 p.m. {cfg['scenario']}", font=reg(27), fill=GREY)
    PY, PW, PH = 214, 356, 590
    for i, c in enumerate(cfg["cases"]):
        px = 6 + i * (PW + 3)
        im.paste(Image.open(os.path.join(fdir, f"wide_{c['key']}.jpg")).convert("RGB").crop((150, 215, 150 + PW, 215 + PH)), (px, PY))
        lab = Image.new("RGBA", (PW, 64), (20, 20, 20, 225)); im.paste(lab, (px, PY), lab)
        d = ImageDraw.Draw(im)
        d.text((px + 14, PY + 6), f"{c['label']} case", font=semi(24), fill="white")
        d.text((px + 14, PY + 34), f"{c['share']} airborne", font=reg(21), fill=GOLD)
    ty = PY + PH + 20; cols = [FX, 420, 640, 860]
    d.text((cols[0], ty), "Farthest reach", font=semi(25), fill=AMBER)
    for col, c in zip(cols[1:], cfg["cases"]):
        d.text((col, ty), c["label"], font=semi(25), fill="white")
    ry = ty + 42
    for i, (lab, k) in enumerate([("Yellow (≥ 5 µg/ft²)", "yellow"), ("Orange (≥ 40 µg/ft²)", "orange"), ("Red (≥ 100 µg/ft²)", "red"),
                                  ("Peak air near plant, µg/m³", "air"), ("Lead airborne, lb", "lb")]):
        if i % 2 == 0:
            d.rectangle((FX - 14, ry - 6, W - FX + 14, ry + 33), fill=(40, 40, 38))
        d.text((cols[0], ry), lab, font=reg(24), fill=GREY)
        for col, c in zip(cols[1:], cfg["cases"]):
            d.text((col, ry), c[k], font=semi(24), fill="white")
        ry += 39
    by = ry + 16
    d.rounded_rectangle((FX - 14, by, W - FX + 14, by + 150), radius=12, fill=(48, 40, 26))
    d.text((FX + 6, by + 12), "What the Army expects", font=semi(26), fill=GOLD)
    for j, line in enumerate(cfg["army_note"][:3]):
        d.text((FX + 6, by + 48 + j * 32), line, font=reg(24), fill=(235, 235, 235))
    fy = by + 168
    d.text((FX, fy), "Unofficial estimate — not from the Army or any agency. Follow official instructions.", font=semi(22), fill=GOLD)
    d.text((FX, fy + 32), "iowaleadtracker.com · Map tiles © Esri, © OpenStreetMap contributors · Weather: Open-Meteo", font=reg(19), fill=(150, 150, 150))
    im.save(out)

def main():
    cfg = json.load(open(sys.argv[1]))
    od = cfg["outdir"]; fdir = os.path.join(od, "frames"); os.makedirs(fdir, exist_ok=True)
    if "--no-capture" not in sys.argv:
        asyncio.run(capture(cfg, fdir))
    frames = []
    for view, kicker in (("wide", "SAME FORECAST · 3 ASSUMPTIONS · BY 8 P.M."), ("close", "CLOSE-UP NEAR THE PLANT · BY 8 P.M.")):
        for c in cfg["cases"]:
            o = os.path.join(fdir, f"story_{view}_{c['key']}.png")
            story(cfg, os.path.join(fdir, f"{view}_{c['key']}.jpg"), o, kicker, c); frames.append(o)
    render(frames, [3.0, 2.6, 2.6, 2.8, 2.6, 4.2], [0.6] * 5, os.path.join(od, f"iaap-airborne-cases-story-{cfg['stamp']}.mp4"))
    fb(cfg, fdir, os.path.join(od, f"iaap-airborne-cases-fb-{cfg['stamp']}.png"))
    print("done:", od)

if __name__ == "__main__":
    main()
```

## Side-by-side day comparison
Use when the site's "Day" menu (`select#d`, values like `2026-11-23` and `2026-11-24`) offers more than one blast day. Both days are captured at one fixed zoom and position, so the two panels compare directly. Each day's auto-fit view differs, so don't use Fit plume here.

1. **Get each day's numbers.** The site's summary has a section per day: "Where the cloud goes on Monday, Nov. 23" and "If the blasts are on Tuesday, Nov. 24". Read each section separately; `sitetext.py`'s regexes catch only the first one. Take wind, direction and miles by 8 p.m., the EPA permit row (red, orange and yellow reach, main model), peak one-hour air, and the yellow-area towns. A quick way: load the page, `t = body.inner_text()`, then slice from each heading to the next heading.
2. **Pick the framing.** `zoom` 6 and `release_at` [270, 180] fit a ~150-mile southeast plume and a ~55-mile southwest plume at the 540-pixel viewport. If a plume runs north, put the release lower (larger y). If it runs east or west, move it the other way. Check `frames/story_8.png` and adjust.
3. Write `days.json`, save `days_post.py` (below) next to `make_assets.py`, and run `python3 days_post.py days.json`. It takes about 1.5 minutes. `--no-capture` recomposes only.
4. **Outputs:**
   - `iaap-<day1>-vs-<day2>-story-<stamp>.mp4`: both days in one 1080×1920 frame, 1 to 8 p.m., with a label bar on each panel giving the day, the wind, and the red/orange/yellow reach.
   - `iaap-<day1>-vs-<day2>-fb-<stamp>.png`: both days at 8 p.m., an at-a-glance table, and a "Why the models disagree more about <day>" box. It puts the color key over whichever panel has less plume at the bottom.
5. **Check** that each release point sits below its panel's label bar and that both plumes fit.
6. **Caption:** follow Voice and tone. Use 📅 for each day with wind and path, then 🔴 🟠 🟡 🌫️ lines. Add one plain sentence comparing the days, and a 🧭 line on why one day is less certain when its wind is lighter. Swap hashtags to fit the paths, e.g. #NortheastMissouri for a southwest path.

`days.json` example (Nov. 22, 10:34 a.m. update):
```json
{"outdir": "/home/claude/out/days-nov22", "stamp": "nov22-1034am", "updated": "Nov. 22, 10:34 a.m.", "models": 7,
 "status_line": "Army says it will act by Tue., Nov. 24. Court ruling pending.",
 "headline": "Monday or Tuesday makes a big difference",
 "zoom": 6, "release_at": [270, 180],
 "why_note": ["When the wind blows hard, the models agree on where the cloud goes.",
              "When it barely blows, small differences between forecasts turn the",
              "cloud in different directions, so Tuesday's shaded area fans out wider."],
 "days": [
  {"value": "2026-11-23", "title": "MONDAY, NOV. 23", "short": "Monday", "wind": "NW, 12 mph", "path": "SE, 152 mi",
   "red": "10 mi", "orange": "26 mi", "yellow": "152 mi", "air": "843"},
  {"value": "2026-11-24", "title": "TUESDAY, NOV. 24", "short": "Tuesday", "wind": "NE, 4 mph", "path": "SW, 54 mi",
   "red": "25 mi", "orange": "38 mi", "yellow": "57 mi", "air": "3,982"}]}
```

### days_post.py
```python
#!/usr/bin/env python3
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_assets import find_release, is_shade, bold, semi, reg, BG, AMBER, GOLD, GREY, LEVELS, render
from PIL import Image, ImageDraw

VW = 540

async def capture(cfg, fdir):
    from playwright.async_api import async_playwright
    T = tuple(cfg.get("release_at", [270, 180])); K = int(cfg.get("zoom", 6))
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": VW, "height": 1280}, device_scale_factor=1, color_scheme="dark")
        pg = await ctx.new_page()
        await pg.goto("https://iowaleadtracker.com/?nc=" + cfg["stamp"], wait_until="networkidle", timeout=90000)
        ok = pg.get_by_role("button", name="OK")
        if await ok.count():
            await ok.first.click()

        async def scroll():
            top = await pg.locator("main iframe").evaluate("e => e.getBoundingClientRect().top + window.scrollY")
            await pg.evaluate(f"window.scrollTo(0,{top})"); await pg.wait_for_timeout(600)

        for day in cfg["days"]:
            await pg.locator("select#d").select_option(day["value"]); await pg.wait_for_timeout(4000)
            fr = pg.frame(name="map")
            await scroll()
            await fr.evaluate("""() => document.querySelectorAll('button').forEach(b => {
                const l = b.getAttribute('aria-label') || '';
                if (/^(Zoom in|Zoom out|Fit plume)$/.test(l)) b.style.visibility = 'hidden'; })""")
            await fr.get_by_role("button", name="Levels of concern", exact=True).first.evaluate("b => b.click()")
            await pg.wait_for_timeout(800)
            cb = fr.get_by_label("weather-model spread", exact=False).first
            if not await cb.is_checked():
                await cb.evaluate("e => e.click()")
            await pg.wait_for_timeout(1500)
            for _ in range(12):
                await fr.locator('button[aria-label="Zoom out"]').first.evaluate("b => b.click()"); await pg.wait_for_timeout(250)
            await pg.wait_for_timeout(1000)
            for _ in range(K):
                await fr.locator('button[aria-label="Zoom in"]').first.evaluate("b => b.click()"); await pg.wait_for_timeout(900)
            await pg.wait_for_timeout(1200)
            for _ in range(4):
                await scroll(); await pg.screenshot(path=os.path.join(fdir, "_p.jpg"), type="jpeg", quality=90)
                pos = find_release(os.path.join(fdir, "_p.jpg"))
                if not pos:
                    raise SystemExit("Could not find the release marker.")
                dx, dy = T[0] - pos[0], T[1] - pos[1]
                if abs(dx) < 5 and abs(dy) < 5:
                    break
                await pg.mouse.move(270, 600); await pg.mouse.down()
                await pg.mouse.move(270 + dx, 600 + dy, steps=15); await pg.mouse.up(); await pg.wait_for_timeout(1300)
            for h in range(1, 9):
                await fr.locator("input[type=range]").first.evaluate(
                    "(e, v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); }", str(h))
                await pg.wait_for_timeout(1500); await scroll()
                await pg.screenshot(path=os.path.join(fdir, f"{day['value']}_{h}.jpg"), type="jpeg", quality=92)
        await b.close()

def legend(d, x, y, size=28):
    gap = 34 if size >= 26 else 18
    for name, col, lvl in LEVELS:
        d.rounded_rectangle((x, y + 6, x + size - 2, y + size + 4), radius=5, fill=col); x += size + 10
        d.text((x, y), name, font=semi(size), fill="white"); x += d.textlength(name, font=semi(size)) + 10
        d.text((x, y), lvl, font=reg(size), fill=GREY); x += d.textlength(lvl, font=reg(size)) + gap

def panel_labels(im, px, py, pw, ph, day, bottom=True):
    top = Image.new("RGBA", (pw, 78), (18, 18, 18, 225)); im.paste(top, (px, py), top)
    d = ImageDraw.Draw(im)
    d.text((px + 18, py + 8), day["title"], font=bold(30), fill="white")
    d.text((px + 18, py + 44), "Wind from " + day["wind"], font=reg(24), fill=GOLD)
    if bottom:
        bot = Image.new("RGBA", (pw, 48), (18, 18, 18, 225)); im.paste(bot, (px, py + ph - 48), bot)
        d = ImageDraw.Draw(im)
        d.text((px + 18, py + ph - 40), f"Red {day['red']} · Orange {day['orange']} · Yellow {day['yellow']}",
               font=semi(22), fill="white")

def story_frame(cfg, fdir, h, out):
    X, PW, PH, PY = 60, 538, 870, 505
    im = Image.new("RGB", (1080, 1920), BG); d = ImageDraw.Draw(im)
    a, b_ = cfg["days"]
    d.text((X, 272), f"{a['short'].upper()} VS. {b_['short'].upper()} · {cfg['models']} WEATHER MODELS", font=semi(30), fill=AMBER)
    d.text((X, 310), "Iowa Army Ammunition Plant", font=bold(54), fill="white")
    big = f"By {h} p.m."
    d.text((X, 374), big, font=bold(66), fill="white")
    d.text((X + d.textlength(big, font=bold(66)) + 22, 398), "where lead could settle", font=reg(32), fill=GREY)
    d.text((X, 456), cfg["status_line"], font=semi(29), fill=GOLD)
    for i, day in enumerate(cfg["days"]):
        px = i * (PW + 4)
        y0 = max(0, int(cfg.get("release_at", [270, 180])[1]) - 120)
        im.paste(Image.open(os.path.join(fdir, f"{day['value']}_{h}.jpg")).convert("RGB").crop((0, y0, PW, y0 + PH)), (px, PY))
        panel_labels(im, px, PY, PW, PH, day)
    d = ImageDraw.Draw(im)
    d.rectangle((PW, PY, PW + 3, PY + PH), fill=(10, 10, 10))
    legend(d, X, 1392)
    d.text((X, 1436), f"Shading = highest of {cfg['models']} weather models. Reach = main model.", font=reg(25), fill=GREY)
    y = 1500
    d.text((X, y), "Unofficial estimate — not from the Army or any agency.", font=semi(31), fill=GOLD)
    d.text((X, y + 44), "Noon blast both days · EPA permit case (100% airborne)", font=reg(29), fill=(225, 225, 225))
    d.text((X, y + 82), "Don't use this to judge safety. Follow official instructions.", font=reg(29), fill=(225, 225, 225))
    d.text((X, y + 130), f"iowaleadtracker.com · updated {cfg['updated']} · weather: Open-Meteo", font=reg(24), fill=(165, 165, 165))
    d.text((X, y + 162), "Map tiles © Esri and its data providers, © OpenStreetMap contributors", font=reg(24), fill=(165, 165, 165))
    im.save(out)

def fb_image(cfg, fdir, out):
    W, H, FX = 1080, 1350, 50
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    a, b_ = cfg["days"]
    d.text((FX, 30), f"{a['short'].upper()} VS. {b_['short'].upper()} · {cfg['models']} WEATHER MODELS · UPDATED {cfg['updated'].upper()}",
           font=semi(24), fill=AMBER)
    d.text((FX, 62), cfg["headline"], font=bold(46), fill="white")
    d.text((FX, 120), "Where lead could settle by 8 p.m. after a noon blast (EPA permit case)", font=reg(26), fill=GREY)
    PW, PH, PY = 538, 655, 168
    for i, day in enumerate(cfg["days"]):
        px = i * (PW + 4)
        y0 = max(0, int(cfg.get("release_at", [270, 180])[1]) - 140)
        im.paste(Image.open(os.path.join(fdir, f"{day['value']}_8.jpg")).convert("RGB").crop((0, y0, PW, y0 + PH)), (px, PY))
        panel_labels(im, px, PY, PW, PH, day, bottom=False)
    d = ImageDraw.Draw(im)
    d.rectangle((PW, PY, PW + 3, PY + PH), fill=(10, 10, 10))
    px_ = im.load()
    shade = [sum(1 for y in range(PY + PH - 50, PY + PH, 3) for x in range(i * (PW + 4), i * (PW + 4) + PW, 4) if is_shade(px_[x, y]))
             for i in range(2)]
    k = 0 if shade[0] < shade[1] else 1
    lb = Image.new("RGBA", (PW, 46), (18, 18, 18, 225)); im.paste(lb, (k * (PW + 4), PY + PH - 46), lb)
    d = ImageDraw.Draw(im); legend(d, k * (PW + 4) + 14, PY + PH - 39, size=21)
    ty = PY + PH + 18; cols = [FX, 470, 780]
    d.text((cols[0], ty), "At a glance", font=semi(25), fill=AMBER)
    d.text((cols[1], ty), a["short"], font=semi(25), fill="white")
    d.text((cols[2], ty), b_["short"], font=semi(25), fill="white")
    rows = [("Wind at blast time", "wind"), ("Cloud by 8 p.m.", "path"), ("Red zone reach (≥100)", "red"),
            ("Orange zone reach (≥40)", "orange"), ("Yellow zone reach (≥5)", "yellow"), ("Peak air near plant, µg/m³", "air")]
    ry = ty + 40
    for i, (lab, key) in enumerate(rows):
        if i % 2 == 0:
            d.rectangle((FX - 14, ry - 6, W - FX + 14, ry + 32), fill=(40, 40, 38))
        d.text((cols[0], ry), lab, font=reg(24), fill=GREY)
        d.text((cols[1], ry), a[key], font=semi(24), fill="white")
        d.text((cols[2], ry), b_[key], font=semi(24), fill="white")
        ry += 38
    by = ry + 14
    d.rounded_rectangle((FX - 14, by, W - FX + 14, by + 142), radius=12, fill=(48, 40, 26))
    d.text((FX + 6, by + 10), f"Why the models disagree more about {b_['short']}", font=semi(25), fill=GOLD)
    for j, line in enumerate(cfg["why_note"][:3]):
        d.text((FX + 6, by + 44 + j * 31), line, font=reg(23), fill=(235, 235, 235))
    fy = by + 156
    d.text((FX, fy), "Unofficial estimate — not from the Army or any agency. Follow official instructions.", font=semi(22), fill=GOLD)
    d.text((FX, fy + 30), "iowaleadtracker.com · Map tiles © Esri, © OpenStreetMap contributors · Weather: Open-Meteo", font=reg(19), fill=(150, 150, 150))
    im.save(out)

def main():
    cfg = json.load(open(sys.argv[1]))
    od = cfg["outdir"]; fdir = os.path.join(od, "frames"); os.makedirs(fdir, exist_ok=True)
    if "--no-capture" not in sys.argv:
        asyncio.run(capture(cfg, fdir))
    frames = []
    for h in range(1, 9):
        o = os.path.join(fdir, f"story_{h}.png"); story_frame(cfg, fdir, h, o); frames.append(o)
    a, b_ = cfg["days"]
    tag = f"{a['short'].lower()}-vs-{b_['short'].lower()}"
    render(frames, [2.0] + [1.5] * 6 + [4.5], [0.6] * 7, os.path.join(od, f"iaap-{tag}-story-{cfg['stamp']}.mp4"))
    fb_image(cfg, fdir, os.path.join(od, f"iaap-{tag}-fb-{cfg['stamp']}.png"))
    print("done:", od)

if __name__ == "__main__":
    main()
```

## If something breaks
- **"Could not find the release marker":** the site's marker color or layout changed. Take a screenshot (`frames/_probe.jpg`), find the marker's color, and adjust `find_release`.
- **Plume cut off or off-center:** check `direction` matches the site's "cloud heads ..." text, then rerun.
- **Site layout changed** (buttons renamed, map not in a frame named "map"): inspect with a short Playwright script before changing the pipeline.
- **No network to the site:** ask the social media manager to check Allowed websites, or use the Claude desktop app's built-in browser as a fallback.
