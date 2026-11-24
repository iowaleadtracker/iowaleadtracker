# Tracer data

Measured crosswind spread (σy) and the weather it was measured in, for checking the
spread schemes offline (`tests/test_turbulence.py`, `tools/tracer_sigma_y.py`,
TURBULENCE.md).

## `prairie_grass_sigma_y.csv`

Project Prairie Grass, O'Neill, Nebraska, 1956 (Barad 1958): continuous SO2 releases at
0.46 m, sampled over 10 minutes on arcs at 50, 100, 200, 400 and 800 m. 56 runs with
weather, 280 arc values.

- `run`, `x_m`, `sigma_y_m`: from J. S. Irwin's analysis of the observations,
  `PGrassOBSAnalysis.txt` (column `Sy`), https://harmo.org/jsirwin/Model_Evaluation-March2013.html.
- `u_star_ms`, `w_star_ms`, `obukhov_m`, `zic_m`, `zim_m`, `z0_m`, `u_ms`, `z_ref_m`: from
  the AERMOD surface file `PGRSURF.MET` in the ASTM D6589 archive (`D6589Archive.zip`,
  `D6589/PrairieGrass/DispersionModeling/AERMOD/`), https://harmo.org/jsirwin/Model_Evaluation-ASTM-EXAMPLE.html,
  matched by date and hour. `w_star_ms` is 0 where the file gives -9 (stable). `zic_m`
  is -999 where there is no convective height; use the larger of the two heights.

## `sagebrush1_sigma_y_10min.csv`

Project Sagebrush Phase 1, Idaho National Laboratory, October 2013 (Finn et al. 2015,
2016): continuous SF6 releases at 1.5 m, 10-minute bag samples on arcs at 200 to 3,200 m,
daytime, stability classes A–D. 169 values.

- `sigma_y_m`: second-moment σy on non-truncated cross-sections, read from the vector data
  of Fig. 212 of NOAA Tech. Memo OAR ARL-268 (doi:10.7289/V5VX0DHV,
  https://repository.library.noaa.gov/view/noaa/11188), better than about 1%; each point
  was matched to its bag by its z/L at both sonics.
- `U10_COC_ms`, `WD10_deg`, `sigth10_COC_deg` (COC tower, 10 m), `ustar_R3`, `ustar_R4`,
  `zL_R3`, `zL_R4` (sonics at 3.2 m on the 3,200 m arc), `PG_sigA`, `PG_SRDT`: the bag's
  row in the memo's Tables 19–23. `L_R*_m` = 3.2 / (z/L), computed here.
- `note`: "matched on one sonic only" where the other sonic's z/L is off the figure's
  scale. IOP 3 bags 9 and 10 have identical z/L and could not be told apart: their rows
  give both bags' weather as `a|b` and are used with the mean.
- Mixing heights are not in the file: the evaluation uses the mean of the memo's Table 18
  radiosonde values for each test (1,250, 1,110, 865, 2,030 and 1,150 m for IOPs 1–5).
