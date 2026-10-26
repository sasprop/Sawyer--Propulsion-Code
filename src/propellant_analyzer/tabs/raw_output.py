"""RAW CEA OUTPUT tab: full NASA CEA text plus the save-to-Formula-Outputs button."""

import os
import re
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from propellant_analyzer import __version__
from propellant_analyzer.paths import resolve_output_dir


def slugify_filename(text: str, fallback: str = "run") -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", (text or "").strip())
    text = text.strip("_")
    return text or fallback


class CeaOutputTab(QWidget):
    """Raw NASA CEA text output with save functionality."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlaceholderText(
            "Full NASA CEA output will appear here after running an analysis."
        )
        lay.addWidget(self.text)

        btn_save = QPushButton("Save Full Output File")
        btn_save.clicked.connect(self._save)
        lay.addWidget(btn_save)

        self._r: Optional[dict] = None

    def populate(self, r: dict):
        self._r = r
        self.text.setPlainText(r["full_output"])

    def _save(self):
        if not self._r:
            return
        r   = self._r
        out = resolve_output_dir(r["cfg"].get("output_dir"))
        os.makedirs(out, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        formula_name = r["cfg"].get("formula_name") or "run"
        path = os.path.join(out, f"{slugify_filename(formula_name)}_{ts}.txt")

        excluded_lines = []
        for e in r.get("excluded_summary", []):
            excluded_lines.append(
                f"    {e['name']:20s}  {e['wt_pct']:6.3f} wt%  [{e['reason']}]"
            )
        exc_block = ("\n  CEA-EXCLUDED INGREDIENTS:\n" + "\n".join(excluded_lines)
                     if excluded_lines else "")

        lines = [
            "=" * 80,
            f"  PROPELLANT ANALYZER v{__version__}  |  Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 80,
            f"  Formula        : {formula_name}",
            f"  Blend          : {r['combo']}",
            f"  Total wt%      : {r['total_all_wt']:.4f}%  "
            f"(CEA: {r['total_cea_wt']:.4f}%)",
            exc_block,
            "",
            f"  C*     (ft/s)  : {r['cstar']:.2f}  "
            f"(th: {r['cstar_th']:.2f}  eff: {r['cfg']['cstar_eff']:.4f})",
            f"  Isp vac   (s)  : {r['isp_vac']:.2f}  (th: {r['isp_vac_th']:.2f})",
            f"  Isp amb   (s)  : {r['isp_amb']:.2f}  [{r['mode']}]",
            (f"  Isp ideal (s)  : {r['isp_ideal']:.2f}  "
             f"(at eps = {r['eps_ideal_val']:.3f})"
             if r["isp_ideal"] else "  Isp ideal     : N/A"),
            f"  Tc              : {r['Tc_K']:.2f} K  ({r['Tc_K']-273.15:.2f} degC)",
            f"  gamma           : {r['gamma_ch']:.4f}",
            (f"  rho*Isp (s*g/cc): vac {r['rho_isp_vac']:.1f}  amb {r['rho_isp_amb']:.1f}"
             + (f"  ideal {r['rho_isp_ideal']:.1f}" if r.get("rho_isp_ideal") else "")
             if r.get("rho_isp_vac") is not None else "  rho*Isp         : N/A (no reactant density)"),
            (f"  Exit Mach (CEA) : {r['mach_exit']:.4f}" if r.get("mach_exit") else "  Exit Mach (CEA) : N/A"),
            (f"  Density         : {r['reactant_density_gcc']:.4f} g/cc  "
             f"({r['reactant_density_lbin3']:.5f} lb/in^3)  "
             f"[{r.get('reactant_density_source', 'Unknown source')}]"
             if r["reactant_density_gcc"] else "  Density         : N/A"),
            f"  Oxygen balance  : {r['ob']['o_remaining']:+.6f}  "
            f"[{r['ob']['balance_status']}]",
            "",
            "=" * 80,
            "  FULL NASA CEA OUTPUT",
            "=" * 80,
            r["full_output"],
        ]

        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        QMessageBox.information(
            self, "Saved", f"Output file saved to:\n{path}"
        )
