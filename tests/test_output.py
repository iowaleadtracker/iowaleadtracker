"""The page data: field encoding and safe embedding in the HTML."""

import base64
import json
import math
import zlib
from pathlib import Path

import numpy as np
import pytest

import puff_dispersal as puff
from dispersal.output import gdas1_files, hysplit_files, load_template, pack, write_html

LS, PS = chr(0x2028), chr(0x2029)  # JavaScript line terminators


def unpack(packed: dict) -> np.ndarray:
    """Decode a packed field the way the page does (template.html qToLog)."""
    q = np.frombuffer(zlib.decompress(base64.b64decode(packed["data"])), np.uint8)
    lo, hi = packed["lo"], packed["hi"]
    return np.where(q > 0, 10 ** (lo + (q.astype(float) - 1) / 254 * (hi - lo)), 0.0)


def test_pack_round_trip_within_quantization() -> None:
    rng = np.random.default_rng(0)
    arr = 10 ** rng.uniform(-12, -3, size=(4, 30, 40))
    arr[0, 0, :5] = 0.0
    packed = pack(arr, decades=9)
    back = unpack(packed).reshape(arr.shape)
    shown = arr >= packed["max"] / 10**9
    step = 9 / 254  # decades per level
    assert np.all(np.abs(np.log10(back[shown]) - np.log10(arr[shown])) <= step / 2 + 1e-12)
    assert np.all(back[~shown] == 0.0)
    assert packed["max"] == pytest.approx(float(np.max(arr)))
    assert packed["hi"] == pytest.approx(math.log10(float(np.max(arr))))


def test_pack_empty_field() -> None:
    packed = pack(np.zeros((2, 3, 4)))
    assert packed["max"] == 0.0
    assert not unpack(packed).any()


def test_write_html_cannot_be_broken_out_of(tmp_path: Path) -> None:
    """No string in the data can close the <script> element or split a JS line."""
    nasty = f"</script><script>alert(1)</script> & {LS} {PS}"
    payload = {"meta": {"title": nasty}, "_arrays": {"x": 1}}
    out = tmp_path / "map.html"
    write_html(payload, out)
    page = out.read_text(encoding="utf-8")
    assert "<script>alert(1)" not in page
    assert LS not in page
    assert PS not in page
    assert "_arrays" not in page
    start = page.index("const DATA = ") + len("const DATA = ")
    data, _ = json.JSONDecoder().raw_decode(page, start)
    assert data["meta"]["title"] == nasty


def test_template_has_one_data_slot() -> None:
    assert load_template().count("/*__DATA__*/null") == 1


def test_hysplit_control_is_consistent() -> None:
    a = puff.parse_args(
        ["--lat", "40.8", "--lon", "-91.3", "--time", "2026-11-23T18:00Z", "--explosive-mass", "1t"]
    )
    grid = {"dx": 600.0, "north": 41.5, "south": 40.0, "east": -90.0, "west": -92.5}
    bins = [{"frac": 0.5, "d": 1e-6, "rho": 9500.0}, {"frac": 0.5, "d": 1e-5, "rho": 9500.0}]
    files = hysplit_files(a, bins, grid)
    lines = files["CONTROL"].splitlines()
    assert lines[0] == "26 11 23 18 00"
    assert lines[1] == "2"  # a vertical line source: two starting heights
    assert set(files) == {"CONTROL", "SETUP.CFG", "README.txt"}
    assert gdas1_files(a.start, 24) == ["gdas1.nov26.w4"]
