#!/usr/bin/env python3
"""Check that two builds of the site are the same apart from build timestamps.

Used to prove that code changes which should not change any output really don't:

    python3 tools/compare_site.py OLD_SITE_DIR NEW_SITE_DIR

Each ``maps/*.html`` page embeds the model output as JSON. The payloads are compared
exactly (every number, every string) after dropping ``meta.generated``, the build
time. The landing page is compared as text after removing the build-time phrases and
the content-hashed map file names, which change whenever ``generated`` does.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

MARKER = "const DATA = "
# Phrases on the landing page that carry the build time, and hashed map names.
VOLATILE = [
    re.compile(r"As of this update \([^)]*\)"),
    re.compile(r"Last updated [^<.]*\."),
    re.compile(r'const BUILT = "[^"]*";'),
    re.compile(r"<lastmod>[^<]*</lastmod>"),
    re.compile(r'"dateModified":\s*"[^"]*"'),
    # m/permit-0900-<hash>, m/2026-11-26-permit-0900-<hash>, m/archived-permit-0900-<hash>
    re.compile(r"m/((?:\d{4}-\d\d-\d\d-)?(?:[a-z]+-)?[a-z]+-\d{4})-[0-9a-f]{10}"),
]


def payload(page: Path) -> dict[str, Any]:
    """Return the model payload embedded in a map page, without the build time."""
    text = page.read_text(encoding="utf-8")
    start = text.index(MARKER) + len(MARKER)
    data: dict[str, Any] = json.JSONDecoder().raw_decode(text, start)[0]
    data["meta"].pop("generated", None)
    return data


def first_difference(a: Any, b: Any, path: str = "") -> str | None:  # noqa: ANN401 - JSON values
    """Return the key path of the first difference between two JSON values, if any."""
    if type(a) is not type(b):
        return f"{path or '/'}: type {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        return _dict_difference(a, b, path)
    if isinstance(a, list):
        return _list_difference(a, b, path)
    return None if a == b else f"{path}: {a!r} != {b!r}"


def _dict_difference(a: dict[str, Any], b: dict[str, Any], path: str) -> str | None:
    for key in sorted(set(a) | set(b)):
        if key not in a or key not in b:
            return f"{path}/{key}: missing on one side"
        found = first_difference(a[key], b[key], f"{path}/{key}")
        if found:
            return found
    return None


def _list_difference(a: list[Any], b: list[Any], path: str) -> str | None:
    if len(a) != len(b):
        return f"{path}: length {len(a)} != {len(b)}"
    for i, (x, y) in enumerate(zip(a, b, strict=True)):
        found = first_difference(x, y, f"{path}[{i}]")
        if found:
            return found
    return None


def normalized_index(site: Path) -> str:
    """Return the landing page with build-time phrases and hashed names neutralized."""
    text = (site / "index.html").read_text(encoding="utf-8")
    for pattern in VOLATILE:
        text = pattern.sub(lambda m: m.group(1) if m.groups() else "", text)
    return text


def main(argv: list[str]) -> int:
    """Compare two site directories; return 0 when they match."""
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print("usage: compare_site.py OLD_SITE_DIR NEW_SITE_DIR", file=sys.stderr)
        return 2
    old, new = (Path(p) for p in argv)
    names = sorted(p.name for p in (old / "maps").glob("*.html"))
    if names != sorted(p.name for p in (new / "maps").glob("*.html")):
        print("different sets of map pages", file=sys.stderr)
        return 1
    bad = 0
    for name in names:
        diff = first_difference(payload(old / "maps" / name), payload(new / "maps" / name))
        if diff:
            bad += 1
            print(f"DIFFERENT {name}: {diff}")
    if normalized_index(old) != normalized_index(new):
        bad += 1
        print("DIFFERENT index.html (after removing build times)")
    print(f"{len(names)} maps compared, {bad} difference(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
