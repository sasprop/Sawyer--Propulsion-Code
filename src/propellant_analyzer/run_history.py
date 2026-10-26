"""
Run history for chart overlays.

Every completed analysis is stored as a compact record (summary numbers plus
the expansion-ratio sweep curves) in ``<workspace>/run_history.json``, so past
runs can be overlaid on the ISP chart, including runs from earlier sessions.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Optional

from propellant_analyzer import paths

MAX_RUNS = 100
CURVE_KEYS = ("eps_range", "isp_vac_curve", "isp_amb_100pct_curve", "isp_amb_eff_curve",
              "tc_curve_k", "tt_curve_k", "te_curve_k")


def _clean(values) -> list:
    out = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = float("nan")
        out.append(None if not math.isfinite(f) else round(f, 6))
    return out


def _restore(values) -> list:
    return [float("nan") if v is None else float(v) for v in values]


def record_from_result(r: dict, source: str = "run", label: Optional[str] = None) -> dict:
    cfg = r.get("cfg", {})
    name = (cfg.get("formula_name") or "Run").strip()
    tag = (cfg.get("formula_tag") or "").strip()
    now = datetime.now()
    rec = {
        "label": label or (f"{name} [{tag}]" if tag else name) + now.strftime("  %m-%d %H:%M"),
        "created": now.isoformat(timespec="seconds"),
        "source": source,
        "pc_psia": float(cfg.get("pc_psia", 0.0)),
        "eps": float(r.get("eps_used", cfg.get("eps", 0.0))),
        "pamb": float(r.get("Pamb", cfg.get("pamb", 0.0))),
        "isp_eff": float(cfg.get("isp_eff", 1.0)),
        "cstar": float(r.get("cstar", 0.0)),
        "isp_vac": float(r.get("isp_vac", 0.0)),
        "isp_amb": float(r.get("isp_amb", 0.0)),
        "Tc_K": float(r.get("Tc_K", 0.0)),
        "ingredients": [(row.get("name"), float(row.get("wt_pct", 0.0))) for row in cfg.get("ingredients", [])],
    }
    for key in CURVE_KEYS:
        rec[key] = _clean(r.get(key, []))
    return rec


def curves(rec: dict) -> dict:
    """Curves of a record as float lists (NaN restored)."""
    return {key: _restore(rec.get(key, [])) for key in CURVE_KEYS}


def describe(rec: dict) -> str:
    when = rec.get("created", "").replace("T", " ")[:16]
    src = "  (from config)" if rec.get("source") == "config" else ""
    lines = [
        f"{rec.get('label', 'Run')}{src}",
        f"{when}",
        f"Pc {rec.get('pc_psia', 0):.0f} psia | eps {rec.get('eps', 0):.2f} | Pamb {rec.get('pamb', 0):.3f} psia",
        f"c* {rec.get('cstar', 0):.1f} ft/s | Isp vac {rec.get('isp_vac', 0):.2f} s | "
        f"Isp amb {rec.get('isp_amb', 0):.2f} s | Tc {rec.get('Tc_K', 0):.0f} K",
    ]
    ings = rec.get("ingredients") or []
    if ings:
        lines.append(", ".join(f"{n} {w:g}%" for n, w in ings))
    return "\n".join(lines)


class RunHistory:
    def __init__(self, path: Optional[str] = None):
        self.path = str(path or paths.RUN_HISTORY)
        self.runs: list[dict] = []
        self._next_seq = 0
        self.load()

    # -- persistence ---------------------------------------------------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.runs = list(data.get("runs", []))
            self._next_seq = int(data.get("next_seq", len(self.runs)))
        except (OSError, ValueError, TypeError):
            self.runs, self._next_seq = [], 0

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"next_seq": self._next_seq, "runs": self.runs}, fh)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # -- edits ---------------------------------------------------------------
    def add(self, rec: dict) -> dict:
        rec = dict(rec)
        rec["seq"] = self._next_seq          # stable identity -> stable colour
        self._next_seq += 1
        rec.setdefault("checked", False)
        self.runs.append(rec)
        if len(self.runs) > MAX_RUNS:
            self.runs = self.runs[-MAX_RUNS:]
        self.save()
        return rec

    def get(self, seq: int) -> Optional[dict]:
        return next((r for r in self.runs if r.get("seq") == seq), None)

    def update(self, seq: int, **fields):
        rec = self.get(seq)
        if rec is not None:
            rec.update(fields)
            self.save()

    def remove(self, seqs):
        seqs = set(seqs)
        self.runs = [r for r in self.runs if r.get("seq") not in seqs]
        self.save()

    def clear(self):
        self.runs = []
        self.save()
