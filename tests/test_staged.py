"""The staged Wednesday-Friday maps: settings, page, privacy and the mirror."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any

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
    """Wednesday to Friday, 8:30, 9:00 and 9:30 a.m., GFS and ECMWF only."""
    assert staged.DAYS == ["2026-11-25", "2026-11-26", "2026-11-27"]
    assert staged.TIMES == ["08:30", "09:00", "09:30"]
    assert staged.WEATHER == "gfs_global,ecmwf_ifs025"
    assert staged.day_label("2026-11-25") == "Wednesday, Nov. 25, 2026"
    assert staged.day_label("2026-11-27") == "Friday, Nov. 27, 2026"
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
    assert n == 3 * 3 * len(site.CASES) == 36
    page = (built / "index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, nofollow">' in page
    assert "This is an unofficial estimate, not from the Army or any government agency." in page
    assert "Don't use it to decide if you're safe." in page
    assert "Follow official instructions." in page
    assert "GFS and ECMWF only" in page
    assert "Wednesday to Friday runs" in page
    assert "Wednesday, Nov. 25, 2026; Thursday, Nov. 26, 2026; and Friday, Nov. 27, 2026" in page
    assert "November 21, 2026, at 9:08 p.m. CST" in page  # forecast pull time
    # When: the Nov. 22 court filing, then the Army's Wednesday announcement, both linked.
    assert "the government said the Army postponed it to Tuesday, Nov. 24" in page
    assert "it is now scheduled for Wednesday, Nov. 25. On Monday, Nov. 23," in page
    assert f'<a href="{forecast_summary.TRUMP_URL}">President Trump said</a>' in page
    assert "until the Eighth Circuit agrees and Governor-elect Rob Sand agrees" in page
    assert "the detonation will be Wednesday morning" in page
    assert "a FEMA emergency alert set it for 9 a.m. Wednesday" in page.replace("\n", " ")
    assert "Thursday and Friday haven&rsquo;t been announced." in page
    assert f'<a href="{html.escape(forecast_summary.ARMY_WED_URL)}">the Army said</a>' in page
    assert f'<a href="{forecast_summary.RESPONSE_URL}">court filing on Nov. 22</a>' in page
    assert "it hasn&rsquo;t\n    announced these days" not in page
    m = re.search(r"const FILES = (\{.*?\});", page)
    assert m
    files = json.loads(m.group(1))
    assert len(files) == 36
    assert files["2026-11-25-permit-0900"] == "maps/2026-11-25-permit-0900.html"
    assert '<option value="09:30">9:30 a.m.</option>' in page
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


def test_refreshes_run_through_the_last_day() -> None:
    """Both refreshes run on a schedule through the last day their maps model."""
    root = Path(__file__).resolve().parent.parent / ".github" / "workflows"
    for name, last in (
        ("refresh-forecast.yml", site.DAYS[-1][0]),  # Thursday, a Day menu option
        ("refresh-staged.yml", staged.DAYS[-1]),  # Friday
    ):
        text = (root / name).read_text(encoding="utf-8")
        assert f'LAST_DAY: "{last}"' in text, name
        assert "schedule:" in text, name
        assert "workflow_dispatch:" in text, name


def test_refresh_downloads_once_then_runs_the_rest_with_its_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the saved file, the first run downloads alone; the rest replay its pull.

    Every later run gets that pull's ``--as-of``, and its hour isn't downloaded again.
    """
    cache = tmp_path / "staged_forecasts.json"
    monkeypatch.setattr(staged, "CACHE", cache)
    monkeypatch.setattr(staged, "MAPS", tmp_path / "maps")
    monkeypatch.setattr(site, "sky_grid_args", list)
    pulled = "2026-11-24T21:00:00+00:00"
    ran: list[tuple[list[str], bool]] = []

    class Done:
        returncode = 0
        stdout = stderr = ""

    def fake_run(cmd: list[str], **kw: Any) -> Done:
        ran.append((cmd, site.CACHE_ONLY_ENV in kw["env"]))
        if not cache.exists():  # the first download saves the file and its time
            cache.write_text(json.dumps({"__fetched__": {"u": pulled}}), encoding="utf-8")
        return Done()

    monkeypatch.setattr(site.subprocess, "run", fake_run)
    staged.build()

    def arg(cmd: list[str], name: str) -> str | None:
        return cmd[cmd.index(name) + 1] if name in cmd else None

    n = len(staged.DAYS) * len(site.CASES) * len(staged.TIMES)
    assert len(ran) == n
    first, *rest = ran
    assert arg(first[0], "--as-of") is None
    assert not first[1]
    as_of = site.retrieved_at(cache)
    assert as_of is not None
    assert {arg(cmd, "--as-of") for cmd, _ in rest} == {as_of.isoformat()}
    assert all("forecast from" in (arg(cmd, "--legend-note") or "") for cmd, _ in rest)
    # one download per other start hour (day and hour); the first run's hour isn't one
    hours = {arg(cmd, "--time")[:13] for cmd, _ in ran}  # type: ignore[index]
    downloading = [cmd for cmd, cache_only in rest if not cache_only]
    assert len(downloading) == len(hours) - 1
    assert arg(first[0], "--time")[:13] not in {arg(c, "--time")[:13] for c in downloading}  # type: ignore[index]
