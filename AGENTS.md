# Notes for contributors and coding agents

Iowa Lead Tracker is an unofficial public model of where lead from a planned detonation
could travel. People may read it during an emergency, so accuracy and clear warnings
matter more than features. Start with `README.md`; the model is in `MODEL.md`, the
Iowa scenario and every assumption in `scenarios/iowa-aap-2026-11-20/README.md`.

## Layout

- `puff_dispersal.py`: the command line and run driver.
- `dispersal/`: the model, one module per topic (see its README).
- `scenarios/iowa-aap-2026-11-20/`: the site build (`make_map_picker.py`), page text
  (`forecast_summary.py`, `works_cited.py`, `index_template.html`) and saved forecasts.
- `tests/`: the test suite (see its README). `tools/compare_site.py`: build comparison.

## Before you finish a change

```bash
pre-commit run --all-files   # ruff, ruff format, mypy, fast tests, file checks
pytest                       # the full suite
```

If the change should not alter the published maps, prove it:

```bash
cp -R scenarios/iowa-aap-2026-11-20/outputs/site /tmp/site-before   # build first if empty
python3 scenarios/iowa-aap-2026-11-20/make_map_picker.py --build
python3 tools/compare_site.py /tmp/site-before scenarios/iowa-aap-2026-11-20/outputs/site
```

## Rules

- **Don't change the maps by accident.** Any change to the numbers must be intended,
  explained in the commit, and reflected in `tests/data/` (`python -m tests.test_regression`).
- **Don't weaken the warnings.** "Unofficial estimate, not from the Army or any government
  agency", "Don't use it to decide if you're safe", and the caveat after every list of
  towns must stay wherever they appear (page, map banner and legend, summary, FAQ,
  `llms.txt`, share image). `tests/test_site.py` enforces this.
- **No per-address verdicts.** The site never says a place is safe or unsafe, and never
  tells people to stay or leave; it points them to official instructions.
- **Cite only what you can verify.** New sources go in `works_cited.py` and the docstrings
  that use them. If a source can't be checked, say so rather than cite it.
- **Don't deploy or publish without the maintainer.** `make_map_picker.py --deploy` and
  `--publish` change the live site. Pushing to `main` changes the public mirror at
  iowaleadtracker.github.io within the hour (its workflow builds from `main`), so treat a
  push like a deploy, and push before deploying so both copies match. Never commit `deploy.local.json` (it holds the
  Cloudflare account ID; it is git-ignored).
- **Dated statements need rechecking.** Every build restamps "As of this update, the
  Army hasn't announced a Monday time itself"; the summary and About dialog also report the
  court pause and the Iowa HHS time. Check the
  news before a build that will be deployed or a push to `main`.
- **Keep tests offline.** No test may use the network (see `tests/README.md`).
- **Keep the saved forecasts as they are.** `met_cache/map_met_all.json` reproduces the
  live site byte for byte. Refreshing it is a deliberate step (scenario README,
  "Refreshing on the day"); older pulls go in an ignored `met_cache_retrieved_*` folder.
