# Propellant Analyzer

Desktop tool for solid-propellant formulation, built on NASA CEA through
[RocketCEA](https://rocketcea.readthedocs.io/).

| Tab | What it does |
| --- | --- |
| **Formulation** (left sidebar) | Solids table, binder system with the NCO/OH cure calculator or manual entry, run conditions, ambient pressure / altitude, efficiency factors |
| **Performance** | c\*, vacuum / ambient / ideal Isp and density Isp, exit Mach, nozzle expansion state, Tc / Tt / Te, gamma, exit molar mass, density |
| **ISP Chart** | Isp, density Isp, temperature or exit Mach vs. expansion ratio. Hover for values; overlay past runs or saved configs from the Run History panel |
| **Chemistry** | Oxygen balance and atom inventory |
| **Flame Color** | Likely visible emitters in the exhaust, with an alumina-smoke penalty |
| **Wiki** | What every input and output means, filled in with your current values |
| **Raw CEA Output** | Full CEA text, and **Save Full Output File** to write a run to `Formula Outputs/` |

## Quick start (Windows)

1. Install Python 3.11 or 3.12 from python.org (tick "Add Python to PATH").
2. Double-click **`setup.bat`** once. It creates `.venv` and installs everything.
3. Double-click **`run.bat`** to start the app.

Or by hand:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python run.py
```

## Building the standalone app

```powershell
build.bat            # -> dist\PropellantAnalyzer\PropellantAnalyzer.exe  + a zip of that folder
build.bat onefile    # -> dist\PropellantAnalyzer-<version>.exe (single file, slower to start)
```

Hand someone the zip (or the single exe). They need nothing else installed.

To check a fresh build works without clicking through it:

```powershell
dist\PropellantAnalyzer\PropellantAnalyzer.exe --selftest
type "%USERPROFILE%\Documents\Propellant Analyzer\selftest.txt"
```

## Where files go

| | Running from source (`run.bat`) | Packaged `.exe` |
| --- | --- | --- |
| Saved runs | `Formula Outputs\` in this folder | `Documents\Propellant Analyzer\Formula Outputs\` |
| Configs (default folder for Load/Save) | `configs\` in this folder | `Documents\Propellant Analyzer\configs\` |
| Run history (chart overlays) | `run_history.json` in this folder | `Documents\Propellant Analyzer\run_history.json` |
| Your ingredient library | `src\propellant_analyzer\data\user_ingredients.json` (tracked in git) | `Documents\Propellant Analyzer\user_ingredients.json` (copied from the bundled one on first launch) |

`Formula Outputs\`, `run_history.json` and your personal `configs\*.ceacfg` are git-ignored. Only
`configs\example_*.ceacfg` is committed. Set the environment variable
`PROPELLANT_ANALYZER_HOME` to use a different folder for all of the above.

Configs saved by older versions (with motor / grain / nozzle sections) still
load. The removed sections are ignored, and old output paths that no longer
exist fall back to the default folder.

## Project layout

```
run.py                      entry point (source runs and PyInstaller)
src/propellant_analyzer/
    __init__.py             version number lives here
    app.py                  QApplication start-up, --selftest
    main_window.py          menus, tabs, config load/save
    input_panel.py          formulation sidebar + cure calculator
    ingredients_ui.py       ingredient table, picker and add-ingredient dialog
    cea_engine.py           run_cea(cfg): the RocketCEA solve (no GUI needed)
    flame_color.py          emitter map and flame-colour scoring
    propellant_analysis.py  altitude/pressure, ideal expansion, atoms, oxygen balance
    database.py             ingredient library (bundled + user)
    config.py               .ceacfg read/write + migration of old configs
    paths.py                every file location, source vs. frozen
    theme.py, widgets.py    styling and shared widgets
    tabs/                   one module per results tab
    data/                   ingredients.json, user_ingredients.json, atomic_masses.txt
packaging/PropellantAnalyzer.spec   PyInstaller build definition
scripts/bump_version.py     release helper
tests/                      python -m pytest
configs/example_*.ceacfg    example config (personal configs are ignored)
```

## Versions and releases

The version lives in one place: `src/propellant_analyzer/__init__.py`. It shows
in the window title, Help > About, saved configs, saved output files and the
.exe's file properties.

1. Add notes under `## [Unreleased]` in `CHANGELOG.md` as you work.
2. When ready: `python scripts\bump_version.py patch` (or `minor` / `major`).
   This updates the version, dates the changelog, commits, and tags `vX.Y.Z`.
3. `git push && git push --tags`
4. `build.bat` and attach the zip from `dist\` to a GitHub Release for that tag.

Rule of thumb: **patch** for fixes, **minor** for new features, **major** when
old configs would stop loading.

## Tests

```powershell
python -m pytest
```

Runs a CEA solve on the example config, checks old-config migration, and checks
the bundled data files.
