# Notes for contributors and coding agents

Iowa Lead Tracker is an unofficial public model of where lead from a planned detonation
could travel. People may read it during an emergency, so accuracy and clear warnings
matter more than features. Start with `README.md`; the model is in `MODEL.md`, the
Iowa scenario and every assumption in `scenarios/iowa-aap-lead-azide/README.md`.

## Layout

- `puff_dispersal.py`: the command line and run driver.
- `dispersal/`: the model, one module per topic (see its README).
- `scenarios/iowa-aap-lead-azide/`: the site build (`make_map_picker.py`), page text
  (`forecast_summary.py`, `works_cited.py`, `index_template.html`) and saved forecasts.
- `tests/`: the test suite (see its README). `tools/compare_site.py`: build comparison.

## Before you finish a change

```bash
pre-commit run --all-files   # ruff, ruff format, mypy, fast tests, file checks
pytest                       # the full suite
pnpm install && pnpm lint    # front-end lint: oxlint (JS), ESLint (HTML, CSS); Node from .nvmrc
pnpm test:map                # the map page in a browser (Playwright), with saved map data
```

CI (`.github/workflows/ci.yml`) runs these, plus an offline site build, on every push
(the front-end lint and map tests on every branch but `main`, so not on the merge);
`main` only takes changes through a reviewed pull request.

If the change should not alter the published maps, prove it:

```bash
cp -R scenarios/iowa-aap-lead-azide/outputs/site /tmp/site-before   # build first if empty
python3 scenarios/iowa-aap-lead-azide/make_map_picker.py --build
python3 tools/compare_site.py /tmp/site-before scenarios/iowa-aap-lead-azide/outputs/site
```

## Rules

- **Don't change the maps by accident.** Any change to the numbers must be intended,
  explained in the commit, and reflected in `tests/data/` (`python -m tests.test_regression`).
  A forecast refresh (`tools/refresh_forecast.py`) regenerates it for you.
- **Don't weaken the warnings.** "Unofficial estimate, not from the Army or any government
  agency", "Don't use it to decide if you're safe", and the caveat after every list of
  towns must stay wherever they appear (page, map banner and legend, summary, FAQ,
  `llms.txt`, share image). `tests/test_site.py` enforces this.
- **No per-address verdicts.** The site never says a place is safe or unsafe, and never
  tells people to stay or leave; it points them to official instructions.
- **Cite only what you can verify.** New sources go in `works_cited.py` and the docstrings
  that use them. If a source can't be checked, say so rather than cite it.
- **Don't deploy or publish without the maintainer.** Merging to `main` is deploying:
  `.github/workflows/deploy.yml` deploys iowaleadtracker.com and the mirror at
  iowaleadtracker.github.io rebuilds from `main` too. `make_map_picker.py --deploy` and
  `--publish` (by hand) also change the live site. Never commit `deploy.local.json` (it
  holds the Cloudflare account ID; it is git-ignored) or any token.
- **Dated statements need rechecking.** Every build restamps "As of this update, a FEMA
  emergency alert ... sets the detonation for 9 a.m. Wednesday"; the summary and About dialog also report the
  court pause and the Iowa HHS time. Check the
  news before merging to `main` (which deploys) or deploying by hand.
- **Keep tests offline.** No test may use the network (see `tests/README.md`).
- **Keep the saved forecasts as they are.** `met_cache/map_met_all.json` reproduces the
  live site byte for byte. Refreshing it is a deliberate step (`tools/refresh_forecast.py`, or the
  scheduled `refresh-forecast` workflow's pull request; scenario README, "Refreshing on the day"); older pulls go in an ignored `met_cache_retrieved_*` folder.
