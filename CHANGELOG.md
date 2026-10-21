# Changelog

All notable changes to Propellant Analyzer. Versions follow
[semantic versioning](https://semver.org/): MAJOR.MINOR.PATCH.

## [Unreleased]

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
