#!/usr/bin/env python3
"""Print a key for the files a site build reads, at a git commit (default HEAD).

    python3 tools/site_key.py [COMMIT]

CI names the site it builds ``site-<key>``, and the deploy reuses that build when its own
commit has the same key, instead of building the site again (about 20 minutes). The key
covers everything the build reads (the model, the scenario with its saved forecasts, the
Python version and requirements) and CI's own workflow file, so a reused site was built
the same way the deploy would build it. Two commits with the same key give the same maps.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: The files and folders the site build depends on, plus the workflow that builds it.
SITE_INPUTS = (
    ".python-version",
    "requirements.txt",
    "puff_dispersal.py",
    "dispersal",
    "template.html",
    "scenarios",
    ".github/workflows/ci.yml",
)


def site_key(commit: str = "HEAD", cwd: Path = ROOT) -> str:
    """Return the key for SITE_INPUTS at `commit`: a hash of their paths and contents."""
    # git and the arguments are fixed; `commit` is a revision, not a shell string.
    tree = subprocess.run(  # noqa: S603
        ["git", "ls-tree", "-r", "--full-tree", commit, "--", *SITE_INPUTS],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if not tree:
        raise SystemExit(f"no site files at {commit}")
    return hashlib.sha256(tree.encode()).hexdigest()[:40]


def main(argv: list[str] | None = None) -> None:
    """Print the key for the commit given on the command line, or HEAD."""
    args = sys.argv[1:] if argv is None else argv
    print(site_key(args[0] if args else "HEAD"))


if __name__ == "__main__":
    main()
