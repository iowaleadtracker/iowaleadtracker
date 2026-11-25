"""Decode the wind table from NEXRAD Level III VAD Wind Profile (NVW) files.

Usage::

    python vad_decode.py NVW_FILE... > kdvn_vad.txt

Files are from NOAA's Level III archive on AWS (bucket ``unidata-nexrad-level3``, keys
like ``DVN_NVW_2026_11_25_15_00_58``). Needs MetPy. Heights are feet above sea level in
the product; ``alt_m_agl`` subtracts the radar's elevation (KDVN: 754 ft).
"""

from __future__ import annotations

import sys
from pathlib import Path

from metpy.io import Level3File

RADAR_FT = 754
MIN_COLUMNS = 10


def rows(path: Path) -> list[tuple[int, int, int, str, str]]:
    """Return (alt ft MSL, direction, speed kt, rms kt, slant range nm) per level."""
    out = []
    for page in Level3File(str(path)).tab_pages:
        for line in "".join(page).splitlines():
            t = line.split()
            if len(t) >= MIN_COLUMNS and t[0].isdigit():
                out.append((int(t[0]) * 100, int(t[4]), int(t[5]), t[6], t[8]))
    return sorted(out)


if __name__ == "__main__":
    sys.stdout.write("# file, alt_ft_msl, alt_m_agl, dir_deg, speed_kt, rms_kt, slant_range_nm\n")
    for name in sys.argv[1:]:
        for alt, d, s, rms, rng in rows(Path(name)):
            sys.stdout.write(
                f"{Path(name).name},{alt},{(alt - RADAR_FT) * 0.3048:.0f},{d},{s},{rms},{rng}\n"
            )
