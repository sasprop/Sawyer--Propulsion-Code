# =============================================================================
#  propellant_analysis.py
#  Standalone analysis functions:
#    - Loads atomic masses from atomic_masses.txt (no hardcoded values)
#    - Atmospheric pressure from altitude (ft) using ISA equation
#    - Optimal expansion ratio from Pamb and Pc
#    - Atom inventory per 100g of propellant
#    - Oxygen balance calculation (C->CO, Al->Al2O3)
#
#  To add a new element: edit atomic_masses.txt only. No Python changes needed.
# =============================================================================

import os
import re

import numpy as np

from propellant_analyzer import paths


# -----------------------------------------------------------------------------
# LOAD ATOMIC MASSES FROM TEXT FILE
# -----------------------------------------------------------------------------

def load_atomic_masses(filepath=None):
    """
    Loads atomic masses from atomic_masses.txt.
    Searches for the file in the same directory as this script if no path given.
    Returns a dict: { "SYMBOL": mass_float }
    """
    if filepath is None:
        filepath = str(paths.ATOMIC_MASSES)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(
            f"atomic_masses.txt not found at: {filepath}\n"
            f"The app's data folder is incomplete - reinstall or re-clone the app."
        )

    masses = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.split("#")[0].strip()
            if not line or "=" not in line:
                continue
            symbol, _, value = line.partition("=")
            symbol = symbol.strip().upper()
            try:
                masses[symbol] = float(value.strip())
            except ValueError:
                raise ValueError(
                    f"Bad entry in atomic_masses.txt: '{raw_line.strip()}'\n"
                    f"Expected format:  SYMBOL = mass"
                )

    if not masses:
        raise ValueError("atomic_masses.txt loaded but contained no valid entries.")

    return masses


# Load once at module import -- all functions below use this
ATOMIC_MASS = load_atomic_masses()


# -----------------------------------------------------------------------------
# ATMOSPHERE
# -----------------------------------------------------------------------------

def altitude_ft_to_m(alt_ft):
    """Convert feet to meters."""
    return alt_ft * 0.3048


def pressure_at_altitude_pa(alt_ft):
    """
    ISA pressure equation:  p = 101325 * (1 - 2.25577e-5 * h)^5.25588
    h in meters, returns pressure in Pa.
    Troposphere valid to ~36,089 ft (11,000 m).
    Stratosphere approximation used above that.
    """
    h = altitude_ft_to_m(alt_ft)
    if h <= 11000:
        p_pa = 101325.0 * (1.0 - 2.25577e-5 * h) ** 5.25588
    else:
        # Lower stratosphere (11,000 m - 20,000 m)
        p_pa = 22632.1 * np.exp(-1.7345e-4 * (h - 11000.0))
    return p_pa


def pa_to_psia(p_pa):
    """Convert Pa to psia."""
    return p_pa / 6894.757


def average_pressure_psia(alt_start_ft, alt_end_ft, n_steps=500):
    """
    Numerically integrates pressure over an altitude range and returns
    the average in psia.
    """
    altitudes = np.linspace(alt_start_ft, alt_end_ft, n_steps)
    pressures = np.array([pa_to_psia(pressure_at_altitude_pa(a)) for a in altitudes])
    return float(np.mean(pressures))


def single_altitude_psia(alt_ft):
    """Return pressure in psia at a single altitude in feet."""
    return pa_to_psia(pressure_at_altitude_pa(alt_ft))


# -----------------------------------------------------------------------------
# NOZZLE EXPANSION ANALYSIS
# -----------------------------------------------------------------------------

def optimal_expansion_ratio(Pc_psia, Pamb_psia, gamma=1.2):
    """
    Calculates the ideal (perfectly expanded) nozzle area ratio Ae/At.
    Uses isentropic flow relations to find the exit Mach number where Pe = Pamb.
    Returns (eps_ideal, Me_ideal) or None if calculation fails.
    """
    Pe_Pc = Pamb_psia / Pc_psia
    g     = gamma

    Me_sq = (2.0 / (g - 1.0)) * ((Pe_Pc ** (-(g - 1.0) / g)) - 1.0)
    if Me_sq <= 0:
        return None
    Me = np.sqrt(Me_sq)

    base     = (2.0 / (g + 1.0)) * (1.0 + (g - 1.0) / 2.0 * Me ** 2)
    exponent = (g + 1.0) / (2.0 * (g - 1.0))
    eps_ideal = (1.0 / Me) * (base ** exponent)

    return round(eps_ideal, 3), round(Me, 3)


# -----------------------------------------------------------------------------
# ATOM INVENTORY
# -----------------------------------------------------------------------------

def parse_formula_from_tag(tag):
    """
    Parses a RocketCEA card tag string and returns {element: count}.
    Handles tags like:
      'name HTPB C 7.337 H 10.982 O 0.058 wt%=100.0 h,cal=... rho,...'
    Stops at 'wt%'.
    """
    atoms = {}
    m = re.search(r"name\s+\S+\s+(.*?)\s+wt%", tag)
    if not m:
        return atoms
    formula_str = m.group(1)

    for match in re.finditer(r"([A-Z][A-Z]?)\s+([\d.]+)", formula_str):
        element = match.group(1).upper()
        count   = float(match.group(2))
        atoms[element] = atoms.get(element, 0.0) + count

    return atoms


def molecular_weight_from_atoms(atoms):
    """
    Calculate molecular weight from atom dict using ATOMIC_MASS table.
    Raises a clear error if an element is missing from atomic_masses.txt.
    """
    mw = 0.0
    for element, count in atoms.items():
        if element not in ATOMIC_MASS:
            raise ValueError(
                f"Element '{element}' not found in atomic_masses.txt.\n"
                f"Add it to atomic_masses.txt to continue."
            )
        mw += ATOMIC_MASS[element] * count
    return mw


def atom_inventory_per_100g(ingredient_keys, ingredient_amts, card_in_func):
    """
    Given the full ingredient list and weight fractions (wt%), calculates
    the total moles of each atom present per 100g of propellant.

    Returns a dict: {element: total_moles_per_100g}
    """
    total_atoms = {}

    for key, wt_pct in zip(ingredient_keys, ingredient_amts):
        tag   = card_in_func(key)[1]
        atoms = parse_formula_from_tag(tag)
        mw    = molecular_weight_from_atoms(atoms)

        if mw <= 0:
            continue

        # wt% == g of ingredient per 100g propellant
        mol_ingredient = wt_pct / mw

        for element, count in atoms.items():
            total_atoms[element] = total_atoms.get(element, 0.0) + mol_ingredient * count

    return total_atoms


# -----------------------------------------------------------------------------
# OXYGEN BALANCE
# -----------------------------------------------------------------------------

def oxygen_balance(atoms_per_100g):
    """
    Calculates oxygen balance based on priority reactions:
      1. All AL -> Al2O3:  requires 1.5 mol O per mol Al
      2. All C  -> CO:     requires 1.0 mol O per mol C

    All bookkeeping is in moles of O atoms (not O2 molecules).

    Returns dict with:
      o_available    : total O atoms available per 100g
      o_for_al2o3    : O atoms consumed by Al->Al2O3
      o_for_co       : O atoms consumed by C->CO
      o_remaining    : positive = excess, negative = deficit
      balance_status : "Oxygen Excess", "Oxygen Deficit", or "Stoichiometric"
    """
    o_avail  = atoms_per_100g.get("O",  0.0)
    c_moles  = atoms_per_100g.get("C",  0.0)
    al_moles = atoms_per_100g.get("AL", 0.0)

    o_for_al    = al_moles * 1.5   # Al2O3: 3 O per 2 Al
    o_for_c     = c_moles  * 1.0   # CO:    1 O per C
    o_remaining = o_avail - o_for_al - o_for_c

    if abs(o_remaining) < 1e-6:
        status = "Stoichiometric"
    elif o_remaining > 0:
        status = "Oxygen Excess"
    else:
        status = "Oxygen Deficit"

    return {
        "o_available":    round(o_avail,      6),
        "o_for_al2o3":    round(o_for_al,     6),
        "o_for_co":       round(o_for_c,      6),
        "o_remaining":    round(o_remaining,  6),
        "balance_status": status,
    }
