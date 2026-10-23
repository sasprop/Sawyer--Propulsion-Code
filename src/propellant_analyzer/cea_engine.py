"""
NASA CEA solve for a formulation (via RocketCEA).

``run_cea(cfg)`` is a plain function so it can be used from tests or scripts
without a GUI.  ``CeaWorker`` wraps it in a QThread for the app.
"""

from __future__ import annotations

import math
import re
from typing import Optional

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from rocketcea import blends
from rocketcea.cea_obj import CEA_Obj, add_new_fuel

from propellant_analyzer import database as DB
from propellant_analyzer.flame_color import analyze_flame_color_species
from propellant_analyzer.propellant_analysis import (
    atom_inventory_per_100g,
    optimal_expansion_ratio,
    oxygen_balance,
)


def _is_valid_cea_scalar(value) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except Exception:
        return False


def _supersonic_mach(eps: float, gamma: float,
                     tol: float = 1e-8, max_iter: int = 1000) -> Optional[float]:
    """
    Newton-Raphson solver for supersonic exit Mach number from area ratio.
    Returns Me, or None if convergence fails.
    """
    g  = gamma
    Me = 2.5  # Supersonic initial guess

    def residual(M):
        base = (2.0 / (g + 1.0)) * (1.0 + (g - 1.0) / 2.0 * M ** 2)
        return (1.0 / M) * (base ** ((g + 1.0) / (2.0 * (g - 1.0)))) - eps

    for _ in range(max_iter):
        dM   = 1e-6
        dfMe = (residual(Me + dM) - residual(Me - dM)) / (2.0 * dM)
        if dfMe == 0.0:
            return None
        step = residual(Me) / dfMe
        Me  -= step
        if abs(step) < tol:
            return Me

    return None


def blend_density_info(rows: list[dict]) -> dict:
    """
    Bulk reactant density from ingredient densities using additive specific
    volume:  rho_mix = total_mass / sum(mass_i / rho_i).

    The wt% inputs are proportional masses on a 100 g basis, so the mass unit
    cancels. Returns {"value", "estimated", "missing"}: value is None when any
    nonzero row has no density; "estimated" lists rows whose density is only
    an estimate.
    """
    total_mass = 0.0
    total_volume_cc = 0.0
    estimated: list[str] = []
    missing: list[str] = []

    for row in rows:
        wt_pct = max(float(row.get("wt_pct", 0.0) or 0.0), 0.0)
        if wt_pct <= 0.0:
            continue
        ing = DB._find_ingredient(row.get("name", ""))
        status = DB.density_status(ing) if ing else "none"
        density = float(ing.get("density", 0.0)) if ing else 0.0
        if status == "none" or density <= 0.0:
            missing.append(row.get("name", "?"))
            continue
        if status == "estimated":
            estimated.append(row.get("name", "?"))
        total_mass += wt_pct
        total_volume_cc += wt_pct / density

    value = None
    if not missing and total_mass > 0.0 and total_volume_cc > 0.0:
        value = total_mass / total_volume_cc
    return {"value": value, "estimated": estimated, "missing": missing}


def run_cea(cfg: dict) -> dict:
    """Run NASA CEA for one formulation and return every value the tabs display."""
    rows    = cfg["ingredients"]
    isp_eff = cfg["isp_eff"]
    Pc      = cfg["pc_psia"]
    eps     = cfg["eps"]
    Pamb    = cfg["pamb"]

    # -- Separate ingredients into CEA and excluded ---------------------
    cea_rows      = []   # (name, wt_pct) for ingredients going into CEA
    excluded_rows = []   # (name, wt_pct) excluded from CEA but tracked

    for row in rows:
        ing = DB._find_ingredient(row["name"])
        has_formula = bool(ing and ing.get("cea_formula", "").strip())
        if row.get("include_cea", True) and has_formula:
            cea_rows.append(row)
        else:
            excluded_rows.append(row)

    if not cea_rows:
        raise ValueError(
            "No ingredients with CEA thermochemical data are selected. "
            "At minimum the oxidizer, binder, and one fuel must be included in CEA."
        )

    # -- Register all CEA ingredients with RocketCEA --------------------
    for row in cea_rows:
        ing = DB._find_ingredient(row["name"])
        if ing:
            name, tag, _, _, _ = DB.card_in(row["name"])
            add_new_fuel(name, tag)

    # -- Build the propellant blend -------------------------------------
    chem_names = []
    chem_pcts  = []

    for row in cea_rows:
        name, _, _, _, _ = DB.card_in(row["name"])
        chem_names.append(name)
        chem_pcts.append(row["wt_pct"])

    total_cea_wt = sum(chem_pcts)
    total_all_wt = sum(r["wt_pct"] for r in rows)

    combo = blends.get_propellant_name(Name=chem_names, PcentL=chem_pcts)
    CEA   = CEA_Obj(propName=combo)

    # -- Core CEA calls -------------------------------------------------
    cstar_th         = CEA.get_Cstar(Pc=Pc)
    isp_vac_th       = CEA.get_Isp(Pc=Pc, eps=eps)
    isp_amb_th, mode = CEA.estimate_Ambient_Isp(Pc=Pc, eps=eps, Pamb=Pamb)

    cstar   = cstar_th   * cfg["cstar_eff"]
    isp_vac = isp_vac_th * isp_eff
    isp_amb = isp_amb_th * isp_eff

    _, gamma_ch   = CEA.get_Chamber_MolWt_gamma(Pc=Pc, eps=eps)
    valid_gamma = _is_valid_cea_scalar(gamma_ch) and float(gamma_ch) > 1.0
    valid_base_solution = (
        _is_valid_cea_scalar(cstar_th) and float(cstar_th) > 0.0 and
        _is_valid_cea_scalar(isp_vac_th) and float(isp_vac_th) > 0.0 and
        _is_valid_cea_scalar(isp_amb_th) and float(isp_amb_th) > 0.0 and
        valid_gamma
    )
    eps_ideal_res = optimal_expansion_ratio(Pc, Pamb, gamma=gamma_ch) if valid_base_solution else None
    isp_ideal = eps_ideal_val = Me_ideal = None
    if eps_ideal_res:
        eps_ideal_val, Me_ideal = eps_ideal_res
        isp_i_th, _ = CEA.estimate_Ambient_Isp(Pc=Pc, eps=eps_ideal_val, Pamb=Pamb)
        if _is_valid_cea_scalar(isp_i_th) and float(isp_i_th) > 0.0:
            isp_ideal = isp_i_th * isp_eff

    temps_R = CEA.get_Temperatures(Pc=Pc, eps=eps)
    Tc_K = temps_R[0] / 1.8
    Tt_K = temps_R[1] / 1.8
    Te_K = temps_R[2] / 1.8

    # -- Parse CEA full output ------------------------------------------
    full_out = CEA.get_full_cea_output(Pc=Pc, eps=eps, pc_units="psia")
    species_mw, species_mole = CEA.get_SpeciesMoleFractions(
        Pc=Pc, eps=eps, min_fraction=1.0e-8
    )
    species_mw = {name: float(value) for name, value in species_mw.items()}
    species_mole = {
        name: [float(v) for v in values]
        for name, values in species_mole.items()
    }
    flame_analysis = analyze_flame_color_species(species_mole)

    def _parse_float(pattern: str) -> Optional[float]:
        m = re.search(pattern, full_out)
        return float(m.group(1)) if m else None

    cea_reactant_density_gcc = _parse_float(r"REACTANT DENSITY=\s*([\d.]+)\s*G/CC")
    blend = blend_density_info(rows)
    blend_density_gcc = blend["value"]
    if blend_density_gcc is not None:
        reactant_density_gcc = blend_density_gcc
        reactant_density_source = "Ingredient blend density"
        if blend["estimated"]:
            reactant_density_source += " (uses estimated density: " + ", ".join(blend["estimated"]) + ")"
    elif cea_reactant_density_gcc is not None:
        reactant_density_gcc = cea_reactant_density_gcc
        reactant_density_source = "RocketCEA reactant density"
    else:
        reactant_density_gcc = None
        reactant_density_source = (
            "Unavailable - no density for: " + ", ".join(blend["missing"])
            if blend["missing"] else "Unavailable"
        )
    mw_m = re.search(r"MW, MOL WT\s+[\d.]+\s+[\d.]+\s+([\d.]+)", full_out)
    mol_wt_exit = float(mw_m.group(1)) if mw_m else None

    # Derived density in lb/inA3
    reactant_density_lbin3 = (reactant_density_gcc * 0.0361273
                              if reactant_density_gcc else None)

    # Exit pressure from isentropic relations
    Me_exit = _supersonic_mach(eps, gamma_ch) if valid_gamma else None
    Pe = (Pc * (1.0 + (gamma_ch - 1.0) / 2.0 * Me_exit ** 2)
          ** (-gamma_ch / (gamma_ch - 1.0))) if Me_exit else None

    # -- Isp vs eps sweep for chart (3 curves) ----------------------------
    chart_warning = None
    if valid_base_solution:
        eps_max   = max(100.0, eps * 2.0)
        eps_range = np.linspace(1.0, eps_max, 180)
        isp_vac_curve = []
        isp_amb_100pct_curve = []
        tc_curve_k = []
        tt_curve_k = []
        te_curve_k = []
        for e in eps_range:
            try:
                vac_val = CEA.get_Isp(Pc=Pc, eps=e)
                amb_val = CEA.estimate_Ambient_Isp(Pc=Pc, eps=e, Pamb=Pamb)[0]
                temp_vals = CEA.get_Temperatures(Pc=Pc, eps=e)
            except Exception:
                vac_val = float("nan")
                amb_val = float("nan")
                temp_vals = None
            isp_vac_curve.append(
                float(vac_val)
                if _is_valid_cea_scalar(vac_val) and float(vac_val) > 0.0
                else float("nan")
            )
            isp_amb_100pct_curve.append(
                float(amb_val)
                if _is_valid_cea_scalar(amb_val) and float(amb_val) > 0.0
                else float("nan")
            )
            if temp_vals and len(temp_vals) >= 3:
                tc_val = temp_vals[0] / 1.8
                tt_val = temp_vals[1] / 1.8
                te_val = temp_vals[2] / 1.8
            else:
                tc_val = float("nan")
                tt_val = float("nan")
                te_val = float("nan")
            tc_curve_k.append(float(tc_val) if _is_valid_cea_scalar(tc_val) else float("nan"))
            tt_curve_k.append(float(tt_val) if _is_valid_cea_scalar(tt_val) else float("nan"))
            te_curve_k.append(float(te_val) if _is_valid_cea_scalar(te_val) else float("nan"))
        isp_amb_eff_curve = [
            (v * isp_eff) if _is_valid_cea_scalar(v) else float("nan")
            for v in isp_amb_100pct_curve
        ]
        if not any(_is_valid_cea_scalar(v) for v in isp_amb_100pct_curve):
            chart_warning = (
                "Expansion-ratio sweep skipped because RocketCEA returned invalid ambient "
                "solutions across the requested eps range."
            )
    else:
        eps_range = np.array([], dtype=float)
        isp_vac_curve = []
        isp_amb_100pct_curve = []
        isp_amb_eff_curve = []
        tc_curve_k = []
        tt_curve_k = []
        te_curve_k = []
        chart_warning = (
            "Expansion-ratio sweep skipped because the base CEA solution returned an invalid "
            "gamma or nonphysical performance values."
        )

    # -- Atom inventory and oxygen balance (CEA ingredients only) -------
    all_keys = [r["name"] for r in cea_rows]
    all_amts = [r["wt_pct"] for r in cea_rows]
    atoms = atom_inventory_per_100g(all_keys, all_amts, DB.card_in)
    ob    = oxygen_balance(atoms)

    # -- Summary of excluded ingredients --------------------------------
    excluded_summary = [
        {
            "name":   r["name"],
            "wt_pct": r["wt_pct"],
            "reason": (
                "No CEA formula in database"
                if not bool(DB._find_ingredient(r["name"]) and
                            DB._find_ingredient(r["name"]).get("cea_formula", ""))
                else "Manually excluded by user"
            ),
        }
        for r in excluded_rows
    ]

    return {
        "cfg":                   cfg,
        "eps_used":              eps,
        "combo":                 combo,
        "total_cea_wt":          total_cea_wt,
        "total_all_wt":          total_all_wt,
        "chem_names":            chem_names,
        "chem_pcts":             chem_pcts,
        "excluded_summary":      excluded_summary,
        "cstar":                 cstar,
        "cstar_th":              cstar_th,
        "isp_vac":               isp_vac,
        "isp_vac_th":            isp_vac_th,
        "isp_amb":               isp_amb,
        "isp_amb_th":            isp_amb_th,
        "isp_ideal":             isp_ideal,
        "eps_ideal_val":         eps_ideal_val,
        "Me_ideal":              Me_ideal,
        "mode":                  mode,
        "Tc_K":                  Tc_K,
        "Tt_K":                  Tt_K,
        "Te_K":                  Te_K,
        "gamma_ch":              gamma_ch,
        "reactant_density_gcc":  reactant_density_gcc,
        "cea_reactant_density_gcc": cea_reactant_density_gcc,
        "blend_density_gcc":      blend_density_gcc,
        "density_estimated":      blend["estimated"],
        "density_missing":        blend["missing"],
        "reactant_density_source": reactant_density_source,
        "reactant_density_lbin3": reactant_density_lbin3,
        "mol_wt_exit":           mol_wt_exit,
        "Pe":                    Pe,
        "Pamb":                  Pamb,
        "Psep":                  0.4 * Pamb,
        "overexpanded":          (Pe < Pamb)       if Pe else False,
        "separating":            (Pe < 0.4 * Pamb) if Pe else False,
        "eps_range":             eps_range,
        "isp_vac_curve":         isp_vac_curve,
        "isp_amb_100pct_curve":  isp_amb_100pct_curve,
        "isp_amb_eff_curve":     isp_amb_eff_curve,
        "tc_curve_k":            tc_curve_k,
        "tt_curve_k":            tt_curve_k,
        "te_curve_k":            te_curve_k,
        "chart_warning":         chart_warning,
        "atoms":                 atoms,
        "ob":                    ob,
        "species_mw":            species_mw,
        "species_mole":          species_mole,
        "flame_analysis":        flame_analysis,
        "full_output":           full_out,
    }


class CeaWorker(QThread):
    """Runs ``run_cea`` in a background thread; emits finished(dict) or error(str)."""
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg

    def run(self):
        try:
            self.finished.emit(run_cea(self.cfg))
        except Exception as exc:
            self.error.emit(str(exc))
