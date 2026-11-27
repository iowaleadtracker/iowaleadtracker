# tests

```bash
pytest -m "not slow"   # fast tests: run by the pre-commit hook on every commit
pytest                 # everything, including full model runs (about 10 s)
```

| File | What it covers |
|---|---|
| `test_units.py` | input parsing and unit conversions |
| `test_source_term.py` | TNT equivalence and Church cloud height, incl. HotSpot's worked examples |
| `test_particles.py` | slip correction and settling speed against published tables |
| `test_deposition.py` | the shape of the dry-deposition and drop-collection curves |
| `test_dispersion.py` | Briggs coefficients, puff growth, ground reflection, the stability table |
| `test_turbulence.py` | `--spread turbulence`: published formulas, minimums, growth, mass conservation, and σy against the Prairie Grass and Sagebrush tracer data in `data/tracer/` |
| `test_model.py` | whole-model properties: mass conserved, linear in mass released, plume direction, analytic comparison |
| `test_regression.py` | golden numbers for one published map |
| `test_met.py` | Open-Meteo requests: the API key's customer servers, and keys kept out of the cache |
| `test_output.py` | packed fields and safe embedding in the HTML |
| `test_cli.py` | `--help` and option checks |
| `test_site.py` | the site's safety wording, headers and defaults |
| `test_brief_page.py` | the monitor-placement page: warnings, no outside files, all of the README shown, written into the site and the mirror |
| `test_map_fixtures.py` | the browser tests' saved map data still has every key the model writes |

## Browser tests of the map page

```bash
pnpm install && pnpm test:map   # Node from .nvmrc; every engine, desktop and phone
pnpm test:map --project=chromium-desktop   # one engine: chromium-, firefox-, webkit-
```

`frontend/map.spec.js` (Playwright) runs in Chromium (Chrome, Edge), Firefox and WebKit
(Safari's engine) on desktop, and on a phone in Chromium and WebKit. It opens
`template.html` with saved map data put in the way `dispersal/output.py` does it, served
from memory with every outside request blocked: no build, no server, no Python. It checks that the page loads and every control works
without errors, the units and peak values, the HYSPLIT and Army-zone boxes, escaping of
text from the data, the basemap credit, dark mode, saved choices, and the phone layout.

The data, `frontend/fixtures/forecast.json` and `archived.json`, is two real maps (the
Army mitigated case at 9:00, forecast and archived weather) on a coarse grid. When the
model starts writing a new key the page reads, `test_map_fixtures.py` fails; remake them
with `python3 tools/refresh_map_fixtures.py` (about 20 s, from the saved forecasts).

## Rules

- **Never use the network.** `conftest.py` makes every download fail. Model runs use a
  steady wind (`--wind`) or the saved forecasts in `scenarios/.../met_cache/`.
- **Runs on saved forecasts need the `frozen_clock` fixture.** The model chooses forecast
  or archive data by comparing the run time with "now"; without the frozen clock those
  runs stop matching the saved forecasts a week after they were pulled.
- **Mark model runs `slow`.** Anything that runs `simulate` or `run_model` takes seconds;
  the pre-commit hook skips `slow` tests to stay under a second.
- **Cite reference values, or don't call them published.** A test that compares with a
  published number names the source in its docstring and explains its tolerance. A value
  that can't be traced to a source is an internal-consistency check and is described that
  way. Never invent a citation.
- **The golden file changes only on purpose.** `data/golden_permit_0900.json` pins one
  published map. If a change is meant to alter the maps, regenerate it with
  `python -m tests.test_regression` and say why in the commit. If it isn't, a failure
  here is a bug.
- **Don't weaken `test_site.py`.** It guards the warnings that keep the site from being
  read as an official safety map. Change the wording on the site and in the test
  together, never just the test.
