# Changelog

All notable changes to Propellant Analyzer. Versions follow
[semantic versioning](https://semver.org/): MAJOR.MINOR.PATCH.

## [Unreleased]

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
