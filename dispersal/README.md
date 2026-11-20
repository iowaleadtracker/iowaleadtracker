# dispersal

The Gaussian puff model behind `puff_dispersal.py`, one module per topic. How the model
works and its limits are in [`MODEL.md`](../MODEL.md); this file is about the code.

| Module | What's in it | Tests |
|---|---|---|
| `constants` | physical constants, unit conversions | |
| `types` | type aliases (annotations only) | |
| `units` | parsing masses, concentrations, size distributions, times | `test_units` |
| `source_term` | explosion cloud height and TNT equivalence, materials, size presets, release cases | `test_source_term` |
| `particles` | diameter, slip correction, settling velocity | `test_particles` |
| `deposition` | dry deposition (Zhang et al. 2001), drop collection (Slinn 1984) | `test_deposition` |
| `dispersion` | stability classes, Briggs sigma curves, puff growth, ground reflection, `erf` | `test_dispersion` |
| `met` | Open-Meteo download and cache, the met field, transport winds | `test_model` |
| `model` | the puff model (`run_model`) | `test_model`, `test_regression` |
| `grid` | puff records to hourly map fields, ensemble smear | `test_model`, `test_regression` |
| `output` | packed fields, HYSPLIT files, the HTML page | `test_output` |

## Rules

- **Imports point down.** `constants` and `types` import nothing from the package;
  `particles`, `units`, `source_term`, `dispersion` and `output` sit on them; then
  `deposition`, `met` and `grid`; `model` is on top. Nothing here imports
  `puff_dispersal.py`, which is only the command line and the run driver.
- **Physics gets a source.** A function that implements a published method names it in
  a `References` section of its docstring, using the works on the site's References list.
  A named constant with a physical meaning says where it comes from.
- **Refactors leave the maps bit-identical.** Floating-point results depend on the order
  of operations, so moving or tidying code must not reorder arithmetic. Prove it: build
  the site before and after, then run `tools/compare_site.py` (see the main README).
- **Changing the physics is a decision.** If the maps should change, regenerate the
  golden file (`python -m tests.test_regression`) and say why in the commit.
