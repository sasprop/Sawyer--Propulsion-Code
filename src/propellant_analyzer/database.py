# =============================================================================
#  database.py  --  Ingredient database backed by ingredients.json
#
#  WHY JSON INSTEAD OF A MATCH STATEMENT:
#    The old match-statement approach required editing Python code to add
#    ingredients. This module loads from ingredients.json (and optionally
#    user_ingredients.json), so any tool can write new ingredients without
#    touching Python source. The lookup API is backwards-compatible:
#      card_in(key) still returns (name, tag, Weq, particles, density)
#    where key can be:
#      - int  : ingredient's "id" field (e.g. 1 -> AL)
#              OR category code (e.g. 2000 -> first metal)
#      - str  : primary name or any alias (case-insensitive)
#
#  CATEGORY CODES (stored in each ingredient's "category" field):
#    1000  Oxidizers
#    2000  Metals / Metal fuels
#    3000  Binders
#    4000  Curatives / Isocyanates
#    5000  Burn Rate Catalysts
#    6000  Burn Rate Suppressants
#    7000  Plasticizers
#    8000  Unknown / Misc
#    9000  Energetic Additives
#
#  INGREDIENT RECORD FIELDS:
#    id              int   : unique integer ID
#    name            str   : primary CEA card name (caps, no spaces)
#    aliases         list  : alternate string keys accepted by card_in()
#    category        int   : category code
#    cea_formula     str   : element-count pairs e.g. "C 7.337 H 10.982 O 0.058"
#                            Empty string -> no CEA thermochemical data
#    h_cal           float : heat of formation in calories (NOT kcal)
#    t_k             float : temperature at which Hf was measured (K)
#    density         float : g/cc
#    Weq             float : equivalent weight g/mol of reactive group; 0 = N/A
#    particles       list  : particle sizes in microns; [0] = homogeneous
#    functional_group str  : "OH", "NCO", "EPOXIDE", etc. for cure calculator
#    phase           str   : "S"=solid, "L"=liquid, ""=unknown
#    notes           str   : free-text notes
# =============================================================================

import copy
import json
import os

from propellant_analyzer import paths

# ---------------------------------------------------------------------------
# File paths (resolved in paths.py so the frozen .exe and source runs agree)
# ---------------------------------------------------------------------------
_DB_PATH      = str(paths.INGREDIENTS_DB)
_USER_DB_PATH = str(paths.USER_DB)


# ---------------------------------------------------------------------------
# Load & merge databases
# ---------------------------------------------------------------------------

def _load_db() -> list:
    """
    Load bundled ingredients.json and merge with user_ingredients.json.
    User entries with duplicate IDs override bundled entries.
    Returns a flat list of ingredient dicts sorted by id.
    """
    if not os.path.isfile(_DB_PATH):
        raise FileNotFoundError(
            f"ingredients.json not found at: {_DB_PATH}\n"
            f"The app's data folder is incomplete - reinstall or re-clone the app."
        )

    with open(_DB_PATH, "r", encoding="utf-8") as fh:
        bundled = json.load(fh)

    user_entries = []
    if os.path.isfile(_USER_DB_PATH):
        with open(_USER_DB_PATH, "r", encoding="utf-8") as fh:
            user_entries = json.load(fh)

    # Merge: user entries overwrite bundled entries with the same id
    by_id = {ing["id"]: ing for ing in bundled}
    for u in user_entries:
        by_id[u["id"]] = u

    return sorted(by_id.values(), key=lambda x: x.get("id", 99999))


# Module-level cache
_DB = []

def reload_db():
    """Force a full reload of the ingredient database from disk."""
    global _DB
    _DB = _load_db()

reload_db()   # Load at import time


def get_all_ingredients() -> list:
    """Return a shallow copy of the full ingredient list."""
    return copy.copy(_DB)


# ---------------------------------------------------------------------------
# card_in() – backwards-compatible public lookup
# ---------------------------------------------------------------------------

def _find_ingredient(key) -> dict:
    """
    Internal lookup. Accepts int (id or category code) or str (name/alias).
    Returns the ingredient dict, or None if not found.
    """
    if isinstance(key, int):
        # Exact ID match first
        for ing in _DB:
            if ing.get("id") == key:
                return ing
        # Category match: return the first ingredient in that category
        for ing in _DB:
            if ing.get("category") == key:
                return ing
        return None

    if isinstance(key, str):
        upper = key.upper()
        for ing in _DB:
            if ing.get("name", "").upper() == upper:
                return ing
            if any(a.upper() == upper for a in ing.get("aliases", [])):
                return ing
        return None

    return None


def card_in(key) -> tuple:
    """
    Public lookup API – backwards-compatible with old match-statement version.

    Parameters
    ----------
    key : int or str
        Any valid lookup key (ID, category, name, or alias).

    Returns
    -------
    (name, cea_tag, Weq, particles, density)
        name      str   CEA card name
        cea_tag   str   Full RocketCEA card string; empty string if no CEA data
        Weq       float Equivalent weight (0.0 if not applicable)
        particles list  Particle size list in microns ([0] for homogeneous)
        density   float g/cc
    """
    ing = _find_ingredient(key)

    if ing is None:
        # Sentinel entry: unrealistically high Hf flags errors in CEA output
        return (
            "NA",
            "name NA  H 2.0 wt%=100.0 h,cal=10000000.0 t(k)=298.15 rho,g/cc=1.00",
            0.0,
            [0],
            1.0,
        )

    name      = ing.get("name", "NA")
    formula   = ing.get("cea_formula", "").strip()
    h_cal     = float(ing.get("h_cal", 0.0))
    t_k       = float(ing.get("t_k", 298.15))
    density   = float(ing.get("density", 1.0))
    Weq       = float(ing.get("Weq", 0.0))
    particles = list(ing.get("particles", [0]))

    if formula:
        cea_tag = (
            f"name {name}  {formula} "
            f"wt%=100.0 h,cal={h_cal:.1f} t(k)={t_k:.2f} "
            f"rho,g/cc={density:.3f}"
        )
    else:
        cea_tag = ""   # Signal: no thermochemical data available

    return (name, cea_tag, Weq, particles, density)


# ---------------------------------------------------------------------------
# User ingredient persistence
# ---------------------------------------------------------------------------

def save_user_ingredient(ingredient: dict):
    """
    Save a user-defined ingredient to user_ingredients.json.
    If an entry with the same id already exists, it is overwritten.
    Refreshes the in-memory database after saving.
    """
    existing = []
    if os.path.isfile(_USER_DB_PATH):
        with open(_USER_DB_PATH, "r", encoding="utf-8") as fh:
            existing = json.load(fh)

    ids = [e["id"] for e in existing]
    if ingredient["id"] in ids:
        existing = [ingredient if e["id"] == ingredient["id"] else e
                    for e in existing]
    else:
        existing.append(ingredient)

    os.makedirs(os.path.dirname(_USER_DB_PATH), exist_ok=True)
    with open(_USER_DB_PATH, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2, ensure_ascii=False)

    reload_db()


def next_user_id() -> int:
    """
    Return the next available integer ID for a new user ingredient.
    User IDs begin at 10001 to avoid collisions with bundled IDs (1–9999).
    """
    user_ids = [i["id"] for i in _DB if i.get("id", 0) >= 10001]
    return max(user_ids, default=10000) + 1


# ---------------------------------------------------------------------------
# Equivalent weight helper functions
# ---------------------------------------------------------------------------

def weq_from_percent_nco(percent_nco: float) -> float:
    """
    Equivalent weight from %NCO content.
    Weq = (MW_NCO / %NCO) * 100  where MW_NCO = 42.018 g/mol.
    """
    if percent_nco <= 0:
        raise ValueError("%NCO must be greater than zero.")
    return (42.018 / percent_nco) * 100.0


def weq_from_hydroxyl_number(hydroxyl_number: float) -> float:
    """
    Equivalent weight from Hydroxyl Number (mg KOH per gram sample).
    Weq = 56100 / Hydroxyl_Number   (MW_KOH = 56.1 g/mol).
    """
    if hydroxyl_number <= 0:
        raise ValueError("Hydroxyl number must be greater than zero.")
    return 56100.0 / hydroxyl_number


def weq_from_hydroxyl_value(hydroxyl_value: float) -> float:
    """
    Equivalent weight from Hydroxyl Value (mmol OH per gram sample).
    Weq = 1000 / Hydroxyl_Value.
    """
    if hydroxyl_value <= 0:
        raise ValueError("Hydroxyl value must be greater than zero.")
    return 1000.0 / hydroxyl_value
