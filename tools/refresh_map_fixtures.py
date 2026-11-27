"""Remake the map data the browser tests load (tests/frontend/fixtures/*.json).

The tests put this data into template.html the way dispersal/output.py does, so they need
no build and no Python. Run this by hand only when the map data changes shape (a new key
the page reads): ``python3 tools/refresh_map_fixtures.py``. A pytest
(tests/test_map_fixtures.py) fails when the model writes a key the fixtures lack.

It runs the site build's own model commands for two maps, the Army mitigated (mid) case
at 9:00, with the saved forecasts and a coarse grid (50 cells): about 20 seconds.

- forecast.json: the forecast map: sky layer, Army outlines, model spread.
- archived.json: the archived-weather map: the NOAA HYSPLIT overlay.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "iowa-aap-lead-azide"
OUT = ROOT / "tests" / "frontend" / "fixtures"
sys.path.insert(0, str(SCENARIO))
sys.path.insert(0, str(ROOT))

import make_map_picker as site  # noqa: E402 - the scenario's modules, found through the path above
import staged  # noqa: E402

GRID = "50"  # cells along the longer side (the site uses 360)
MAPS = {"forecast": "mid 09:00", "archived": "archived mid 09:00"}
DATA = re.compile(r"const DATA = (\{.*?\});\n", re.DOTALL)


def site_commands() -> dict[str, list[str]]:
    """Return the build's model command for each map in MAPS, without running any."""
    found: list[site.Run] = []

    def collect(runs: list[site.Run], *, saved: bool, downloaded: Iterable[str] = ()) -> list[str]:  # noqa: ARG001
        found.extend(runs)
        return []  # nothing skipped

    def keep_days(days: list[str]) -> None:  # noqa: ARG001 - leave the built maps alone
        return

    def collect_archived(py: str) -> None:
        found.extend(site.archived_runs(py))

    site.run_maps = collect  # the build lists its commands instead of running them
    site.build_archived = collect_archived
    site.remove_days_not_built = keep_days
    staged.CACHE = SCENARIO / "no-staged-maps"  # skip the staged pages' maps
    site.build()
    by_name = {r.which: list(r.cmd) for r in found}
    return {name: by_name[which] for name, which in MAPS.items()}


def main() -> None:
    """Run each map on a coarse grid and save its data as JSON."""
    cache = SCENARIO / "met_cache"
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, cmd in site_commands().items():
            cmd[cmd.index("--grid") + 1] = GRID
            page = Path(tmp) / f"{name}.html"
            cmd[cmd.index("-o") + 1] = str(page)
            subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603 - our own model
            m = DATA.search(page.read_text(encoding="utf-8"))
            if not m:
                raise SystemExit(f"no map data in {page}")
            data = json.loads(m.group(1))
            path = OUT / f"{name}.json"
            path.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")
    # The saved forecasts must be enough: a download would change them.
    changed = subprocess.run(
        ["git", "status", "--porcelain", "--", str(cache)],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if changed:
        raise SystemExit(f"the model downloaded weather and changed {cache}; restore it:\n{changed}")


if __name__ == "__main__":
    main()
