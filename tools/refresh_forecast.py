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
SCENARIO = ROOT / "scenarios" / "iowa-aap-2026-11-20"
CACHE = SCENARIO / "met_cache" / "map_met_all.json"
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


def main() -> int:
    """Refresh the forecasts; return 0 when they changed, 3 when they didn't."""
    if not CACHE.exists():
        raise SystemExit(f"no saved forecasts at {CACHE}")
    old_text = CACHE.read_text(encoding="utf-8")
    old = json.loads(old_text)
    archive = SCENARIO / archive_name(old)
    archive.mkdir(exist_ok=True)
    kept = archive / CACHE.name
    shutil.move(CACHE, kept)
    print(f"moved the saved forecasts to {kept.relative_to(ROOT)}", file=sys.stderr)

    try:
        run([sys.executable, "make_map_picker.py", "--build"], cwd=SCENARIO)
    except subprocess.CalledProcessError:
        shutil.copy2(kept, CACHE)  # leave the repo as it was
        raise

    new = json.loads(CACHE.read_text(encoding="utf-8"))
    if forecasts(new) == forecasts(old):
        CACHE.write_text(old_text, encoding="utf-8")
        print("the forecasts haven't changed; kept the saved file", file=sys.stderr)
        return UNCHANGED

    env = {**os.environ, "PYTHONPATH": str(SCENARIO)}
    run([sys.executable, "-m", "tests.test_regression"], cwd=ROOT, env=env)
    pulled = min(fetched(new)).astimezone(dt.timezone(dt.timedelta(hours=-6)))
    print(f"new forecasts pulled {pulled:%Y-%m-%d %H:%M} CST", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
