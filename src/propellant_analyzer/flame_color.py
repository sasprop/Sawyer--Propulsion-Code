"""
Flame-colour screening.

Maps RocketCEA product species (injector / chamber / throat / exit mole
fractions) onto known visible emitters, then penalises colour visibility when
the exit mix carries a lot of alumina smoke.  Pure functions - no Qt.
"""

import math

from propellant_analyzer.theme import C

FLAME_COLOR_RULES = [
    {
        "family": "Yellow",
        "hex": "#f2d35b",
        "label": "Sodium emitters",
        "prefixes": ["NA"],
        "wavelength": "Na D lines, 589.0 / 589.6 nm",
        "note": "Sodium is an intensely bright yellow emitter and can visually dominate even when present only in trace amounts.",
        "weight": 14.0,
    },
    {
        "family": "Violet",
        "hex": "#b391ff",
        "label": "Potassium emitters",
        "prefixes": ["K"],
        "wavelength": "K lines, 404.4 / 766.5 / 769.9 nm",
        "note": "Potassium typically pushes the flame toward lilac or violet.",
        "weight": 7.0,
    },
    {
        "family": "Red",
        "hex": "#ff6b6b",
        "label": "Lithium emitters",
        "prefixes": ["LI"],
        "wavelength": "Li line, 670.8 nm",
        "note": "Lithium is a classic crimson-red flame emitter.",
        "weight": 9.0,
    },
    {
        "family": "Red",
        "hex": "#ff6b6b",
        "label": "Strontium emitters",
        "prefixes": ["SR"],
        "wavelength": "Sr lines near 640.8 / 650.4 / 661.7 / 687.8 nm; SrCl and SrOH strengthen red pyrotechnic emission",
        "note": "Strontium species are the standard route to red flames; chlorine-bearing systems often improve red color purity by promoting SrCl.",
        "weight": 11.0,
    },
    {
        "family": "Orange",
        "hex": "#ff9b54",
        "label": "Calcium emitters",
        "prefixes": ["CA"],
        "wavelength": "Ca lines near 643.9 / 646.3 / 649.4 nm",
        "note": "Calcium species usually appear orange to orange-red.",
        "weight": 8.0,
    },
    {
        "family": "Green",
        "hex": "#6fe68f",
        "label": "Barium emitters",
        "prefixes": ["BA"],
        "wavelength": "Ba+ lines near 455.4 / 493.4 nm; BaCl bands are important green emitters",
        "note": "Barium systems are the classic green color route, especially when chlorine helps form emitting barium halides.",
        "weight": 10.0,
    },
    {
        "family": "Blue-Green",
        "hex": "#58c4dd",
        "label": "Copper emitters",
        "prefixes": ["CU"],
        "wavelength": "Cu lines near 510.6 / 515.3 / 521.8 / 522.0 nm; CuCl / CuBr / CuI can improve blue flame quality",
        "note": "Copper is the main route to blue or blue-green flames, with copper halides generally giving the cleanest color.",
        "weight": 12.0,
    },
    {
        "family": "Blue",
        "hex": "#6fb6ff",
        "label": "CH radical",
        "exact": ["CH"],
        "wavelength": "CH* chemiluminescence near 431 nm",
        "note": "CH radicals are a major contributor to the blue reaction-zone glow in hydrocarbon flames.",
        "weight": 5.0,
    },
    {
        "family": "Cyan-Green",
        "hex": "#6fe6d3",
        "label": "C2 radical",
        "exact": ["C2"],
        "wavelength": "C2 Swan bands, especially near 516.5 nm",
        "note": "C2 radicals often produce the green or cyan component of fuel-rich hydrocarbon flames.",
        "weight": 6.0,
    },
    {
        "family": "Violet",
        "hex": "#b391ff",
        "label": "CN radical",
        "exact": ["CN"],
        "wavelength": "CN violet system near 388 nm",
        "note": "CN can contribute a violet edge when both carbon- and nitrogen-bearing reaction products are present.",
        "weight": 4.5,
    },
    {
        "family": "Near-UV / Blue Edge",
        "hex": "#9bbcff",
        "label": "OH radical",
        "exact": ["OH"],
        "wavelength": "OH* chemiluminescence near 308 nm",
        "note": "OH is mostly near-UV, but it often tracks the hottest reaction zone and can give a faint blue-violet edge.",
        "weight": 1.5,
    },
]

FLAME_FAMILY_ORDER = [
    "Red",
    "Orange",
    "Yellow",
    "Green",
    "Cyan-Green",
    "Blue",
    "Blue-Green",
    "Violet",
    "Near-UV / Blue Edge",
]


def _normalize_species_name(name: str) -> str:
    return name.lstrip("*").strip().upper()


def _flame_rule_matches(rule: dict, species_name: str) -> bool:
    norm = _normalize_species_name(species_name)
    for exact in rule.get("exact", []):
        if norm == exact:
            return True
    for prefix in rule.get("prefixes", []):
        if norm.startswith(prefix):
            return True
    return False


def _flame_strength_band(exit_pct: float) -> str:
    if exit_pct >= 1.0:
        return "High"
    if exit_pct >= 0.1:
        return "Moderate"
    if exit_pct >= 0.01:
        return "Low"
    if exit_pct >= 0.001:
        return "Trace"
    return "Very trace"


def _smoke_obscuration_band(exit_pct: float) -> str:
    if exit_pct >= 5.0:
        return "High"
    if exit_pct >= 1.0:
        return "Moderate"
    if exit_pct >= 0.1:
        return "Low"
    return "Minimal"


def analyze_flame_color_species(mole_frac_d: dict) -> dict:
    contributors = []
    family_totals = {}
    family_scores_raw = {}
    smoke_contributors = []

    for raw_name, values in mole_frac_d.items():
        inj, chm, tht, exit_ = [float(v) for v in values]
        if exit_ <= 0.0:
            continue
        species_display = _normalize_species_name(raw_name)
        if species_display.startswith("AL2O3"):
            smoke_contributors.append(
                {
                    "species": raw_name,
                    "species_display": species_display,
                    "inj_pct": inj * 100.0,
                    "chm_pct": chm * 100.0,
                    "tht_pct": tht * 100.0,
                    "exit_pct": exit_ * 100.0,
                    "strength": _smoke_obscuration_band(exit_ * 100.0),
                    "note": "Condensed or condensed-phase alumina is a strong plume obscurer and tends to wash out color purity.",
                }
            )
        match = None
        for rule in FLAME_COLOR_RULES:
            if _flame_rule_matches(rule, raw_name):
                match = rule
                break
        if not match:
            continue

        exit_pct = exit_ * 100.0
        score = exit_pct * float(match["weight"])
        contributor = {
            "species": raw_name,
            "species_display": species_display,
            "family": match["family"],
            "family_hex": match["hex"],
            "label": match["label"],
            "inj_pct": inj * 100.0,
            "chm_pct": chm * 100.0,
            "tht_pct": tht * 100.0,
            "exit_pct": exit_pct,
            "wavelength": match["wavelength"],
            "note": match["note"],
            "strength": _flame_strength_band(exit_pct),
            "score": score,
        }
        contributors.append(contributor)
        family_totals[match["family"]] = family_totals.get(match["family"], 0.0) + exit_pct
        family_scores_raw[match["family"]] = family_scores_raw.get(match["family"], 0.0) + score

    contributors.sort(key=lambda item: (item["score"], item["exit_pct"]), reverse=True)
    smoke_contributors.sort(key=lambda item: item["exit_pct"], reverse=True)

    alumina_smoke_exit_pct = sum(item["exit_pct"] for item in smoke_contributors)
    alumina_smoke_frac = alumina_smoke_exit_pct / 100.0
    plume_clarity = max(0.15, math.exp(-4.0 * alumina_smoke_frac))
    plume_obscuration = _smoke_obscuration_band(alumina_smoke_exit_pct)

    family_rows = []
    for family in FLAME_FAMILY_ORDER:
        total = family_totals.get(family, 0.0)
        raw_score = family_scores_raw.get(family, 0.0)
        score = raw_score * plume_clarity
        if total <= 0.0 and score <= 0.0:
            continue
        family_hex = next(
            (rule["hex"] for rule in FLAME_COLOR_RULES if rule["family"] == family),
            C["text2"],
        )
        family_rows.append(
            {
                "family": family,
                "exit_pct": total,
                "score": score,
                "raw_score": raw_score,
                "hex": family_hex,
            }
        )

    if family_rows:
        dominant = max(family_rows, key=lambda item: item["score"])
        strongest = contributors[0]
        summary = (
            f"Likely visible hue trend: {dominant['family']}. "
            f"Top mapped emitter: {strongest['species_display']} at {strongest['exit_pct']:.4f} mol% exit."
        )
        if alumina_smoke_exit_pct > 0.0:
            summary += (
                f" Alumina smoke screen: {alumina_smoke_exit_pct:.4f} mol% exit "
                f"({plume_obscuration.lower()} obscuration, clarity factor {plume_clarity:.3f})."
            )
    else:
        dominant = None
        strongest = None
        summary = (
            "No mapped color emitters were found above the screening threshold. "
            "Observed flame may still be shaped by hot particles, soot, or broadband thermal emission."
        )
        if alumina_smoke_exit_pct > 0.0:
            summary += (
                f" Exit alumina products total {alumina_smoke_exit_pct:.4f} mol%, "
                f"which suggests a bright white or smoky plume may still dominate visibility."
            )

    notes = [
        "This screen is heuristic. Visible flame color is not set by concentration alone; pressure, temperature, afterburning, soot, aluminum oxide particles, and optical path can dominate what the eye sees.",
        "The concentration bands in this tab are screening bands for RocketCEA exit composition, not guaranteed color thresholds.",
    ]
    if alumina_smoke_exit_pct > 0.0:
        notes.append(
            f"Alumina smoke penalty applied: exit alumina products = {alumina_smoke_exit_pct:.4f} mol%, reducing color-family visibility scores by the plume clarity factor."
        )
    if any(item["family"] == "Yellow" for item in family_rows):
        notes.append("Sodium is especially likely to overpower other colors visually, even when its predicted mole fraction is much lower than other emitters.")
    if any(item["family"] in {"Blue-Green", "Green", "Red"} and "CL" in item["species_display"] for item in contributors):
        notes.append("Halide-containing emitters are present in the predicted products, which often helps color purity for copper, barium, and strontium systems.")

    return {
        "contributors": contributors,
        "family_rows": family_rows,
        "dominant_family": dominant["family"] if dominant else None,
        "dominant_score": dominant["score"] if dominant else 0.0,
        "dominant_exit_pct": dominant["exit_pct"] if dominant else 0.0,
        "strongest_species": strongest["species_display"] if strongest else None,
        "strongest_exit_pct": strongest["exit_pct"] if strongest else 0.0,
        "visible_exit_total_pct": sum(item["exit_pct"] for item in contributors),
        "plume_clarity": plume_clarity,
        "plume_obscuration": plume_obscuration,
        "alumina_smoke_exit_pct": alumina_smoke_exit_pct,
        "smoke_contributors": smoke_contributors,
        "summary": summary,
        "notes": notes,
    }
