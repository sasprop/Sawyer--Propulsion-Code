# Changelog

All notable changes to Propellant Analyzer. Versions follow
[semantic versioning](https://semver.org/): MAJOR.MINOR.PATCH.

## [Unreleased]

## [1.2.0] - 2026-10-26

### Added
- ISP chart hover readout: a crosshair follows the mouse and lists every plotted curve's value at that
  expansion ratio (Isp in s, temperatures in the selected unit).
- Run History panel on the ISP chart. Every completed run is saved (last 100, kept across sessions in
  `run_history.json`). Tick runs to overlay them on the current run; pick which curve to compare
  (ambient / ambient-with-eta / vacuum Isp, or exit / throat / chamber temperature). Each run keeps a
  fixed colour, dots mark each run's design eps, names can be renamed in place, runs can be removed.
- "Add config..." runs one or more saved .ceacfg files in the background and overlays them without
  touching the current inputs.

### Changed
- CEA solves are serialized (RocketCEA's Fortran core is not thread-safe), so overlay runs queue
  behind the main run instead of running at the same time.

## [1.1.0] - 2026-10-23

### Added
- Density provenance for every ingredient: measured, **estimated**, or **not available**.
  Shown in the ingredient browser ("(est.)" / "none" plus the source note), editable in the
  add/edit ingredient dialog ("Density source"), and flagged on the Performance tab when a run
  uses an estimated density or an ingredient with none.
- The ISP chart (Temperature view) shades and labels the flat stretch in the exit-temperature
  curve; the Wiki explains it (Al2O3 freezing at 2327 K in shifting equilibrium).

### Changed
- The 114 ingredients that carried a 0.001 g/cc placeholder density now have the allprop.dat value of
  their condensed-phase entry, a literature value (14), an estimate (54, marked: atomic-volume increments
  fitted to allprop.dat, or a sibling entry), or no density (23). 17 gas-phase entries are flagged as
  having no condensed density. A CEA card is written without rho when there is no density.
- Blend density reports which estimated densities it used, or which ingredient has none.

### Fixed (ingredient values not covered by allprop.dat)
- Values that had been entered as cal/g in the kcal/mol column, now converted with PEP data:
  ammonium carbonate, ammonium oxalate, monoammonium oxalate monohydrate.
- TiO2 Hf -73.0 -> -225.8 kcal/mol (used by AST3: vacuum Isp 270.56 -> 269.23 s).
- Tepanol HX-878 Hf -0.146 -> about -83 kcal/mol (estimate; used by VSP1: 221.40 -> 221.34 s).
- DDI, PBAN, PEG, PPG, castor oil, urea (formula was wrong), B4C, Cr2O3, NH4F, Sr/Ba nitrate,
  HDPE, water vapour; densities of triphenylbismuth, erythritol, naphthalene, vanadium.
- Seven colorant salts (Sr/Ba nitrate, SrCO3, Li2CO3, CuCl2, CaCl2, Na2C2O4) were weight-track only;
  they are now CEA-ready so the Flame Color tab can see their emitters.
- 15 liquids (ClF3, ClF5, ClF3O, liquid F2 / OF2 / NF3, diborane, HNO3, N2F4, ...) were using the
  gas-phase allprop.dat entry; switched to the condensed entry's Hf and density.

## [1.0.1] - 2026-10-23

### Fixed (ingredient database, cross-checked against the AFCEI allprop.dat list)
- All 285 entries that map to allprop.dat were compared for heat of formation, density and formula.
- DEKAZENE formula was B10H28N2; corrected to B10H18N2.
- The old allprop importer let later library additions overwrite earlier entries that shared a short
  name. Restored the original values and moved the overwriting entries to their own records:
  TA (triacetin, was tantalum -> new TANTALUM), CA (cellulose acetate, was cyanuric acid -> new CYANURIC_ACID),
  LOX / LH2 / liquid N2 / liquid methane (had gas or slush values -> new O2_GAS, H2_GAS, N2_GAS, SLUSH_METHANE),
  MAGNESIUM_ALUMINUM_ALLOY (was spinelium -> new SPINELIUM), H2O (was water vapour -> new WATER_VAPOR).
- NTO now uses the liquid N2O4 entry (#36, Hf -4.68 kcal/mol, 1.431 g/cc) instead of the gas entry
  (#102, no density); the gas entry is kept as N2O4_GAS.
- ETHYLENE_LIQUID_AT_NBP carried PE / POLYETHYLENE aliases, so looking up "PE" returned ethylene.
- Bundled fallback library: DOA and OXAMIDE now match allprop.dat (they were already correct in the user library).
- None of the saved configs use a changed ingredient; their results are unchanged.

## [1.0.0] - 2026-10-21

First clean release. The project was rebuilt from the old `Propellant Analyzer 9000/CEA_App.py`
(12,700 lines in one file) into a package.

### Kept
- Formulation sidebar: solids table, binder system with NCO/OH cure calculator or manual entry,
  run conditions, ambient pressure / altitude, efficiency factors, ingredient database and dialogs.
- Tabs: Performance, ISP Chart, Chemistry, Flame Color, Wiki, Raw CEA Output (with save to Formula Outputs).
- CEA results are identical to the old app for every saved config (checked number-for-number).

### Removed
- Grain Design, Wired Endburner, Nozzle View, erosive burning (Lenoir-Robillard), motor simulation,
  motor hardware inputs, the units preference that only applied to those, and the `motor/` package.
- Dead code: the unused CureCalcPanel, unreachable cure-calc branch, unused database and analysis helpers.
- Unrelated scripts and folders (moved to `_archive/` outside git): Rheology, Wired endburners,
  OpenMotor Analysis, cea_web, third_party, tools, root-level test scripts, Rocket Files reference PDFs.
- Git history restarted. The old 1.8 GB history (PDFs, openMotor binaries) is kept locally on
  branch `legacy-main` and is not pushed.

### Added
- Standalone Windows build (PyInstaller): `build.bat`, `packaging/PropellantAnalyzer.spec`, `--selftest`.
- Proper file locations for source runs vs. the packaged app (`paths.py`), with fallback for stale
  output folders in old configs.
- Old-config migration: motor sections are dropped; "Use exit diameter" nozzle mode is converted to eps.
- Version shown in the title bar, Help > About, saved configs and output files; `scripts/bump_version.py`.
- `setup.bat`, `run.bat`, tests, README.
