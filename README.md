# Iowa Lead Tracker

Open, unofficial model of where lead from the Army's planned lead azide detonation at the
Iowa Army Ammunition Plant could travel and settle. The maps are at
**https://iowaleadtracker.com**.

The Army hasn't released the inputs, data, or model runs behind its public safety maps.
This repo holds everything behind ours: the model, the weather forecasts it used, the
assumptions, and the sources, so anyone can check, test, and improve it.

## This is not official

The U.S. Army, the Iowa Army Ammunition Plant, and government agencies didn't make this
model, and none of them have checked it. The numbers are estimates built on assumptions
that may be wrong. Don't use it to decide if you're safe; follow the instructions of local
officials.

## What's here

| Path | What it is |
|---|---|
| `puff_dispersal.py` | the command line: options, weather models and ensemble, and the map page |
| `dispersal/` | the Gaussian puff model, one module per topic: units, source term, particles, deposition, dispersion, weather, the model, gridding, output |
| `template.html` | the interactive map page the model fills in |
| `MODEL.md` | how the model works, every option, and its limits |
| `validate_explosion.py`, `validation_output.txt` | checks of the explosion source against published results |
| `scenarios/iowa-aap-2026-11-20/` | the Iowa scenario: site build scripts, saved forecasts, and a README with every assumption and source |
| `tests/` | the test suite: physics checked against published values, model properties, a golden run, and the site's safety wording |
| `tools/compare_site.py` | proves two site builds are identical apart from build times |

## Run it

Python 3.10 or newer.

```bash
pip install -r requirements.txt

# one map: the EPA permit case, noon, using the saved forecasts
python3 puff_dispersal.py --lat 40.825518 --lon -91.266502 \
    --time 2026-11-23T12:00-06:00 --release-case permit-100 \
    --material lead-azide --explosive-mass 9700lb --specific-energy 1.64 \
    --shots 2 --confinement earth-covered --hours 8 --dt 60 --grid 360 \
    --weather-model gfs_seamless \
    --met-cache scenarios/iowa-aap-2026-11-20/met_cache/map_met_all.json \
    -o permit-noon.html

# the whole site: 4 cases x 7 blast times, written to scenarios/.../outputs/site/
python3 scenarios/iowa-aap-2026-11-20/make_map_picker.py --build
```

Open the HTML file in a browser. The saved forecasts in `met_cache/` reproduce the live
site on any date (the site build passes `--as-of`, the time they were pulled); delete the
cache file to download fresh forecasts from Open-Meteo. A mirror of the site, built from
this repository, is at https://iowaleadtracker.github.io/ for readers who can't reach
iowaleadtracker.com. The `--publish`
and `--deploy` options are for the maintainer; anyone else can serve `outputs/site/` from
any static web host.

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
pre-commit install          # lint, format, type-check and fast tests on every commit

pytest -m "not slow"        # fast tests, under a second
pytest                      # everything, including full model runs (about 10 s)
pre-commit run --all-files  # every check on every file
```

GitHub Actions (`.github/workflows/ci.yml`) runs the same hooks, the full test suite and
an offline build of the site on every branch push and pull request.

Linting is ruff with nearly every rule on, plus mypy type checking; the settings and the
reasons for each exception are in `pyproject.toml`. Tests never use the network: model
runs use a steady wind or the saved forecasts. Physics tests name the published source
of each reference value in their docstrings.

`tests/test_regression.py` pins the numbers of one published map (EPA permit case, noon).
If a change is meant to alter the maps, regenerate it with `python -m tests.test_regression`
and say why in the commit. For a change that should *not* alter any map, rebuild the site
and compare it with a build from before the change:

```bash
python3 tools/compare_site.py OLD/outputs/site scenarios/iowa-aap-2026-11-20/outputs/site
```

## Questions and corrections

Open an issue. Corrections to the inputs, physics, or sources are especially welcome. If
you measure lead after the detonation, a comparison with the model is welcome too, good or
bad.

## License

- Code: MIT (see `LICENSE`).
- Maps, text, and images: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
- Weather data in `met_cache/`: from Open-Meteo (https://open-meteo.com), CC BY 4.0, which
  passes along data from NOAA, ECMWF, DWD, Environment Canada, and the UK Met Office.
- Basemap tiles on the maps load from Esri at view time and follow Esri's terms.
