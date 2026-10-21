"""
Reading and writing ``.ceacfg`` / ``.propcfg`` files.

Configs saved by older builds also carried motor, grain, nozzle-hardware and
wired-endburner sections. Those features were removed, so ``migrate_config``
drops them. The one setting that changed results is kept: when the old nozzle
hardware was set to "Use exit diameter", the expansion ratio came from
(exit / throat)^2 instead of the eps box, so that value is copied into ``eps``.
"""

from __future__ import annotations

import json
from typing import Any

from propellant_analyzer import __version__

CONFIG_FORMAT = 2          # bump when the saved structure changes
EPS_MIN, EPS_MAX = 1.5, 60.0
_REMOVED_KEYS = ("motor_sim", "units")


def migrate_config(cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(cfg or {})
    hw = (cfg.get("motor_sim") or {}).get("hardware") or {}
    if hw.get("nozzle_mode") == "Use exit diameter":
        try:
            throat = float(hw.get("throat_dia_in", 0.0))
            exit_ = float(hw.get("exit_dia_in", 0.0))
            if throat > 0.0 and exit_ >= throat:
                cfg["eps"] = min(max((exit_ / throat) ** 2, EPS_MIN), EPS_MAX)
        except (TypeError, ValueError):
            pass
    for key in _REMOVED_KEYS:
        cfg.pop(key, None)
    return cfg


def read_config(path: str) -> dict[str, Any]:
    # utf-8-sig tolerates files edited in Notepad (BOM)
    with open(path, "r", encoding="utf-8-sig") as fh:
        return migrate_config(json.load(fh))


def write_config(path: str, cfg: dict[str, Any]) -> None:
    out = dict(cfg)
    out["app_version"] = __version__
    out["config_format"] = CONFIG_FORMAT
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
