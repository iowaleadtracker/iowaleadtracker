"""Download fresh weather forecasts for the Iowa scenario and rebuild everything from them.

Steps:

1. Move ``met_cache/map_met_all.json`` into ``met_cache_retrieved_<UTC time>/`` (git-ignored),
   named for when that copy was downloaded.
2. Run ``make_map_picker.py --build``, which downloads new forecasts into ``met_cache/``
   and rebuilds all the maps and the page.
3. If the new forecasts hold the same numbers as the old ones (only the download times
   differ), put the old file back and exit with status 3: nothing to publish.
4. Otherwise regenerate the golden regression data (``tests/data/``) from the new file.

It doesn't commit, deploy or publish. Run it by hand (``python tools/refresh_forecast.py``)
or let ``.github/workflows/refresh-forecast.yml`` run it and open a pull request.

With ``--staged`` it does the same for the staged Tuesday/Wednesday maps
(``scenarios/iowa-aap-lead-azide/staged.py``): their own saved file
(``met_cache/staged_forecasts.json``), only those maps rebuilt (``staged.py --build``),
no golden data. The first run, before that file exists, downloads it. The
``refresh-staged.yml`` workflow runs it by hand only.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "iowa-aap-lead-azide"
CACHE = SCENARIO / "met_cache" / "map_met_all.json"
STAGED_CACHE = SCENARIO / "met_cache" / "staged_forecasts.json"
UNCHANGED = 3


def fetched(data: dict[str, Any]) -> list[dt.datetime]:
    """Return the download times recorded in a forecast cache."""
    return [dt.datetime.fromisoformat(v) for v in (data.get("__fetched__") or {}).values()]


def forecasts(data: dict[str, Any]) -> dict[str, Any]:
    """Return the cached responses without their download times."""
    return {k: v for k, v in data.items() if k != "__fetched__"}


def archive_name(data: dict[str, Any]) -> str:
    """Name the archive folder for the oldest download in ``data`` (UTC)."""
    stamps = fetched(data)
    when = min(stamps) if stamps else dt.datetime.now(dt.timezone.utc)
    return f"met_cache_retrieved_{when.astimezone(dt.timezone.utc):%Y%m%dT%H%M}"


def run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    """Run a step, echoing it; stop on failure."""
    print("+", " ".join(args), file=sys.stderr)
    subprocess.run(args, cwd=cwd, env=env, check=True)  # noqa: S603 - our own scripts


def main(argv: list[str] | None = None) -> int:
    """Refresh the forecasts; return 0 when they changed, 3 when they didn't."""
    args = sys.argv[1:] if argv is None else argv
    if any(a != "--staged" for a in args):
        raise SystemExit("usage: refresh_forecast.py [--staged]")
    if "--staged" in args:
        return refresh(STAGED_CACHE, ["staged.py", "--build"], golden=False)
    return refresh(CACHE, ["make_map_picker.py", "--build"], golden=True)


def refresh(cache: Path, build: list[str], *, golden: bool) -> int:
    """Download new forecasts into ``cache`` and rebuild; 0 when changed, 3 when not."""
    if not cache.exists():
        if golden:
            raise SystemExit(f"no saved forecasts at {cache}")
        run([sys.executable, *build], cwd=SCENARIO)  # first download
        print(f"downloaded {cache.relative_to(ROOT)}", file=sys.stderr)
        return 0
    old_text = cache.read_text(encoding="utf-8")
    old = json.loads(old_text)
    archive = SCENARIO / archive_name(old)
    archive.mkdir(exist_ok=True)
    kept = archive / cache.name
    shutil.move(cache, kept)
    print(f"moved the saved forecasts to {kept.relative_to(ROOT)}", file=sys.stderr)

    try:
        run([sys.executable, *build], cwd=SCENARIO)
    except subprocess.CalledProcessError:
        shutil.copy2(kept, cache)  # leave the repo as it was
        raise

    new = json.loads(cache.read_text(encoding="utf-8"))
    if forecasts(new) == forecasts(old):
        cache.write_text(old_text, encoding="utf-8")
        print("the forecasts haven't changed; kept the saved file", file=sys.stderr)
        return UNCHANGED

    if golden:
        env = {**os.environ, "PYTHONPATH": str(SCENARIO)}
        run([sys.executable, "-m", "tests.test_regression"], cwd=ROOT, env=env)
    pulled = min(fetched(new)).astimezone(dt.timezone(dt.timedelta(hours=-6)))
    print(f"new forecasts pulled {pulled:%Y-%m-%d %H:%M} CST", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
