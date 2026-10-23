"""ISP CHART tab: Isp or temperature versus expansion ratio."""

from typing import Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from propellant_analyzer.theme import C
from propellant_analyzer.widgets import _dspin, mono_label


class ChartsTab(QWidget):
    """
    Expansion-ratio chart that can show:
      1. Specific impulse curves
      2. Chamber / throat / exit temperature curves
    """
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
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
        ctrl.addSpacing(10)
        self.lbl_chart_view = mono_label("Chart:")
        self.cmb_chart_view = QComboBox()
        self.cmb_chart_view.addItems(["Specific Impulse", "Temperature"])
        self.cmb_chart_view.setFixedWidth(170)
        self.lbl_temp_units = mono_label("Temp units:")
        self.cmb_temp_units = QComboBox()
        self.cmb_temp_units.addItems(["Kelvin", "deg C", "deg F"])
        self.cmb_temp_units.setFixedWidth(110)
        ctrl.addWidget(self.lbl_chart_view)
        ctrl.addWidget(self.cmb_chart_view)
        ctrl.addWidget(self.lbl_temp_units)
        ctrl.addWidget(self.cmb_temp_units)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.fig    = Figure(figsize=(10, 5.5), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background:{C['bg1']};")
        lay.addWidget(self.canvas)

        self.ph = QLabel("Run analysis to generate expansion-ratio charts")
        self.ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ph.setStyleSheet(
            f"color:{C['text3']}; font-family:Consolas,monospace; font-size:13px;"
        )
        lay.addWidget(self.ph)

        self._result: Optional[dict] = None
        self._full_eps_range = (0.0, 100.0)
        self._set_range_controls_enabled(False)
        self.spn_xmin.valueChanged.connect(self._on_x_range_changed)
        self.spn_xmax.valueChanged.connect(self._on_x_range_changed)
        self.btn_xreset.clicked.connect(self._reset_x_range)
        self.cmb_chart_view.currentTextChanged.connect(self._on_chart_mode_changed)
        self.cmb_temp_units.currentTextChanged.connect(self._render_current)
        self._update_chart_mode_controls()

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
        if self._result is not None:
            self._render_current()

    def _on_x_range_changed(self, *_args):
        if self._result is None:
            return
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
        if self._result is not None:
            self._render_current()

    def _update_chart_mode_controls(self):
        is_temp = self.cmb_chart_view.currentText() == "Temperature"
        self.lbl_temp_units.setVisible(is_temp)
        self.cmb_temp_units.setVisible(is_temp)

    @staticmethod
    def _convert_temperature_curve(values_k, unit_label: str) -> np.ndarray:
        values = np.asarray(values_k, dtype=float)
        if unit_label == "deg C":
            return values - 273.15
        if unit_label == "deg F":
            return (values - 273.15) * 9.0 / 5.0 + 32.0
        return values

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

    def populate(self, r: dict):
        self._result = r
        self._configure_x_range_controls(r["eps_range"])
        self._render_current()

    def _render_current(self):
        r = self._result
        if r is None:
            return
        self.ph.hide()
        self.fig.clear()
        ax  = self.fig.add_subplot(111)
        er  = r["eps_range"]
        eff = r["cfg"]["isp_eff"]
        if len(er) < 2:
            self._set_range_controls_enabled(False)
            ax.set_axis_off()
            msg = r.get("chart_warning") or (
                "Expansion-ratio chart unavailable for this run.\n"
                "The base CEA solution did not support a valid eps sweep."
            )
            ax.text(
                0.5, 0.5, msg,
                ha="center", va="center",
                color=C["text2"], fontsize=11, family="monospace",
                transform=ax.transAxes,
            )
            self.canvas.draw_idle()
            return

        display_x_min = self.spn_xmin.value()
        x_min = max(float(er[0]), display_x_min)
        x_max = min(float(er[-1]), self.spn_xmax.value())
        visible_mask = (er >= x_min) & (er <= x_max)
        if np.count_nonzero(visible_mask) < 2:
            visible_mask = np.ones_like(er, dtype=bool)
            display_x_min = 0.0
            x_min = float(er[0])
            x_max = float(er[-1])
            self._set_x_controls(display_x_min, x_max)
        chart_mode = self.cmb_chart_view.currentText()
        cfg_eps = r.get("eps_used", r["cfg"]["eps"])
        eps_span = er[-1] - er[0]

        if chart_mode == "Temperature":
            temp_unit = self.cmb_temp_units.currentText()
            temp_unit_display = {
                "Kelvin": "K",
                "deg C": "degC",
                "deg F": "degF",
            }.get(temp_unit, temp_unit)
            tc_curve = self._convert_temperature_curve(r.get("tc_curve_k", []), temp_unit)
            tt_curve = self._convert_temperature_curve(r.get("tt_curve_k", []), temp_unit)
            te_curve = self._convert_temperature_curve(r.get("te_curve_k", []), temp_unit)
            if len(tc_curve) != len(er) or len(tt_curve) != len(er) or len(te_curve) != len(er):
                ax.set_axis_off()
                ax.text(
                    0.5, 0.5,
                    "Temperature sweep data is unavailable for this run.",
                    ha="center", va="center",
                    color=C["text2"], fontsize=11, family="monospace",
                    transform=ax.transAxes,
                )
                self.canvas.draw_idle()
                return

            self._mark_exit_plateau(ax, er, r.get("te_curve_k", []), te_curve, temp_unit_display, x_min, x_max)
            ax.plot(er, tc_curve, color=C["amber"], lw=2.2, label="Chamber temperature", zorder=3)
            ax.plot(er, tt_curve, color=C["blue"], lw=2.0, ls="--", label="Throat temperature", zorder=3)
            ax.plot(er, te_curve, color=C["green"], lw=2.0, ls="-.", label="Exit temperature", zorder=3)
            if x_min <= cfg_eps <= x_max:
                ax.axvline(x=cfg_eps, color=C["text3"], lw=1, ls="--", zorder=2, alpha=0.6)
                cfg_tc = float(np.interp(cfg_eps, er, tc_curve))
                ax.scatter([cfg_eps], [cfg_tc], color=C["amber"], s=55, zorder=6)
                ax.annotate(
                    f"eps = {cfg_eps:.1f}\nTc {cfg_tc:.1f} {temp_unit_display}",
                    xy=(cfg_eps, cfg_tc),
                    xytext=(cfg_eps + eps_span * 0.04, cfg_tc),
                    color=C["amber"],
                    fontsize=8.5,
                    fontfamily="monospace",
                    bbox=dict(
                        boxstyle="round,pad=0.35",
                        facecolor=C["bg0"],
                        edgecolor=C["border2"],
                        alpha=0.92,
                    ),
                    arrowprops=dict(
                        arrowstyle="-|>",
                        connectionstyle="arc3,rad=0.12",
                        color=C["amber"],
                        lw=0.8,
                    ),
                    zorder=7,
                )
            ax.set_xlabel("Expansion Ratio", labelpad=8, fontsize=10, color=C["text1"])
            ax.set_ylabel(f"Temperature  ({temp_unit_display})", labelpad=8, fontsize=10, color=C["text1"])
            ax.set_title(
                f"Temperature vs Expansion Ratio  -  Pc = {r['cfg']['pc_psia']:.0f} psia"
                f"  |  Pamb = {r['Pamb']:.3f} psia",
                fontsize=10, pad=10, color=C["text1"],
            )
        else:
            # -- Three Isp curves --------------------------------------------
            ax.plot(er, r["isp_vac_curve"],
                    color=C["blue"],  lw=2, ls="-",  label="Isp vacuum (theoretical)",  zorder=3)
            ax.plot(er, r["isp_amb_100pct_curve"],
                    color=C["amber"], lw=2, ls="--", label="Isp ambient - 100% efficient", zorder=3)
            if eff < 1.0:
                ax.plot(er, r["isp_amb_eff_curve"],
                        color=C["green"], lw=2, ls="-",
                        label=f"Isp ambient - eta={eff:.3f} (expected)", zorder=3)

            _ann_box = dict(
                boxstyle="round,pad=0.35",
                facecolor=C["bg0"],
                edgecolor=C["border2"],
                alpha=0.92,
            )
            _arr = dict(
                arrowstyle="-|>",
                connectionstyle="arc3,rad=0.15",
                color=C["text3"],
                lw=0.8,
            )

            y_100 = float(np.interp(cfg_eps, er, r["isp_amb_100pct_curve"]))
            y_eff = float(np.interp(cfg_eps, er, r["isp_amb_eff_curve"]))
            visible_isp = np.asarray(r["isp_amb_100pct_curve"], dtype=float)[visible_mask]
            visible_isp = visible_isp[np.isfinite(visible_isp)]
            if visible_isp.size < 2:
                visible_isp = np.asarray(r["isp_amb_100pct_curve"], dtype=float)
                visible_isp = visible_isp[np.isfinite(visible_isp)]
            isp_span = float(max(visible_isp) - min(visible_isp)) if visible_isp.size >= 2 else 1.0
            cfg_label = (
                f"eps = {cfg_eps:.1f}\n"
                f"{y_100:.1f} s  (100% eff)\n"
                f"{y_eff:.1f} s  (eta={eff:.3f})"
            ) if eff < 1.0 else (
                f"eps = {cfg_eps:.1f}\n"
                f"{y_100:.1f} s"
            )
            if x_min <= cfg_eps <= x_max:
                ax.axvline(x=cfg_eps, color=C["text3"], lw=1, ls="--", zorder=2, alpha=0.6)
                ax.scatter([cfg_eps], [y_100], color=C["amber"], s=60, zorder=6)
                ax.annotate(
                    cfg_label,
                    xy=(cfg_eps, y_100),
                    xytext=(cfg_eps - eps_span * 0.18, y_100 - isp_span * 0.28),
                    color=C["amber"],
                    fontsize=8.5,
                    fontfamily="monospace",
                    bbox=_ann_box,
                    arrowprops={**_arr, "color": C["amber"]},
                    zorder=7,
                )

            if r["eps_ideal_val"] and r["isp_ideal"]:
                ei = r["eps_ideal_val"]
                y_id = float(np.interp(ei, er, r["isp_amb_100pct_curve"]))
                if x_min <= ei <= x_max:
                    ax.axvline(x=ei, color=C["green"], lw=1, ls=":", zorder=2, alpha=0.7)
                    ax.scatter([ei], [y_id], color=C["green"], s=60, zorder=6, marker="D")
                    ax.annotate(
                        f"eps_ideal = {ei:.2f}\n{y_id:.1f} s",
                        xy=(ei, y_id),
                        xytext=(ei + eps_span * 0.08, y_id + isp_span * 0.12),
                        color=C["green"],
                        fontsize=8.5,
                        fontfamily="monospace",
                        bbox=_ann_box,
                        arrowprops={**_arr, "color": C["green"]},
                        zorder=7,
                    )

            ax.set_xlabel("Expansion Ratio", labelpad=8, fontsize=10, color=C["text1"])
            ax.set_ylabel("Specific Impulse  (s)", labelpad=8, fontsize=10, color=C["text1"])
            ax.set_title(
                f"Isp vs Expansion Ratio  -  Pc = {r['cfg']['pc_psia']:.0f} psia"
                f"  |  Pamb = {r['Pamb']:.3f} psia"
                f"  |  eta_isp = {eff:.4f}",
                fontsize=10, pad=10, color=C["text1"],
            )
            y_lo, y_hi = ax.get_ylim()
            ax.set_ylim(y_lo, y_hi + isp_span * 0.08)

        ax.tick_params(colors=C["text2"], labelsize=9)
        ax.legend(loc="upper left", framealpha=0.25, edgecolor=C["border2"])
        ax.set_xlim(display_x_min, x_max)
        self.canvas.draw()
