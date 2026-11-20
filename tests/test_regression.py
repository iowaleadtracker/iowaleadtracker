"""Golden numbers for one published map: the EPA permit case, noon blast.

Runs the site's exact model options on the saved forecasts (met_cache/), so it needs
no network, and compares field totals and maxima with tests/data/. A change here means
the published maps would change: if that is intended, regenerate with

    python -m tests.test_regression

and say why in the commit message.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import make_map_picker as site
import pytest

from . import conftest
from .conftest import run_puff

GOLDEN = Path(__file__).with_name("data") / "golden_permit_1200.json"
FIELDS = ("conc", "peak", "dep", "m60", "env_conc", "env_dep")


def site_argv() -> list[str]:
    return [
        *("--lat", str(site.LAT)),
        *("--lon", str(site.LON)),
        *("--time", f"{site.DATE}T12:00-06:00"),
        *("--release-case", "permit-100"),
        *site.MODEL_ARGS,
    ]


def fingerprint(out: dict[str, Any]) -> dict[str, Any]:
    arrays = out["_arrays"]
    last = out["hours"][-1]
    return {
        "weather": out["meta"]["weather"],
        "models": out["meta"]["ensemble"]["models"],
        "grid": [out["grid"]["nx"], out["grid"]["ny"], out["grid"]["dx"]],
        "fields": {
            k: {"sum": float(arrays[k].sum()), "max": float(arrays[k].max())} for k in FIELDS
        },
        "budget": {k: last[k] for k in ("released", "airborne", "dry", "wet")},
        "centroid": last["centroid"],
    }


@pytest.mark.slow
@pytest.mark.usefixtures("frozen_clock")
def test_permit_noon_matches_golden() -> None:
    _, out = run_puff(site_argv())
    got = fingerprint(out)
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert got["weather"] == want["weather"]
    assert got["models"] == want["models"]
    assert got["grid"][:2] == want["grid"][:2]
    assert got["grid"][2] == pytest.approx(want["grid"][2], rel=1e-12)
    for k, stats in want["fields"].items():
        assert got["fields"][k]["sum"] == pytest.approx(stats["sum"], rel=1e-9), k
        assert got["fields"][k]["max"] == pytest.approx(stats["max"], rel=1e-9), k
    for k, v in want["budget"].items():
        assert got["budget"][k] == pytest.approx(v, rel=1e-9), k
    assert got["centroid"] == pytest.approx(want["centroid"], abs=1e-5)


@pytest.mark.slow
def test_saved_forecasts_replay_on_a_later_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """With --as-of, a build months later uses the same saved forecasts.

    Without it, the model would treat the run as historical and ask the weather
    archive for data the saved file doesn't have. The site build (make_map_picker.py)
    passes --as-of so the Cloudflare and GitHub Pages copies always match.
    """
    later = conftest.FORECAST_PULLED + dt.timedelta(days=60)
    conftest.freeze_clock(monkeypatch, at=later)
    _, out = run_puff([*site_argv(), "--as-of", conftest.FORECAST_PULLED.isoformat()])
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    got = fingerprint(out)
    assert got["weather"] == want["weather"]
    assert got["models"] == want["models"]
    for k, stats in want["fields"].items():
        assert got["fields"][k]["sum"] == pytest.approx(stats["sum"], rel=1e-9), k


def regenerate() -> None:
    """Rewrite the golden file from the current code (run on purpose only)."""
    with pytest.MonkeyPatch.context() as mp:
        conftest.block_network(mp)
        conftest.freeze_clock(mp)
        _, out = run_puff(site_argv())
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_text(json.dumps(fingerprint(out), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {GOLDEN}", file=sys.stderr)


if __name__ == "__main__":
    regenerate()
