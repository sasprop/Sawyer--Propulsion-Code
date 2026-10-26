"""
ISP CHART tab: Isp or temperature versus expansion ratio.

* Hover anywhere on the plot for a crosshair readout of every curve at that eps.
* The RUN HISTORY panel lists past runs (kept across sessions). Tick runs to
  overlay one chosen curve from each on top of the current run.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from propellant_analyzer import run_history as RH
from propellant_analyzer.theme import C
from propellant_analyzer.widgets import SectionCard, _dspin, mono_label

# Categorical run colours, fixed order, validated (lightness, chroma, CVD and
# contrast) against the dark chart surface. A run keeps its colour for life:
# colour = slot[run.seq % 8], never its position in the current selection.
RUN_COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
MAX_OVERLAYS = 7  # current run + 7 = the 8 validated colours

COMPARE_CURVES = {
    "Specific Impulse": [
        ("Isp ambient (100% eff.)", "isp_amb_100pct_curve"),
        ("Isp ambient (with eta)", "isp_amb_eff_curve"),
        ("Isp vacuum", "isp_vac_curve"),
    ],
    "Temperature": [
        ("Exit temperature", "te_curve_k"),
        ("Throat temperature", "tt_curve_k"),
        ("Chamber temperature", "tc_curve_k"),
    ],
}


def run_color(seq: int) -> str:
    return RUN_COLORS[int(seq) % len(RUN_COLORS)]


class ChartsTab(QWidget):
    add_config_requested = pyqtSignal()

    def __init__(self, history: Optional[RH.RunHistory] = None):
        super().__init__()
        self.history = history or RH.RunHistory()
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter)

        # ---- left: controls + plot -----------------------------------------
        left = QWidget()
        lay = QVBoxLayout(left)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        ctrl.addWidget(mono_label("Shown eps range:"))
        self.spn_xmin = _dspin(0.0, 100.0, 0.0, 2, 0.5, "")
        self.spn_xmax = _dspin(1.0, 100.0, 100.0, 2, 0.5, "")
        self.btn_xreset = QPushButton("Reset")
        self.btn_xreset.setObjectName("small_btn")
        self.spn_xmin.setFixedWidth(92)
        self.spn_xmax.setFixedWidth(92)
        ctrl.addWidget(self.spn_xmin)
        ctrl.addWidget(mono_label("to"))
        ctrl.addWidget(self.spn_xmax)
        ctrl.addWidget(self.btn_xreset)
        ctrl.addStretch()
        lay.addLayout(ctrl)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        ctrl.addWidget(mono_label("Chart:"))
        self.cmb_chart_view = QComboBox()
        self.cmb_chart_view.addItems(list(COMPARE_CURVES))
        self.cmb_chart_view.setFixedWidth(160)
        ctrl.addWidget(self.cmb_chart_view)
        self.lbl_temp_units = mono_label("Temp units:")
        self.cmb_temp_units = QComboBox()
        self.cmb_temp_units.addItems(["Kelvin", "deg C", "deg F"])
        self.cmb_temp_units.setFixedWidth(100)
        ctrl.addWidget(self.lbl_temp_units)
        ctrl.addWidget(self.cmb_temp_units)
        self.lbl_compare = mono_label("Compare:")
        self.cmb_compare = QComboBox()
        self.cmb_compare.setFixedWidth(190)
        ctrl.addWidget(self.lbl_compare)
        ctrl.addWidget(self.cmb_compare)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.fig = Figure(figsize=(10, 5.5), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background:{C['bg1']};")
        self.canvas.setMouseTracking(True)
        lay.addWidget(self.canvas, 1)

        self.ph = QLabel("Run analysis to generate expansion-ratio charts")
        self.ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ph.setStyleSheet(f"color:{C['text3']}; font-family:Consolas,monospace; font-size:13px;")
        lay.addWidget(self.ph)
        splitter.addWidget(left)

        # ---- right: run history -----------------------------------------------
        card = SectionCard("RUN HISTORY")
        hint = mono_label(
            "Tick runs to overlay them. The current run (bold) is always drawn. "
            "Double-click a name to rename it; hover it for details.", C["text3"], 10)
        hint.setWordWrap(True)
        card.add(hint)
        self.lst_runs = QListWidget()
        self.lst_runs.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lst_runs.setStyleSheet(
            f"QListWidget {{ background:{C['bg0']}; border:1px solid {C['border']}; "
            f"font-family:Consolas,monospace; font-size:11px; }}"
            f"QListWidget::item {{ padding:3px 2px; }}"
            f"QListWidget::item:selected {{ background:{C['amber_bg']}; color:{C['amber']}; }}"
        )
        card.add(self.lst_runs)
        self.btn_add_cfg = QPushButton("Add config...")
        self.btn_add_cfg.setToolTip("Run one or more saved .ceacfg files and overlay them")
        self.btn_uncheck = QPushButton("Untick all")
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setToolTip("Delete the selected runs from the history")
        self.btn_clear = QPushButton("Clear history")
        for pair in ((self.btn_add_cfg, self.btn_uncheck), (self.btn_remove, self.btn_clear)):
            row = QHBoxLayout()
            for b in pair:
                b.setObjectName("small_btn")
                row.addWidget(b)
            card.add_layout(row)
        self.lbl_overlay_note = mono_label("", C["amber"], 10)
        self.lbl_overlay_note.setWordWrap(True)
        card.add(self.lbl_overlay_note)
        card.setMinimumWidth(290)
        splitter.addWidget(card)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([900, 300])

        # ---- state + signals ----------------------------------------------------
        self._result: Optional[dict] = None
        self._current_seq: Optional[int] = None
        self._full_eps_range = (0.0, 100.0)
        self._hover_lines: list = []
        self._hover_ax = None
        self._filling_list = False
        self._set_range_controls_enabled(False)
        self.spn_xmin.valueChanged.connect(self._on_x_range_changed)
        self.spn_xmax.valueChanged.connect(self._on_x_range_changed)
        self.btn_xreset.clicked.connect(self._reset_x_range)
        self.cmb_chart_view.currentTextChanged.connect(self._on_chart_mode_changed)
        self.cmb_temp_units.currentTextChanged.connect(self._render_current)
        self.cmb_compare.currentIndexChanged.connect(self._render_current)
        self.lst_runs.itemChanged.connect(self._on_item_changed)
        self.btn_add_cfg.clicked.connect(self.add_config_requested.emit)
        self.btn_uncheck.clicked.connect(self._uncheck_all)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_history)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)
        self.canvas.mpl_connect("axes_leave_event", self._hide_hover)
        self.canvas.mpl_connect("figure_leave_event", self._hide_hover)
        self._update_chart_mode_controls()
        self.refresh_history()

    # ======================================================================
    #  Run history list
    # ======================================================================
    def refresh_history(self):
        self._filling_list = True
        self.lst_runs.clear()
        for rec in reversed(self.history.runs):            # newest first
            seq = rec["seq"]
            is_current = seq == self._current_seq
            item = QListWidgetItem(rec.get("label", "Run"))
            item.setData(Qt.ItemDataRole.UserRole, seq)
            pix = QPixmap(12, 12)
            pix.fill(QColor(run_color(seq)))
            item.setIcon(QIcon(pix))
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            if not is_current:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
            item.setFlags(flags)
            if not is_current:
                item.setCheckState(Qt.CheckState.Checked if rec.get("checked") else Qt.CheckState.Unchecked)
            item.setToolTip(RH.describe(rec) + ("\n\nThis is the current run (always shown)." if is_current else ""))
            if is_current:
                item.setForeground(QColor(C["text0"]))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.lst_runs.addItem(item)
        self._filling_list = False
        self._update_overlay_note()

    def _on_item_changed(self, item: QListWidgetItem):
        if self._filling_list:
            return
        seq = item.data(Qt.ItemDataRole.UserRole)
        rec = self.history.get(seq)
        if rec is None:
            return
        fields = {}
        if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
            checked = item.checkState() == Qt.CheckState.Checked
            if checked and not rec.get("checked") and len(self._overlay_records()) >= MAX_OVERLAYS:
                self._filling_list = True
                item.setCheckState(Qt.CheckState.Unchecked)
                self._filling_list = False
                QMessageBox.information(self, "Overlay limit",
                                        f"Up to {MAX_OVERLAYS} runs can be overlaid at once so each keeps a distinct colour.")
                return
            fields["checked"] = checked
        new_label = item.text().strip()
        if new_label and new_label != rec.get("label"):
            fields["label"] = new_label
        if fields:
            self.history.update(seq, **fields)
            if "label" in fields:
                self.refresh_history()
            self._update_overlay_note()
            self._render_current()

    def _overlay_records(self) -> list[dict]:
        return [r for r in self.history.runs if r.get("checked") and r.get("seq") != self._current_seq]

    def _update_overlay_note(self):
        n = len(self._overlay_records())
        self.lbl_overlay_note.setText(f"{n} run{'s' if n != 1 else ''} overlaid." if n else "")
        self._update_chart_mode_controls()

    def _uncheck_all(self):
        for r in self.history.runs:
            r["checked"] = False
        self.history.save()
        self.refresh_history()
        self._render_current()

    def _remove_selected(self):
        seqs = [it.data(Qt.ItemDataRole.UserRole) for it in self.lst_runs.selectedItems()]
        seqs = [s for s in seqs if s != self._current_seq]
        if not seqs:
            return
        self.history.remove(seqs)
        self.refresh_history()
        self._render_current()

    def _clear_history(self):
        if not self.history.runs:
            return
        ret = QMessageBox.question(self, "Clear run history",
                                   "Delete every saved run from the history (the current run stays on screen)?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        keep = self.history.get(self._current_seq) if self._current_seq is not None else None
        self.history.clear()
        if keep is not None:
            self.history.runs.append(keep)
            self.history.save()
        self.refresh_history()
        self._render_current()

    def add_overlay_record(self, rec: dict):
        """A run added from a config file: tick it so it shows straight away."""
        if len(self._overlay_records()) < MAX_OVERLAYS:
            self.history.update(rec["seq"], checked=True)
        self.refresh_history()
        self._render_current()

    # ======================================================================
    #  Controls
    # ======================================================================
    def _set_range_controls_enabled(self, enabled: bool):
        self.spn_xmin.setEnabled(enabled)
        self.spn_xmax.setEnabled(enabled)
        self.btn_xreset.setEnabled(enabled)

    def _set_x_controls(self, x_min: float, x_max: float):
        self.spn_xmin.blockSignals(True)
        self.spn_xmax.blockSignals(True)
        self.spn_xmin.setValue(x_min)
        self.spn_xmax.setValue(x_max)
        self.spn_xmin.blockSignals(False)
        self.spn_xmax.blockSignals(False)

    def _configure_x_range_controls(self, er):
        if len(er) < 2:
            self._full_eps_range = (0.0, 100.0)
            self._set_range_controls_enabled(False)
            self.spn_xmin.setRange(0.0, 100.0)
            self.spn_xmax.setRange(1.0, 100.0)
            self._set_x_controls(0.0, 100.0)
            return
        full_min = 0.0
        full_max = max(100.0, float(er[-1]))
        self._full_eps_range = (full_min, full_max)
        self._set_range_controls_enabled(True)
        self.spn_xmin.setRange(full_min, full_max)
        self.spn_xmax.setRange(max(1.0, full_min), full_max)
        self._set_x_controls(full_min, full_max)

    def _reset_x_range(self):
        full_min, full_max = self._full_eps_range
        self._set_x_controls(full_min, full_max)
        self._render_current()

    def _on_x_range_changed(self, *_args):
        x_min = self.spn_xmin.value()
        x_max = self.spn_xmax.value()
        if x_min >= x_max:
            sender = self.sender()
            step = max(self.spn_xmin.singleStep(), 0.1)
            full_min, full_max = self._full_eps_range
            if sender is self.spn_xmin:
                x_max = min(full_max, x_min + step)
            else:
                x_min = max(full_min, x_max - step)
            self._set_x_controls(x_min, x_max)
        self._render_current()

    def _on_chart_mode_changed(self, *_args):
        self._update_chart_mode_controls()
        self._render_current()

    def _update_chart_mode_controls(self):
        mode = self.cmb_chart_view.currentText()
        is_temp = mode == "Temperature"
        self.lbl_temp_units.setVisible(is_temp)
        self.cmb_temp_units.setVisible(is_temp)
        wanted = [label for label, _ in COMPARE_CURVES[mode]]
        if [self.cmb_compare.itemText(i) for i in range(self.cmb_compare.count())] != wanted:
            self.cmb_compare.blockSignals(True)
            self.cmb_compare.clear()
            self.cmb_compare.addItems(wanted)
            self.cmb_compare.blockSignals(False)
        comparing = bool(self._overlay_records()) if hasattr(self, "_current_seq") else False
        self.lbl_compare.setVisible(comparing)
        self.cmb_compare.setVisible(comparing)

    @staticmethod
    def _convert_temperature_curve(values_k, unit_label: str) -> np.ndarray:
        values = np.asarray(values_k, dtype=float)
        if unit_label == "deg C":
            return values - 273.15
        if unit_label == "deg F":
            return (values - 273.15) * 9.0 / 5.0 + 32.0
        return values

    def _temp_unit_display(self) -> str:
        return {"Kelvin": "K", "deg C": "degC", "deg F": "degF"}.get(self.cmb_temp_units.currentText(), "K")

    # ======================================================================
    #  Exit-temperature plateau
    # ======================================================================
    @staticmethod
    def find_exit_plateau(er, te_k, tol_k: float = 0.05):
        """
        Return (eps_start, eps_end, Te_K) for the widest stretch where the exit
        temperature stays constant, or None.

        In shifting-equilibrium CEA runs this happens when a condensed product
        freezes inside the nozzle: the latent heat holds the gas at that
        product's melting point until it has all solidified. For aluminized
        propellants it is Al2O3 at 2327 K.
        """
        te = np.asarray(te_k, dtype=float)
        er = np.asarray(er, dtype=float)
        if te.size < 3 or te.size != er.size:
            return None
        flat = np.abs(np.diff(te)) < tol_k
        best, start = None, None
        for i, f in enumerate(np.append(flat, False)):
            if f and start is None:
                start = i
            elif not f and start is not None:
                if best is None or (i - start) > (best[1] - best[0]):
                    best = (start, i)
                start = None
        if best is None or not np.isfinite(te[best[0]]):
            return None
        return float(er[best[0]]), float(er[best[1]]), float(te[best[0]])

    def _mark_exit_plateau(self, ax, er, te_k, te_display, unit_label, x_min, x_max):
        found = self.find_exit_plateau(er, te_k)
        if not found:
            return
        e0, e1, t_k = found
        if e1 < x_min or e0 > x_max:
            return
        what = "Al2O3 freezing" if abs(t_k - 2327.0) < 1.0 else "condensed product freezing"
        ax.axvspan(e0, e1, color=C["border2"], alpha=0.35, lw=0, zorder=1)
        t_disp = float(np.interp(e0, er, te_display))
        ax.annotate(
            f"Te held at {t_disp:.0f} {unit_label}\n({what})",
            xy=((e0 + e1) / 2.0, t_disp),
            xytext=(12, 18), textcoords="offset points",
            color=C["text1"], fontsize=8.5, fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.35", facecolor=C["bg0"], edgecolor=C["border2"], alpha=0.92),
            zorder=7,
        )

    # ======================================================================
    #  Rendering
    # ======================================================================
    def populate(self, r: dict, record: Optional[dict] = None):
        self._result = r
        self._current_seq = record["seq"] if record else None
        self._configure_x_range_controls(r["eps_range"])
        self.refresh_history()
        self._render_current()

    def _visible_window(self, er):
        display_x_min = self.spn_xmin.value()
        x_min = max(float(er[0]), display_x_min)
        x_max = min(float(er[-1]), self.spn_xmax.value())
        if np.count_nonzero((er >= x_min) & (er <= x_max)) < 2:
            display_x_min, x_min, x_max = 0.0, float(er[0]), float(er[-1])
            self._set_x_controls(display_x_min, x_max)
        return display_x_min, x_min, x_max

    def _render_current(self, *_args):
        overlays = self._overlay_records()
        if self._result is None and not overlays:
            return
        self.ph.hide()
        self.fig.clear()
        self._hover_lines = []
        ax = self.fig.add_subplot(111)
        if overlays:
            self._render_compare(ax, overlays)
        else:
            self._render_single(ax)

    def _style_axes(self, ax, display_x_min, x_max):
        ax.tick_params(colors=C["text2"], labelsize=9)
        ax.set_xlim(display_x_min, x_max)
        self._setup_hover(ax)
        self.canvas.draw()

    def _message(self, ax, msg: str):
        ax.set_axis_off()
        ax.text(0.5, 0.5, msg, ha="center", va="center", color=C["text2"], fontsize=11,
                family="monospace", transform=ax.transAxes)
        self.canvas.draw_idle()

    # ---- one run, full detail ----------------------------------------------------
    def _render_single(self, ax):
        r = self._result
        er = np.asarray(r["eps_range"], dtype=float)
        eff = r["cfg"]["isp_eff"]
        if len(er) < 2:
            self._set_range_controls_enabled(False)
            self._message(ax, r.get("chart_warning") or (
                "Expansion-ratio chart unavailable for this run.\n"
                "The base CEA solution did not support a valid eps sweep."))
            return
        display_x_min, x_min, x_max = self._visible_window(er)
        visible_mask = (er >= x_min) & (er <= x_max)
        cfg_eps = r.get("eps_used", r["cfg"]["eps"])
        eps_span = er[-1] - er[0]
        box = dict(boxstyle="round,pad=0.35", facecolor=C["bg0"], edgecolor=C["border2"], alpha=0.92)

        if self.cmb_chart_view.currentText() == "Temperature":
            temp_unit = self.cmb_temp_units.currentText()
            unit = self._temp_unit_display()
            tc = self._convert_temperature_curve(r.get("tc_curve_k", []), temp_unit)
            tt = self._convert_temperature_curve(r.get("tt_curve_k", []), temp_unit)
            te = self._convert_temperature_curve(r.get("te_curve_k", []), temp_unit)
            if not (len(tc) == len(tt) == len(te) == len(er)):
                self._message(ax, "Temperature sweep data is unavailable for this run.")
                return
            self._mark_exit_plateau(ax, er, r.get("te_curve_k", []), te, unit, x_min, x_max)
            for y, color, ls, lw, label in [
                (tc, C["amber"], "-", 2.2, "Chamber temperature"),
                (tt, C["blue"], "--", 2.0, "Throat temperature"),
                (te, C["green"], "-.", 2.0, "Exit temperature"),
            ]:
                ax.plot(er, y, color=color, lw=lw, ls=ls, label=label, zorder=3)
                self._hover_lines.append((label, er, y, color, f"{{:.1f}} {unit}"))
            if x_min <= cfg_eps <= x_max:
                ax.axvline(x=cfg_eps, color=C["text3"], lw=1, ls="--", zorder=2, alpha=0.6)
                cfg_tc = float(np.interp(cfg_eps, er, tc))
                ax.scatter([cfg_eps], [cfg_tc], color=C["amber"], s=55, zorder=6)
                ax.annotate(f"eps = {cfg_eps:.1f}\nTc {cfg_tc:.1f} {unit}", xy=(cfg_eps, cfg_tc),
                            xytext=(cfg_eps + eps_span * 0.04, cfg_tc), color=C["amber"], fontsize=8.5,
                            fontfamily="monospace", bbox=box,
                            arrowprops=dict(arrowstyle="-|>", connectionstyle="arc3,rad=0.12", color=C["amber"], lw=0.8),
                            zorder=7)
            ax.set_xlabel("Expansion Ratio", labelpad=8, fontsize=10, color=C["text1"])
            ax.set_ylabel(f"Temperature  ({unit})", labelpad=8, fontsize=10, color=C["text1"])
            ax.set_title(f"Temperature vs Expansion Ratio  -  Pc = {r['cfg']['pc_psia']:.0f} psia"
                         f"  |  Pamb = {r['Pamb']:.3f} psia", fontsize=10, pad=10, color=C["text1"])
        else:
            series = [(r["isp_vac_curve"], C["blue"], "-", "Isp vacuum (theoretical)"),
                      (r["isp_amb_100pct_curve"], C["amber"], "--", "Isp ambient - 100% efficient")]
            if eff < 1.0:
                series.append((r["isp_amb_eff_curve"], C["green"], "-", f"Isp ambient - eta={eff:.3f} (expected)"))
            for y, color, ls, label in series:
                y = np.asarray(y, dtype=float)
                ax.plot(er, y, color=color, lw=2, ls=ls, label=label, zorder=3)
                self._hover_lines.append((label, er, y, color, "{:.2f} s"))

            arr = dict(arrowstyle="-|>", connectionstyle="arc3,rad=0.15", lw=0.8)
            amb = np.asarray(r["isp_amb_100pct_curve"], dtype=float)
            y_100 = float(np.interp(cfg_eps, er, amb))
            y_eff = float(np.interp(cfg_eps, er, np.asarray(r["isp_amb_eff_curve"], dtype=float)))
            visible = amb[visible_mask]
            visible = visible[np.isfinite(visible)]
            if visible.size < 2:
                visible = amb[np.isfinite(amb)]
            isp_span = float(visible.max() - visible.min()) if visible.size >= 2 else 1.0
            label = (f"eps = {cfg_eps:.1f}\n{y_100:.1f} s  (100% eff)\n{y_eff:.1f} s  (eta={eff:.3f})"
                     if eff < 1.0 else f"eps = {cfg_eps:.1f}\n{y_100:.1f} s")
            if x_min <= cfg_eps <= x_max:
                ax.axvline(x=cfg_eps, color=C["text3"], lw=1, ls="--", zorder=2, alpha=0.6)
                ax.scatter([cfg_eps], [y_100], color=C["amber"], s=60, zorder=6)
                ax.annotate(label, xy=(cfg_eps, y_100),
                            xytext=(cfg_eps - eps_span * 0.18, y_100 - isp_span * 0.28),
                            color=C["amber"], fontsize=8.5, fontfamily="monospace", bbox=box,
                            arrowprops={**arr, "color": C["amber"]}, zorder=7)
            if r["eps_ideal_val"] and r["isp_ideal"]:
                ei = r["eps_ideal_val"]
                y_id = float(np.interp(ei, er, amb))
                if x_min <= ei <= x_max:
                    ax.axvline(x=ei, color=C["green"], lw=1, ls=":", zorder=2, alpha=0.7)
                    ax.scatter([ei], [y_id], color=C["green"], s=60, zorder=6, marker="D")
                    ax.annotate(f"eps_ideal = {ei:.2f}\n{y_id:.1f} s", xy=(ei, y_id),
                                xytext=(ei + eps_span * 0.08, y_id + isp_span * 0.12),
                                color=C["green"], fontsize=8.5, fontfamily="monospace", bbox=box,
                                arrowprops={**arr, "color": C["green"]}, zorder=7)
            ax.set_xlabel("Expansion Ratio", labelpad=8, fontsize=10, color=C["text1"])
            ax.set_ylabel("Specific Impulse  (s)", labelpad=8, fontsize=10, color=C["text1"])
            ax.set_title(f"Isp vs Expansion Ratio  -  Pc = {r['cfg']['pc_psia']:.0f} psia"
                         f"  |  Pamb = {r['Pamb']:.3f} psia  |  eta_isp = {eff:.4f}",
                         fontsize=10, pad=10, color=C["text1"])
            y_lo, y_hi = ax.get_ylim()
            ax.set_ylim(y_lo, y_hi + isp_span * 0.08)

        ax.legend(loc="upper left", framealpha=0.25, edgecolor=C["border2"])
        self._style_axes(ax, display_x_min, x_max)

    # ---- several runs, one curve each --------------------------------------------
    def _render_compare(self, ax, overlays: list[dict]):
        mode = self.cmb_chart_view.currentText()
        options = COMPARE_CURVES[mode]
        idx = max(0, min(self.cmb_compare.currentIndex(), len(options) - 1))
        curve_label, key = options[idx]
        is_temp = mode == "Temperature"
        unit = self._temp_unit_display() if is_temp else "s"
        fmt = f"{{:.1f}} {unit}" if is_temp else "{:.2f} s"

        entries = []   # (label, er, y, color, lw, design eps, is_current)
        if self._result is not None and len(self._result.get("eps_range", [])) >= 2:
            cur = self.history.get(self._current_seq) if self._current_seq is not None else None
            label = (cur or {}).get("label") or (self._result["cfg"].get("formula_name") or "Current run")
            color = run_color(self._current_seq) if self._current_seq is not None else C["amber"]
            entries.append((f"{label} (current)", np.asarray(self._result["eps_range"], dtype=float),
                            np.asarray(self._result.get(key, []), dtype=float), color, 2.6,
                            float(self._result.get("eps_used", self._result["cfg"]["eps"])), True))
        for rec in overlays:
            cv = RH.curves(rec)
            entries.append((rec.get("label", "Run"), np.asarray(cv["eps_range"], dtype=float),
                            np.asarray(cv.get(key, []), dtype=float), run_color(rec["seq"]), 1.8,
                            float(rec.get("eps", 0.0)), False))

        entries = [e for e in entries if len(e[1]) >= 2 and len(e[1]) == len(e[2])]
        if not entries:
            self._message(ax, "The selected runs have no sweep data to compare.")
            return
        if is_temp:
            entries = [(lb, er, self._convert_temperature_curve(y, self.cmb_temp_units.currentText()), c, lw, de, cur)
                       for lb, er, y, c, lw, de, cur in entries]

        all_er = np.concatenate([e[1] for e in entries])
        full_max = max(100.0, float(np.nanmax(all_er)))
        if self._full_eps_range[1] < full_max:
            self._full_eps_range = (0.0, full_max)
            self.spn_xmax.setRange(1.0, full_max)
        self._set_range_controls_enabled(True)
        display_x_min = self.spn_xmin.value()
        x_max = self.spn_xmax.value()

        for label, er, y, color, lw, design_eps, is_current in entries:
            ax.plot(er, y, color=color, lw=lw, label=label, zorder=4 if is_current else 3)
            self._hover_lines.append((label, er, y, color, fmt))
            if er[0] <= design_eps <= er[-1] and display_x_min <= design_eps <= x_max:
                yd = float(np.interp(design_eps, er, y))
                if np.isfinite(yd):
                    ax.scatter([design_eps], [yd], color=color, s=34, zorder=6,
                               edgecolors=C["bg0"], linewidths=1.5)

        ax.set_xlabel("Expansion Ratio", labelpad=8, fontsize=10, color=C["text1"])
        ax.set_ylabel(f"{curve_label}  ({unit})", labelpad=8, fontsize=10, color=C["text1"])
        ax.set_title(f"Run comparison  -  {curve_label}  (dots mark each run's design eps)",
                     fontsize=10, pad=10, color=C["text1"])
        ax.legend(loc="best", framealpha=0.25, edgecolor=C["border2"], fontsize=8.5)
        self._style_axes(ax, display_x_min, x_max)

    # ======================================================================
    #  Hover readout
    # ======================================================================
    def _setup_hover(self, ax):
        self._hover_ax = ax
        self._hover_vline = ax.axvline(0.0, color=C["text2"], lw=0.8, ls=":", zorder=9, visible=False)
        self._hover_dots = ax.scatter([], [], s=42, zorder=10, edgecolors=C["bg0"], linewidths=1.5)
        self._hover_text = ax.annotate(
            "", xy=(0, 0), xytext=(14, 14), textcoords="offset points",
            color=C["text0"], fontsize=8.5, fontfamily="monospace", zorder=11, visible=False,
            annotation_clip=False,
            bbox=dict(boxstyle="round,pad=0.45", facecolor=C["bg2"], edgecolor=C["border2"], alpha=0.95),
        )

    def hover_values(self, x: float) -> list[tuple[str, float, str]]:
        """(label, y, colour) of every curve at eps = x (curves that cover x)."""
        out = []
        for label, xs, ys, color, _fmt in self._hover_lines:
            if len(xs) < 2 or x < xs[0] or x > xs[-1]:
                continue
            y = float(np.interp(x, xs, ys))
            if np.isfinite(y):
                out.append((label, y, color))
        return out

    def _on_hover(self, event):
        if self._hover_ax is None or event.inaxes is not self._hover_ax or event.xdata is None:
            self._hide_hover()
            return
        x = float(event.xdata)
        vals = self.hover_values(x)
        if not vals:
            self._hide_hover()
            return
        fmts = {label: fmt for label, _xs, _ys, _c, fmt in self._hover_lines}
        width = min(max(len(label) for label, _, _ in vals), 44)
        lines = [f"eps = {x:.2f}"] + [f"{label[:44]:<{width}}  {fmts[label].format(y)}" for label, y, _ in vals]
        y_anchor = vals[0][1]
        self._hover_vline.set_xdata([x, x])
        self._hover_vline.set_visible(True)
        self._hover_dots.set_offsets(np.array([[x, y] for _, y, _ in vals]))
        self._hover_dots.set_facecolors([c for _, _, c in vals])
        self._hover_text.xy = (x, y_anchor)
        x0, x1 = self._hover_ax.get_xlim()
        right_side = x > x0 + 0.6 * (x1 - x0)
        self._hover_text.set_position((-14, 14) if right_side else (14, 14))
        self._hover_text.set_horizontalalignment("right" if right_side else "left")
        self._hover_text.set_text("\n".join(lines))
        self._hover_text.set_visible(True)
        self.canvas.draw_idle()

    def _hide_hover(self, *_args):
        if self._hover_ax is None or not getattr(self, "_hover_text", None):
            return
        if self._hover_text.get_visible():
            self._hover_text.set_visible(False)
            self._hover_vline.set_visible(False)
            self._hover_dots.set_offsets(np.empty((0, 2)))
            self.canvas.draw_idle()
