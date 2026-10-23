"""
Headless checks for the CEA engine and config handling.

    python -m pytest

The reference numbers come from the v1.0.0 cleanup, where every saved config
gave identical results in the old monolithic app and the new package.
"""

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "configs" / "example_HTPB_AP_baseline.ceacfg"


@pytest.fixture(scope="module")
def panel():
    from PyQt6.QtWidgets import QApplication

    from propellant_analyzer.input_panel import InputPanel

    app = QApplication.instance() or QApplication([])
    yield InputPanel()
    del app


def test_example_config_runs(panel):
    from propellant_analyzer.cea_engine import run_cea
    from propellant_analyzer.config import read_config

    panel.load_config(read_config(str(EXAMPLE)))
    r = run_cea(panel.get_config())
    assert abs(r["total_all_wt"] - 100.0) < 0.1
    assert 4500 < r["cstar"] < 5500
    assert 230 < r["isp_vac"] < 300
    assert r["Tc_K"] > 2500
    assert len(r["eps_range"]) == 180
    assert r["flame_analysis"]["family_rows"] is not None
    assert "THEORETICAL ROCKET PERFORMANCE" in r["full_output"]


def test_legacy_config_migration():
    from propellant_analyzer.config import migrate_config

    old = {
        "eps": 9.0,
        "units": "Imperial",
        "motor_sim": {"hardware": {"nozzle_mode": "Use exit diameter",
                                   "throat_dia_in": 0.5, "exit_dia_in": 1.5}},
    }
    new = migrate_config(old)
    assert "motor_sim" not in new and "units" not in new
    assert new["eps"] == pytest.approx(9.0)  # (1.5 / 0.5) ** 2

    kept = migrate_config({"eps": 12.5, "motor_sim": {"hardware": {"nozzle_mode": "Use expansion ratio"}}})
    assert kept["eps"] == 12.5


def test_stale_output_dir_falls_back():
    from propellant_analyzer.paths import DEFAULT_OUTPUT_DIR, resolve_output_dir

    assert resolve_output_dir(r"C:\RocketCEA\Propellant Analyzer 9000\Formula Outputs_does_not_exist") == str(DEFAULT_OUTPUT_DIR)


def test_bundled_data_is_valid_json():
    from propellant_analyzer import paths

    for p in (paths.INGREDIENTS_DB, paths.SEED_USER_DB):
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        assert isinstance(data, list) and data


def test_density_flags_and_cards():
    from propellant_analyzer import database as DB

    gas = DB._find_ingredient("O2_GAS")
    assert DB.density_status(gas) == "none" and DB.density_text(gas) == "none"
    _, card, *_ = DB.card_in("O2_GAS")
    assert "rho" not in card  # no density -> card without rho
    est = DB._find_ingredient("TETRAZOLE")
    assert DB.density_status(est) == "estimated" and DB.density_text(est).endswith("(est.)")
    assert DB.density_status(DB._find_ingredient("AP_CUSTOM")) == "measured"
    # no ingredient keeps the old 0.001 g/cc placeholder
    assert all(abs(float(i.get("density", 0)) - 0.001) > 1e-9 for i in DB.get_all_ingredients())


def test_blend_density_reports_estimates():
    from propellant_analyzer.cea_engine import blend_density_info

    info = blend_density_info([{"name": "AP_CUSTOM", "wt_pct": 80}, {"name": "TETRAZOLE", "wt_pct": 20}])
    assert info["value"] and info["estimated"] == ["TETRAZOLE"] and not info["missing"]
    info = blend_density_info([{"name": "AP_CUSTOM", "wt_pct": 80}, {"name": "MERCUROUS_AZIDE", "wt_pct": 20}])
    assert info["value"] is None and info["missing"] == ["MERCUROUS_AZIDE"]


def test_exit_temperature_plateau_detection():
    import numpy as np

    from propellant_analyzer.tabs.charts import ChartsTab

    er = np.linspace(1, 20, 39)
    te = np.where(er < 6, 3000 - 120 * er, np.where(er < 9, 2327.0, 2327 - 20 * (er - 9)))
    e0, e1, t = ChartsTab.find_exit_plateau(er, te)
    assert abs(t - 2327.0) < 1e-9 and 5.5 < e0 < 6.5 and 8.5 < e1 < 9.5
    assert ChartsTab.find_exit_plateau(er, 3000 - 50 * er) is None
