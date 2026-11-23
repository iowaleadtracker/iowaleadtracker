"""The staged Tuesday/Wednesday maps: settings, page, privacy and the mirror."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import forecast_summary
import make_map_picker as site
import mirror
import pytest
import staged

MAP = "<!doctype html>\n<html><head>\n<title>map</title></head><body>map</body></html>"


@pytest.fixture
def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a fake set of staged maps and saved forecasts in tmp_path."""
    out = tmp_path / staged.DIR_NAME
    monkeypatch.setattr(staged, "OUT", out)
    monkeypatch.setattr(staged, "MAPS", out / "maps")
    cache = tmp_path / "staged_forecasts.json"
    cache.write_text(
        json.dumps({"__fetched__": {"a": "2026-11-22T03:08:00+00:00"}}), encoding="utf-8"
    )
    monkeypatch.setattr(staged, "CACHE", cache)
    (out / "maps").mkdir(parents=True)
    for day in staged.DAYS:
        for case, _, _ in site.CASES:
            for t in staged.TIMES:
                (out / "maps" / staged.map_name(day, case, t)).write_text(MAP, encoding="utf-8")
    return out


def test_settings() -> None:
    """Tuesday and Wednesday, 11 a.m. to 1 p.m. every 30 minutes, GFS and ECMWF only."""
    assert staged.DAYS == ["2026-11-24", "2026-11-25"]
    assert staged.TIMES == ["11:00", "11:30", "12:00", "12:30", "13:00"]
    assert staged.WEATHER == "gfs_seamless,ecmwf_ifs025"
    assert staged.day_label("2026-11-24") == "Tuesday, Nov. 24, 2026"
    assert staged.day_label("2026-11-25") == "Wednesday, Nov. 25, 2026"
    assert re.fullmatch(r"s-[0-9a-f]{10}", staged.DIR_NAME)


def test_model_args_change_only_weather_and_file() -> None:
    args = staged.model_args()
    assert args[args.index("--weather-model") + 1] == staged.WEATHER
    assert args[args.index("--met-cache") + 1] == str(staged.CACHE)
    public = site.MODEL_ARGS
    assert public[public.index("--weather-model") + 1] == site.WEATHER  # not changed
    assert public[public.index("--met-cache") + 1] == str(site.MET_CACHE)
    others = [
        a
        for i, a in enumerate(args)
        if i not in {args.index("--weather-model") + 1, args.index("--met-cache") + 1}
    ]
    pub = [
        a
        for i, a in enumerate(public)
        if i not in {public.index("--weather-model") + 1, public.index("--met-cache") + 1}
    ]
    assert others == pub  # same model settings as the public maps


def test_picker_page(built: Path) -> None:
    n = staged.write_pages()
    assert n == 2 * 5 * len(site.CASES) == 40
    page = (built / "index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, nofollow">' in page
    assert "This is an unofficial estimate, not from the Army or any government agency." in page
    assert "Don't use it to decide if you're safe." in page
    assert "Follow official instructions." in page
    assert "GFS and ECMWF only" in page
    assert "Tuesday, Nov. 24, 2026" in page
    assert "Wednesday, Nov. 25, 2026" in page
    assert "November 21, 2026, at 9:08 p.m. CST" in page  # forecast pull time
    # When: from the Nov. 22 court filing, linked, not the old "Monday only" line.
    assert "the government said the Army postponed it to Tuesday, Nov. 24" in page
    assert "it is now scheduled for Wednesday, Nov. 25. No time has been given." in page
    assert f'<a href="{forecast_summary.ARMY_WED_URL}">the Army said</a>' in page
    assert f'<a href="{forecast_summary.RESPONSE_URL}">court filing on Nov. 22</a>' in page
    assert "it hasn&rsquo;t\n    announced these days" not in page
    m = re.search(r"const FILES = (\{.*?\});", page)
    assert m
    files = json.loads(m.group(1))
    assert len(files) == 40
    assert files["2026-11-24-permit-1200"] == "maps/2026-11-24-permit-1200.html"
    assert '<option value="13:00">1:00 p.m.</option>' in page
    for mp in (built / "maps").glob("*.html"):  # each map stays out of search too
        assert '<meta name="robots" content="noindex">' in mp.read_text(encoding="utf-8")


def test_no_maps_no_folder(built: Path) -> None:
    for mp in (built / "maps").glob("*.html"):
        mp.unlink()
    assert staged.write_pages() == 0
    assert not built.exists()


def test_kept_off_public_files_and_on_mirror(tmp_path: Path) -> None:
    """Nothing public points to the folder; the mirror carries it, noindex; it's noindex."""
    assert f"/{staged.DIR_NAME}/*\n  X-Robots-Tag: noindex, nofollow" in site.HEADERS
    for text in (
        site.PAGE_TEMPLATE.read_text(encoding="utf-8"),
        (site.TOOL / "template.html").read_text(encoding="utf-8"),
    ):
        assert not staged.links_to_staged(text)
    src = tmp_path / "site"
    (src / staged.DIR_NAME / "maps").mkdir(parents=True)
    (src / staged.DIR_NAME / "index.html").write_text(MAP, encoding="utf-8")
    (src / staged.DIR_NAME / "maps" / "a.html").write_text(MAP, encoding="utf-8")
    (src / "maps").mkdir()
    (src / "m").mkdir()
    (src / "index.html").write_text(
        MAP.replace("<head>", f'<head><link rel="canonical" href="{mirror.CANONICAL_URL}">'),
        encoding="utf-8",
    )
    out = tmp_path / "mirror"
    mirror.write_mirror(src, out, site.CSP)
    for page in (out / staged.DIR_NAME / "index.html", out / staged.DIR_NAME / "maps" / "a.html"):
        txt = page.read_text(encoding="utf-8")
        assert '<meta http-equiv="Content-Security-Policy"' in txt
        assert '<meta name="robots" content="noindex' in txt
        assert '<meta name="referrer" content="no-referrer">' in txt
        assert mirror.NOTICE_ID not in txt
    assert (src / staged.DIR_NAME / "index.html").exists()  # the main site keeps it


def test_retrieved_at_ignores_staged_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the public file missing, the staged file's time is never used for it."""
    other = tmp_path / "staged_forecasts.json"
    other.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(staged, "CACHE", other)
    assert site.retrieved_at(tmp_path / "map_met_all.json") is None


def test_refresh_tool_arguments() -> None:
    sys.path.insert(0, str(site.TOOL / "tools"))
    try:
        import refresh_forecast  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    with pytest.raises(SystemExit, match="usage"):
        refresh_forecast.main(["--bogus"])
    assert refresh_forecast.STAGED_CACHE.name == staged.CACHE.name


def test_missing_staged_file_has_no_time(tmp_path: Path) -> None:
    """A missing staged file never borrows the public forecasts' time."""
    assert site.retrieved_at(tmp_path / "staged_forecasts.json") is None


def test_refreshes_run_through_wednesday() -> None:
    """Both refreshes run on a schedule through the last day the maps model."""
    root = Path(__file__).resolve().parent.parent / ".github" / "workflows"
    last = staged.DAYS[-1]
    for name in ("refresh-forecast.yml", "refresh-staged.yml"):
        text = (root / name).read_text(encoding="utf-8")
        assert f'LAST_DAY: "{last}"' in text, name
        assert "schedule:" in text, name
        assert "workflow_dispatch:" in text, name
