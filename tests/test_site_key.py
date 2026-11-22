"""The key that lets the deploy reuse CI's build of the site (tools/site_key.py)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tools import site_key

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Make a tiny git repository with a site input and a file the build doesn't read."""
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "scenarios" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "other.py").write_text("y = 1\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "one")
    return tmp_path


def test_key_follows_site_files_only(repo: Path) -> None:
    first = site_key.site_key("HEAD", cwd=repo)
    assert re.fullmatch(r"[0-9a-f]{40}", first)
    (repo / "tools" / "other.py").write_text("y = 2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "not a site file")
    assert site_key.site_key("HEAD", cwd=repo) == first
    (repo / "scenarios" / "a.py").write_text("x = 2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "a site file")
    second = site_key.site_key("HEAD", cwd=repo)
    assert second != first
    assert site_key.site_key("HEAD~1", cwd=repo) == first  # any commit, not just HEAD


def test_deploy_triggers_are_covered() -> None:
    """Every path that starts a deploy is part of the key, so a reused site is current."""
    text = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
    block = text.split("paths:", 1)[1].split("workflow_dispatch", 1)[0]
    paths = re.findall(r'-\s*"([^"]+)"', block)
    assert "scenarios/**" in paths
    for p in paths:
        if p == ".github/workflows/deploy.yml":  # the deploy itself, not the build
            continue
        top = p.removesuffix("/**")
        assert top in site_key.SITE_INPUTS, p


def test_workflows_use_the_same_key() -> None:
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    deploy = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
    assert "python tools/site_key.py" in ci
    assert "name: site-${{ steps.key.outputs.key }}" in ci
    assert "python tools/site_key.py" in deploy
    assert "name: site-${{ steps.ci.outputs.key }}" in deploy
    assert '"$(python tools/site_key.py "$sha")" != "$key"' in deploy  # checks the commit
    # Without a reusable build, the deploy still tests and builds.
    assert "if: ${{ !steps.ci.outputs.run }}\n        run: python -m pytest -q" in deploy
