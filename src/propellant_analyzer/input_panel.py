"""Left sidebar: formulation (solids + binder/cure system) and run conditions."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QScrollArea, QSpinBox,
    QTextEdit, QVBoxLayout, QWidget,
)

from propellant_analyzer import database as DB
from propellant_analyzer.ingredients_ui import IngredientTable
from propellant_analyzer.paths import DEFAULT_OUTPUT_DIR, resolve_output_dir
from propellant_analyzer.propellant_analysis import average_pressure_psia, single_altitude_psia
from propellant_analyzer.theme import C
from propellant_analyzer.widgets import SectionCard, _dspin, mono_label, sep_line


class InputPanel(QScrollArea):
    """
    Left sidebar containing all user-configurable inputs.
    Uses InputPanel.get_config() to extract a plain dict for the worker thread.

    LAYOUT NOTES
    -------------
    The IngredientTable is placed directly in the scroll-area content widget
    (not inside a QGroupBox) so that setFixedHeight() is respected by the layout
    engine.  A QGroupBox clamps child sizes to its own sizeHint, preventing the
    table from growing dynamically.

    The binder/cure section is split into two clearly labelled radio modes:
      - Cure Calculator  - enter binder ingredients with no manual wt% for
                           curative; the calc computes curative mass live.
      - Manual Entry     - type binder and curative wt% directly.
    """
    preview_changed = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumWidth(560)
        self.setMaximumWidth(1100)

        w = QWidget()
        self.setWidget(w)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        # -- App header -----------------------------------------------------
        title = QLabel("PROPELLANT ANALYZER")
        title.setStyleSheet(
            f"color:{C['amber']}; font-size:16px; font-weight:800; "
            f"letter-spacing:3px; font-family:Consolas,monospace;"
        )
        sub = QLabel("// NASA CEA  |  Solid Propellant Design Tool")
        sub.setStyleSheet(
            f"color:{C['text3']}; font-size:10px; "
            f"font-family:Consolas,monospace; letter-spacing:1px;"
        )
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addWidget(sep_line())

        # ----------------------------------------------------------------------
        # PROPELLANT INGREDIENTS  (oxidizers, metals, additives - entered first)
        # ----------------------------------------------------------------------
        ing_hdr = QLabel("FORMULA / PROPELLANT INPUTS")
        ing_hdr.setStyleSheet(
            f"color:{C['amber']}; font-size:10px; font-weight:700; "
            f"letter-spacing:2px; font-family:Consolas,monospace; padding:2px 0;"
        )
        lay.addWidget(ing_hdr)

        # Table lives directly in scroll content - not a QGroupBox - so
        # setFixedHeight() propagates through the layout correctly.
        meta = SectionCard("FORMULA IDENTITY")
        meta_form = QFormLayout()
        meta_form.setSpacing(5)
        meta_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.txt_formula_name = QLineEdit("HTPB-AP BASELINE")
        self.txt_formula_name.setPlaceholderText("Named propellant formula")
        self.txt_formula_tag = QLineEdit("DEV")
        self.txt_formula_tag.setPlaceholderText("Program / tag")
        meta_form.addRow(mono_label("Formula name:"), self.txt_formula_name)
        meta_form.addRow(mono_label("Formula tag:"), self.txt_formula_tag)
        meta.add_layout(meta_form)
        self.txt_formula_notes = QTextEdit()
        self.txt_formula_notes.setFixedHeight(66)
        self.txt_formula_notes.setPlaceholderText(
            "Optional notes for this formulation, cure schedule, processing window, or test campaign."
        )
        meta.add(self.txt_formula_notes)
        lay.addWidget(meta)
        lay.addWidget(sep_line())

        self.ing_table = IngredientTable(show_func_col=False, show_weq_col=False)
        self.ing_table.add_ingredient("AP_CUSTOM", 70.0, True)
        self.ing_table.add_ingredient("AL",        18.0, True)
        lay.addWidget(self.ing_table)
        self.ing_table.changed.connect(self._on_solids_changed)

        lay.addWidget(sep_line())

        # ----------------------------------------------------------------------
        # BINDER SYSTEM  (below solids, as requested)
        # ----------------------------------------------------------------------
        binder_hdr_lbl = QLabel("BINDER SYSTEM")
        binder_hdr_lbl.setStyleSheet(
            f"color:{C['amber']}; font-size:10px; font-weight:700; "
            f"letter-spacing:2px; font-family:Consolas,monospace; padding:2px 0;"
        )
        lay.addWidget(binder_hdr_lbl)

        # Mode toggle
        mode_row = QHBoxLayout()
        self.rb_cure_calc   = QRadioButton("Cure Calculator")
        self.rb_cure_manual = QRadioButton("Manual Entry")
        self.rb_cure_calc.setChecked(True)
        bg_cure = QButtonGroup(self)
        bg_cure.addButton(self.rb_cure_calc)
        bg_cure.addButton(self.rb_cure_manual)
        for rb in [self.rb_cure_calc, self.rb_cure_manual]:
            rb.setStyleSheet(f"color:{C['text1']}; font-size:12px; font-weight:600;")
            mode_row.addWidget(rb)
        mode_row.addStretch()
        lay.addLayout(mode_row)
        lay.addWidget(sep_line())

        # -- CURE CALC MODE -------------------------------------------------
        # Logic:
        #   curative wt% = 100 - sum(solid rows) - sum(binder rows)
        # The user never types a curative wt% - it fills the gap automatically.
        self.cure_calc_box = QWidget()
        cc_lay = QVBoxLayout(self.cure_calc_box)
        cc_lay.setContentsMargins(0, 0, 0, 0)
        cc_lay.setSpacing(6)

        cc_desc = mono_label(
            "Auto mode shows binder-system wt% values without direct numeric entry.\n"
            "The curative wt% is computed as:  100 - solids - binder total.",
            C["text3"]
        )
        cc_desc.setText(
            "Auto mode computes the primary binder/curative pair from the target NCO/OH ratio.\n"
            "Extra liquid rows stay editable and subtract from the remaining liquid mass."
        )
        cc_desc.setWordWrap(True)
        cc_lay.addWidget(cc_desc)

        self.binder_table = IngredientTable(
            show_func_col=True, show_weq_col=True, show_include_col=False
        )
        self.binder_table.add_ingredient("HTPB", 9.94, True)
        self.binder_table.add_ingredient("IDP",  1.24, True)
        self.binder_table.set_pct_inputs_enabled(True)
        cc_lay.addWidget(self.binder_table)

        cc_form = QFormLayout()
        cc_form.setSpacing(5)
        cc_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.spn_nco_oh = _dspin(0.5, 2.0, 0.89, 3, 0.01)
        self.spn_nco_oh.setToolTip(
            "NCO:OH ratio. < 1.0 = softer/flexible  > 1.0 = harder/crosslinked\n"
            "Used to check the computed curative mass against your target.\n"
            "Typical: 0.85a0.95"
        )
        cc_form.addRow(mono_label("NCO/OH ratio:"), self.spn_nco_oh)
        cc_lay.addLayout(cc_form)

        cc_lay.addWidget(sep_line())
        self.lbl_cc_curative = mono_label("Curative:         -",       C["text1"])
        self.lbl_cc_binder   = mono_label("Binder subtotal:  - wt%",  C["text1"])
        self.lbl_cc_cure     = mono_label("Curative (auto):  - wt%",  C["amber"])
        self.lbl_cc_oh       = mono_label("NCO/OH check:     -",       C["text2"])
        self.lbl_cc_note     = mono_label("",                           C["text3"])
        self.lbl_cc_note.setWordWrap(True)
        for lbl_w in [self.lbl_cc_curative, self.lbl_cc_binder,
                      self.lbl_cc_cure, self.lbl_cc_oh, self.lbl_cc_note]:
            cc_lay.addWidget(lbl_w)

        lay.addWidget(self.cure_calc_box)

        # -- MANUAL ENTRY MODE ----------------------------------------------
        self.manual_box = QWidget()
        mb_outer = QVBoxLayout(self.manual_box)
        mb_outer.setContentsMargins(0, 0, 0, 0)
        mb_outer.setSpacing(6)

        mb_desc = mono_label(
            "Enter all binder-system ingredients with their wt% (including curative).\n"
            "Functional group and Weq are shown for reference - no math applied.",
            C["text3"]
        )
        mb_desc.setWordWrap(True)
        mb_outer.addWidget(mb_desc)

        self.manual_table = IngredientTable(
            show_func_col=True, show_weq_col=True, show_include_col=False
        )
        self.manual_table.add_ingredient("HTPB", 9.94, True)
        self.manual_table.add_ingredient("IPDI", 0.82, True)
        self.manual_table.add_ingredient("IDP",  1.24, True)
        mb_outer.addWidget(self.manual_table)

        self.manual_box.hide()
        lay.addWidget(self.manual_box)

        # Wire binder/cure signals
        self.rb_cure_calc.toggled.connect(self._toggle_cure_mode)
        self.spn_nco_oh.valueChanged.connect(self._refresh_cure_calc)
        self.binder_table.changed.connect(self._on_binder_changed)
        self.manual_table.changed.connect(self._on_ingredients_changed)

        lay.addWidget(sep_line())

        # Grand total wt% indicator
        self.lbl_total = QLabel("Total:  --  wt%")
        self.lbl_total.setStyleSheet(
            f"color:{C['text2']}; font-family:Consolas,monospace; font-size:12px;"
        )
        lay.addWidget(self.lbl_total)

        # -- Run conditions -------------------------------------------------
        lay.addWidget(sep_line())
        rc = SectionCard("RUN CONDITIONS")
        f2 = QFormLayout()
        f2.setSpacing(5)
        f2.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.spn_pc  = _dspin(100, 5000, 1000, 1, 50,  " psia")
        self.spn_eps = _dspin(1.5, 60,   9.0,  2, 0.1)
        for lbl, w in [("Chamber Pc:", self.spn_pc), ("Exp ratio (eps):", self.spn_eps)]:
            f2.addRow(mono_label(lbl), w)
        rc.add_layout(f2)
        lay.addWidget(rc)

        # -- Ambient pressure -----------------------------------------------
        ac = SectionCard("AMBIENT PRESSURE")
        self.rb_manual = QRadioButton("Manual Pamb")
        self.rb_manual.setChecked(True)
        self.rb_fixed  = QRadioButton("Fixed altitude")
        self.rb_range  = QRadioButton("Altitude range")
        bg_alt = QButtonGroup(self)
        for rb in [self.rb_manual, self.rb_fixed, self.rb_range]:
            bg_alt.addButton(rb)
            ac.add(rb)
            rb.toggled.connect(self._toggle_alt)
        f3 = QFormLayout()
        f3.setSpacing(5)
        f3.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.spn_pamb   = _dspin(0.1, 30,     14.7,  3, 0.1,  " psia")
        self.spn_afixed = _dspin(0,   150000,  0,     0, 500,  " ft")
        self.spn_astart = _dspin(0,   150000,  0,     0, 500,  " ft")
        self.spn_aend   = _dspin(0,   150000, 30000,  0, 500,  " ft")
        self.lbl_pamb_calc = mono_label("", C["text3"])
        for lbl, w in [("Pamb:", self.spn_pamb), ("Fixed alt:", self.spn_afixed),
                       ("Start alt:", self.spn_astart), ("End alt:", self.spn_aend)]:
            f3.addRow(mono_label(lbl), w)
        ac.add_layout(f3)
        ac.add(self.lbl_pamb_calc)
        lay.addWidget(ac)
        self.spn_afixed.valueChanged.connect(self._update_pamb_display)
        self.spn_astart.valueChanged.connect(self._update_pamb_display)
        self.spn_aend.valueChanged.connect(self._update_pamb_display)

        # -- Efficiency factors ---------------------------------------------
        ec = SectionCard("EFFICIENCY FACTORS")
        f4 = QFormLayout()
        f4.setSpacing(5)
        f4.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.spn_cstar_eff = _dspin(0.80, 1.00, 1.0, 4, 0.001)
        self.spn_isp_eff   = _dspin(0.80, 1.00, 1.0, 4, 0.001)
        for lbl, w in [("C* efficiency:", self.spn_cstar_eff),
                       ("Isp efficiency:", self.spn_isp_eff)]:
            f4.addRow(mono_label(lbl), w)
        ec.add_layout(f4)
        lay.addWidget(ec)

        # -- Output directory -----------------------------------------------
        oc = SectionCard("OUTPUT DIRECTORY")
        self.txt_out = QLineEdit(str(DEFAULT_OUTPUT_DIR))
        btn_b = QPushButton("...")
        btn_b.setObjectName("small_btn")
        btn_b.setFixedWidth(28)
        btn_b.clicked.connect(self._browse_out)
        out_row = QHBoxLayout()
        out_row.addWidget(self.txt_out)
        out_row.addWidget(btn_b)
        oc.add_layout(out_row)
        lay.addWidget(oc)

        # -- Run button -----------------------------------------------------
        self.btn_run = QPushButton(">   RUN ANALYSIS")
        self.btn_run.setObjectName("run_btn")
        self.btn_run.setMinimumHeight(44)
        lay.addWidget(self.btn_run)
        lay.addStretch()

        # Any input change refreshes the live Wiki tab
        for widget in [
            self.spn_pc, self.spn_eps, self.spn_pamb, self.spn_afixed,
            self.spn_astart, self.spn_aend, self.spn_cstar_eff, self.spn_isp_eff,
        ]:
            widget.valueChanged.connect(self._emit_preview_changed)
        for widget in [self.txt_formula_name, self.txt_formula_tag, self.txt_out]:
            widget.textChanged.connect(self._emit_preview_changed)
        self.txt_formula_notes.textChanged.connect(self._emit_preview_changed)

        # Initial display state
        self._sync_manual_to_auto()
        self._toggle_alt()
        if self.rb_cure_calc.isChecked():
            self._refresh_cure_calc()
            self._sync_auto_to_manual()
        else:
            self._on_ingredients_changed()
        self._emit_preview_changed()

    # -- Binder / cure helpers ----------------------------------------------
    def _toggle_cure_mode(self):
        """Switch between cure-calc and manual entry modes."""
        use_calc = self.rb_cure_calc.isChecked()
        self.cure_calc_box.setVisible(use_calc)
        self.manual_box.setVisible(not use_calc)
        if use_calc:
            self._sync_manual_to_auto()
            self.binder_table.set_pct_inputs_enabled(True)
            self._refresh_cure_calc()
        else:
            # Restore editable wt% spinboxes when leaving cure-calc mode
            self.binder_table.unfreeze_all_rows()
            self._sync_auto_to_manual()
        self._on_ingredients_changed()
        self._emit_preview_changed()

    def _sync_manual_to_auto(self):
        """Use the manual-entry liquid recipe as the template for auto mode."""
        self.binder_table.set_rows(self.manual_table.get_rows())

    def _sync_auto_to_manual(self):
        """Keep manual mode aligned with the latest auto-mode liquid formulation."""
        self.manual_table.set_rows(self.binder_table.get_rows())

    def _on_solids_changed(self):
        """Refresh totals, and recompute auto-mode liquids when solids change."""
        if self.rb_cure_calc.isChecked():
            self._refresh_cure_calc()
        else:
            self._on_ingredients_changed()
        self._emit_preview_changed()

    def _row_weq(self, row: dict) -> float:
        """Return the effective Weq for a binder-table row."""
        ing = DB._find_ingredient(row["name"])
        if row.get("weq_override") and row["weq_override"] > 0:
            return float(row["weq_override"])
        return float(ing.get("Weq", 0.0)) if ing else 0.0

    def _pick_primary_auto_row(self, rows: list[dict], target_fg: str,
                               preferred_categories: tuple[int, ...]) -> Optional[int]:
        """Pick the main auto-computed OH or NCO row."""
        fallback_idx = None
        for row_idx, row in enumerate(rows):
            fg = self.binder_table.get_effective_func_group(row_idx, row["name"])
            if fg != target_fg or self._row_weq(row) <= 0:
                continue
            ing = DB._find_ingredient(row["name"])
            cat = int(ing.get("category", 8000)) if ing else 8000
            if cat in preferred_categories:
                return row_idx
            if fallback_idx is None:
                fallback_idx = row_idx
        return fallback_idx

    def _solve_auto_liquids(self, target_total: float) -> tuple[list[dict], Optional[int], Optional[int], str]:
        """
        Compute the auto-mode liquid recipe.

        The first binder-like OH row and first curative-like NCO row are treated
        as the auto-computed base pair. Any additional liquid rows keep their
        user-entered wt% and subtract from the remaining binder-system mass.
        """
        rows = self.binder_table.get_rows()
        note_parts: list[str] = []
        target_total = max(0.0, target_total)
        if not rows:
            return rows, None, None, ""

        primary_oh_idx = self._pick_primary_auto_row(rows, "OH", (3000,))
        primary_nco_idx = self._pick_primary_auto_row(rows, "NCO", (4000,))
        locked_rows = {idx for idx in (primary_oh_idx, primary_nco_idx) if idx is not None}

        fixed_total = 0.0
        fixed_oh_eq = 0.0
        fixed_nco_eq = 0.0
        excluded_names: list[str] = []

        for row_idx, row in enumerate(rows):
            ing = DB._find_ingredient(row["name"])
            if ing and not ing.get("cea_formula", "").strip():
                excluded_names.append(row["name"])
            if row_idx in locked_rows:
                continue
            wt = max(0.0, row["wt_pct"])
            fixed_total += wt
            fg = self.binder_table.get_effective_func_group(row_idx, row["name"])
            weq = self._row_weq(row)
            if fg == "OH" and weq > 0:
                fixed_oh_eq += wt / weq
            elif fg == "NCO" and weq > 0:
                fixed_nco_eq += wt / weq

        if excluded_names:
            note_parts.append(
                f"CEA note: {', '.join(excluded_names)} has no thermochemical data, so its wt% is tracked as part of the binder system."
            )

        if primary_oh_idx is None or primary_nco_idx is None:
            for row_idx in range(len(rows)):
                self.binder_table.set_row_wt_pct(row_idx, rows[row_idx]["wt_pct"])
            self.binder_table.set_pct_locked_rows(set(), "")
            if primary_oh_idx is None:
                note_parts.append("Auto mode needs one OH ingredient with Weq > 0 to compute the binder split.")
            if primary_nco_idx is None:
                note_parts.append("Auto mode needs one NCO ingredient with Weq > 0 to compute the curative split.")
            return self.binder_table.get_rows(), primary_oh_idx, primary_nco_idx, "  ".join(note_parts)

        remaining_total = target_total - fixed_total
        if remaining_total < 0:
            note_parts.append("Fixed liquid additives exceed the available liquid mass after solids, so the auto binder/curative rows were reduced to zero.")
            remaining_total = 0.0
        oh_row = rows[primary_oh_idx]
        nco_row = rows[primary_nco_idx]
        weq_oh = self._row_weq(oh_row)
        weq_nco = self._row_weq(nco_row)
        ratio = self.spn_nco_oh.value()

        binder_auto = 0.0
        curative_auto = 0.0
        impossible = False
        if remaining_total > 0 and weq_oh > 0 and weq_nco > 0:
            numerator = (remaining_total / weq_nco) + fixed_nco_eq - (ratio * fixed_oh_eq)
            denominator = (1.0 / weq_nco) + (ratio / weq_oh)
            binder_auto = numerator / denominator if denominator > 0 else 0.0
            curative_auto = remaining_total - binder_auto
            if binder_auto < 0 or curative_auto < 0:
                impossible = True
                binder_auto = max(0.0, binder_auto)
                curative_auto = max(0.0, curative_auto)
                scale = binder_auto + curative_auto
                if scale > 0:
                    binder_auto = remaining_total * (binder_auto / scale)
                    curative_auto = remaining_total - binder_auto
                else:
                    binder_auto = max(0.0, remaining_total)
                    curative_auto = 0.0
        else:
            binder_auto = max(0.0, remaining_total)

        self.binder_table.set_row_wt_pct(primary_oh_idx, binder_auto)
        self.binder_table.set_row_wt_pct(primary_nco_idx, curative_auto)
        self.binder_table.set_pct_locked_rows(
            locked_rows,
            "Auto-computed from the target NCO/OH ratio and the remaining liquid mass."
        )

        if impossible:
            note_parts.append("The fixed liquid additives over-constrained the NCO/OH target, so the auto binder/curative split was clamped to non-negative values.")

        return self.binder_table.get_rows(), primary_oh_idx, primary_nco_idx, "  ".join(note_parts)

    def _on_binder_changed(self):
        """Binder table changed - refresh cure calc and total."""
        if self.rb_cure_calc.isChecked():
            self._refresh_cure_calc()
            self._sync_auto_to_manual()
        else:
            self._on_ingredients_changed()

    def _refresh_cure_calc(self):
        """
        Compute the auto curative wt% and update the display labels.

        LOGIC
        -------------
        curative_wt = 100 - sum(solid_rows) - sum(binder_rows)

        This means the curative automatically fills whatever mass is left over
        after the user has entered all other ingredient amounts.  No numerical
        input is needed for the curative at all.

        Additionally, the NCO/OH equivalents ratio is checked against the
        computed curative mass so the user can see whether their NCO/OH target
        is achievable - but this check does NOT alter the computed mass.
        """
        if not self.rb_cure_calc.isChecked():
            return

        solid_rows = self.ing_table.get_rows()
        solid_total = sum(r["wt_pct"] for r in solid_rows)
        binder_rows, primary_oh_idx, primary_nco_idx, auto_note = self._solve_auto_liquids(
            100.0 - solid_total
        )
        nco_oh = self.spn_nco_oh.value()

        cure_name = None
        cure_weq = 0.0
        cure_wt = 0.0
        if primary_nco_idx is not None and primary_nco_idx < len(binder_rows):
            cure_row = binder_rows[primary_nco_idx]
            cure_name = cure_row["name"]
            cure_weq = self._row_weq(cure_row)
            cure_wt = cure_row["wt_pct"]

        binder_non_cure = 0.0
        oh_eq_total = 0.0
        nco_eq_total = 0.0
        for row_idx, row in enumerate(binder_rows):
            fg = self.binder_table.get_effective_func_group(row_idx, row["name"])
            weq = self._row_weq(row)
            wt = max(0.0, row["wt_pct"])
            if fg == "NCO":
                nco_eq_total += (wt / weq) if weq > 0 else 0.0
            else:
                binder_non_cure += wt
                if fg == "OH" and weq > 0:
                    oh_eq_total += wt / weq

        if cure_name:
            self.lbl_cc_curative.setText(
                f"Curative:         {cure_name}"
                + (f"  (Weq = {cure_weq:.2f} g/eq)" if cure_weq > 0 else "  (Weq not set)")
            )
        else:
            self.lbl_cc_curative.setText(
                "Curative:         none - add an NCO ingredient to the binder table"
            )

        if not cure_name:
            self.lbl_cc_curative.setText("Curative:         none - add an NCO ingredient to the binder table")

        self.lbl_cc_binder.setText(f"Binder subtotal:  {binder_non_cure:.3f} wt%")
        self.lbl_cc_cure.setText(f"Curative (auto):  {cure_wt:.3f} wt%")
        self.lbl_cc_cure.setStyleSheet(
            f"color:{C['amber']}; font-family:Consolas,monospace; font-size:11px;"
        )

        if oh_eq_total > 0 and nco_eq_total > 0:
            actual_ratio = nco_eq_total / oh_eq_total
            delta = actual_ratio - nco_oh
            status = (f"NCO/OH check:     {actual_ratio:.3f} actual  "
                      f"(target {nco_oh:.3f}  |  delta {delta:+.3f})")
            color = C["green"] if abs(delta) < 0.02 else \
                    C["amber"] if abs(delta) < 0.05 else C["text2"]
            self.lbl_cc_oh.setText(status)
            self.lbl_cc_oh.setStyleSheet(
                f"color:{color}; font-family:Consolas,monospace; font-size:11px;"
            )
        elif primary_nco_idx is None:
            self.lbl_cc_oh.setText("NCO/OH check:     add an NCO ingredient with Weq > 0 to enable")
            self.lbl_cc_oh.setStyleSheet(
                f"color:{C['text3']}; font-family:Consolas,monospace; font-size:11px;"
            )
        elif primary_oh_idx is None:
            self.lbl_cc_oh.setText("NCO/OH check:     add an OH ingredient with Weq > 0 to enable")
            self.lbl_cc_oh.setStyleSheet(
                f"color:{C['text3']}; font-family:Consolas,monospace; font-size:11px;"
            )
        else:
            self.lbl_cc_oh.setText("NCO/OH check:     set Weq values on the reactive ingredients to enable")
            self.lbl_cc_oh.setStyleSheet(
                f"color:{C['text3']}; font-family:Consolas,monospace; font-size:11px;"
            )

        self.lbl_cc_note.setText(
            auto_note or
            "Auto mode computes the primary binder/curative pair from the target NCO/OH ratio. Extra liquid rows stay editable and subtract from the auto split."
        )
        self._on_ingredients_changed()
        self._emit_preview_changed()

    def _get_binder_curative_rows(self) -> list:
        """
        Return all binder-system rows as dicts ready for the CEA run.

        Cure Calculator mode: the binder table already holds the auto-computed
        binder/curative wt% values.  Manual mode: rows exactly as typed.
        """
        if self.rb_cure_calc.isChecked():
            return list(self.binder_table.get_rows())
        else:
            return list(self.manual_table.get_rows())


    # -- Total wt% ---------------------------------------------------------
    def _on_ingredients_changed(self):
        """Recompute the grand total wt% across binder system + solids."""
        binder_rows  = self._get_binder_curative_rows()
        solid_rows   = self.ing_table.get_rows()
        total = sum(r["wt_pct"] for r in binder_rows + solid_rows)
        ok    = abs(total - 100.0) < 0.1
        self.lbl_total.setText(f"Total:  {total:.3f} wt%")
        self.lbl_total.setStyleSheet(
            f"color:{C['green'] if ok else C['red']}; "
            f"font-family:Consolas,monospace; font-size:12px; font-weight:700;"
        )
        if hasattr(self, "preview_changed"):
            self._emit_preview_changed()

    # -- Altitude helpers ---------------------------------------------------
    def _toggle_alt(self):
        is_manual = self.rb_manual.isChecked()
        is_fixed  = self.rb_fixed.isChecked()
        is_range  = self.rb_range.isChecked()
        self.spn_pamb.setVisible(is_manual)
        self.spn_afixed.setVisible(is_fixed)
        self.spn_astart.setVisible(is_range)
        self.spn_aend.setVisible(is_range)
        self._update_pamb_display()

    def _update_pamb_display(self):
        if self.rb_fixed.isChecked():
            p = single_altitude_psia(self.spn_afixed.value())
            self.lbl_pamb_calc.setText(f"->  Pamb = {p:.4f} psia")
        elif self.rb_range.isChecked():
            p = average_pressure_psia(self.spn_astart.value(), self.spn_aend.value())
            self.lbl_pamb_calc.setText(f"->  Avg Pamb = {p:.4f} psia")
        else:
            self.lbl_pamb_calc.setText("")

    def _emit_preview_changed(self, *_args):
        try:
            self.preview_changed.emit(self.get_config())
        except Exception:
            pass

    def _get_pamb(self) -> float:
        if self.rb_fixed.isChecked():
            return single_altitude_psia(self.spn_afixed.value())
        if self.rb_range.isChecked():
            return average_pressure_psia(self.spn_astart.value(), self.spn_aend.value())
        return self.spn_pamb.value()

    def _browse_out(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d:
            self.txt_out.setText(d)

    def _commit_pending_edits(self):
        """Force spinboxes to commit typed text before reading config values."""
        for box in self.findChildren(QDoubleSpinBox):
            box.interpretText()
        for box in self.findChildren(QSpinBox):
            box.interpretText()

    # -- Config serialisation -----------------------------------------------
    def get_config(self) -> dict:
        """
        Collect all UI inputs into a JSON-safe dict for the worker thread
        and for File > Save Config.
        """
        self._commit_pending_edits()
        binder_rows = self._get_binder_curative_rows()
        solid_rows  = self.ing_table.get_rows()
        return {
            "ingredients":      binder_rows + solid_rows,
            "formula_name":     self.txt_formula_name.text().strip(),
            "formula_tag":      self.txt_formula_tag.text().strip(),
            "formula_notes":    self.txt_formula_notes.toPlainText().strip(),
            "cure_mode":        "calc" if self.rb_cure_calc.isChecked() else "manual",
            "nco_oh_ratio":     self.spn_nco_oh.value(),
            "pc_psia":          self.spn_pc.value(),
            "eps":              self.spn_eps.value(),
            "pamb":             self._get_pamb(),
            "alt_mode":         ("manual" if self.rb_manual.isChecked()
                                 else "fixed" if self.rb_fixed.isChecked()
                                 else "range"),
            "alt_fixed":        self.spn_afixed.value(),
            "alt_start":        self.spn_astart.value(),
            "alt_end":          self.spn_aend.value(),
            "pamb_manual":      self.spn_pamb.value(),
            "cstar_eff":        self.spn_cstar_eff.value(),
            "isp_eff":          self.spn_isp_eff.value(),
            "output_dir":       self.txt_out.text(),
        }

    def get_propellant_config(self) -> dict:
        cfg = self.get_config()
        return {
            "formula_name": cfg.get("formula_name", ""),
            "formula_tag": cfg.get("formula_tag", ""),
            "formula_notes": cfg.get("formula_notes", ""),
            "ingredients": cfg.get("ingredients", []),
            "cure_mode": cfg.get("cure_mode", "calc"),
            "nco_oh_ratio": cfg.get("nco_oh_ratio", 0.89),
        }

    def load_config(self, cfg: dict):
        """Restore all UI inputs from a previously saved config dict."""
        binder_cats = {3000, 4000, 7000, 8000}
        solid_cats  = {1000, 2000, 5000, 6000, 9000}

        # Restore binder table (cure-calc mode)
        self.binder_table._rows.clear()
        # Restore manual table
        self.manual_table._rows.clear()
        # Restore solid table
        self.ing_table._rows.clear()

        for row in cfg.get("ingredients", []):
            ing = DB._find_ingredient(row["name"])
            cat = int(ing.get("category", 8000)) if ing else 8000
            if cat in binder_cats:
                self.binder_table.add_ingredient(
                    row["name"], row["wt_pct"],
                    row.get("include_cea", True), row.get("weq_override"),
                    row.get("func_override"))
                self.manual_table.add_ingredient(
                    row["name"], row["wt_pct"],
                    row.get("include_cea", True), row.get("weq_override"),
                    row.get("func_override"))
            elif cat in solid_cats:
                self.ing_table.add_ingredient(
                    row["name"], row["wt_pct"],
                    row.get("include_cea", True), row.get("weq_override"),
                    row.get("func_override"))

        self.txt_formula_name.setText(cfg.get("formula_name", "HTPB-AP BASELINE"))
        self.txt_formula_tag.setText(cfg.get("formula_tag", "DEV"))
        self.txt_formula_notes.setPlainText(cfg.get("formula_notes", ""))

        mode = cfg.get("cure_mode", "calc")
        if mode == "manual":
            self.rb_cure_manual.setChecked(True)
        else:
            self.rb_cure_calc.setChecked(True)

        self.spn_nco_oh.setValue(cfg.get("nco_oh_ratio", 0.89))

        self.spn_pc.setValue(cfg.get("pc_psia", 1000.0))
        self.spn_eps.setValue(cfg.get("eps", 9.0))
        self.spn_pamb.setValue(cfg.get("pamb_manual", 14.7))
        self.spn_afixed.setValue(cfg.get("alt_fixed", 0.0))
        self.spn_astart.setValue(cfg.get("alt_start", 0.0))
        self.spn_aend.setValue(cfg.get("alt_end", 30000.0))

        alt_mode = cfg.get("alt_mode", "manual")
        if alt_mode == "fixed":
            self.rb_fixed.setChecked(True)
        elif alt_mode == "range":
            self.rb_range.setChecked(True)
        else:
            self.rb_manual.setChecked(True)

        self.spn_cstar_eff.setValue(cfg.get("cstar_eff", 1.0))
        self.spn_isp_eff.setValue(cfg.get("isp_eff", 1.0))
        self.txt_out.setText(resolve_output_dir(cfg.get("output_dir")))
        self._refresh_cure_calc()
        self._on_ingredients_changed()

    def load_propellant_config(self, cfg: dict):
        merged = self.get_config()
        merged.update({
            "formula_name": cfg.get("formula_name", merged.get("formula_name", "")),
            "formula_tag": cfg.get("formula_tag", merged.get("formula_tag", "")),
            "formula_notes": cfg.get("formula_notes", merged.get("formula_notes", "")),
            "ingredients": cfg.get("ingredients", merged.get("ingredients", [])),
            "cure_mode": cfg.get("cure_mode", merged.get("cure_mode", "calc")),
            "nco_oh_ratio": cfg.get("nco_oh_ratio", merged.get("nco_oh_ratio", 0.89)),
        })
        self.load_config(merged)
