"""Rewrite a HYSPLIT CONTROL file so it releases from the modeled sources.

Usage::

    python place_sources.py CONTROL

The CONTROL files in ``validation/hysplit-backtest/blast-day`` release from one vertical
line at the nominal point. This replaces that line with one vertical line per source in
``data/source.json``, keeping the two release heights. HYSPLIT gives each line the full
emission rate; ``lib.hysplit`` divides the result by the number of lines.
"""

from __future__ import annotations

import sys
from pathlib import Path

import lib


def main(path: Path) -> None:
    """Rewrite the starting locations in place."""
    lines = path.read_text().split("\n")
    count = int(lines[1])
    heights = [line.split()[2] for line in lines[2 : 2 + count]]
    starts = [f"{la:.4f} {lo:.4f} {h}" for la, lo in lib.source_coordinates() for h in heights]
    lines[1 : 2 + count] = [str(len(starts)), *starts]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
