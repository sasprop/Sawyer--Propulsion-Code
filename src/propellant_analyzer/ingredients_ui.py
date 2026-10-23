"""
Ingredient UI: the add/edit ingredient dialog, the searchable ingredient
picker, and the editable ingredient table used for solids and binder rows.
"""

from __future__ import annotations

from html import escape
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)

from propellant_analyzer import database as DB
from propellant_analyzer.theme import C, CATEGORY_COLORS, CATEGORY_NAMES
from propellant_analyzer.widgets import _dspin, mono_label, sep_line


class AddIngredientDialog(QDialog):
    """
    Dialog for adding a new ingredient to user_ingredients.json.

    Supports two modes:
      1. Full CEA ingredient  - formula, Hf, density required
      2. Weight-track only    - no CEA formula; optionally binder-system with Weq
    """
    ingredient_saved = pyqtSignal()

    # Readable input method names
    WEQ_INPUT_METHODS = ["Direct Weq (g/eq)", "% NCO", "Hydroxyl Number (mg KOH/g)", "Hydroxyl Value (mmol/g)"]

    def __init__(self, parent=None, existing_ingredient: Optional[dict] = None):
        super().__init__(parent)
        self._editing = dict(existing_ingredient) if existing_ingredient else None
        self.setWindowTitle("Edit Ingredient" if self._editing else "Add New Ingredient")
        self.setMinimumWidth(560)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(16, 16, 16, 16)

        # -- Name & category ------------------------------------------------
        form_top = QFormLayout()
        form_top.setSpacing(6)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. CUO_NANO  (no spaces, uppercase preferred)")

        self.txt_aliases = QLineEdit()
        self.txt_aliases.setPlaceholderText("Comma-separated aliases, e.g. 'Copper Oxide, CuO'")

        self.cmb_category = QComboBox()
        for code, label in sorted(CATEGORY_NAMES.items()):
            self.cmb_category.addItem(f"{code}  -  {label}", code)

        self.cmb_density_status = QComboBox()
        for label, key in [("Measured / literature value", "measured"),
                           ("Estimated (rough)", "estimated"),
                           ("Not available", "none")]:
            self.cmb_density_status.addItem(label, key)
        self.cmb_density_status.setToolTip(
            "Where the density below comes from. Estimated densities are flagged on the Performance tab;\n"
            "'Not available' stores no density, and the blend density then falls back to CEA or N/A."
        )
        self.cmb_density_status.currentIndexChanged.connect(self._toggle_density_status)

        for lbl, w in [("Name *:", self.txt_name),
                       ("Aliases:", self.txt_aliases),
                       ("Category *:", self.cmb_category),
                       ("Density source:", self.cmb_density_status)]:
            form_top.addRow(mono_label(lbl), w)
        main.addLayout(form_top)
        main.addWidget(sep_line())

        # -- CEA or weight-track-only ---------------------------------------
        self.chk_cea = QCheckBox("Include in CEA (has thermochemical data)")
        self.chk_cea.setChecked(True)
        self.chk_cea.stateChanged.connect(self._toggle_cea)
        main.addWidget(self.chk_cea)

        # CEA fields
        self.cea_box = QGroupBox("CEA Thermochemical Data")
        cea_lay = QFormLayout(self.cea_box)
        cea_lay.setSpacing(6)

        self.txt_formula = QLineEdit()
        self.txt_formula.setPlaceholderText("e.g.  C 12.0 H 18.0 N 2.0 O 2.0")
        self.txt_formula.setToolTip(
            "Enter element-count pairs separated by spaces.\n"
            "Use uppercase element symbols with two-letter symbols like CL, FE, AL.\n"
            "Example: N 1.0 H 4.0 CL 1.0 O 4.0"
        )
        # Only allow uppercase letters, digits, spaces, and decimal points in formula
        self.txt_formula.textChanged.connect(self._enforce_formula_format)

        self.spn_hf = QDoubleSpinBox()
        self.spn_hf.setRange(-9999999, 9999999)
        self.spn_hf.setDecimals(1)
        self.spn_hf.setValue(0.0)
        self.spn_hf.setSingleStep(100)
        self.spn_hf.setPrefix("cal  ")
        self.spn_hf.setToolTip("Heat of formation in calories (cal/mol). Use negative for exothermic compounds.")

        self.chk_kcal = QCheckBox("Input in kcal/mol (will be converted to cal)")
        self.chk_kcal.stateChanged.connect(self._toggle_hf_units)

        self.spn_tk = _dspin(200, 400, 298.15, 2, 1.0, " K")
        self.chk_std_tk = QCheckBox("Standard (298.15 K)")
        self.chk_std_tk.setChecked(True)
        self.chk_std_tk.stateChanged.connect(self._toggle_tk)
        self._toggle_tk(Qt.CheckState.Checked.value)

        self.spn_density_cea = _dspin(0.001, 30.0, 1.0, 3, 0.1, " g/cc")

        for lbl, w in [("Formula *:", self.txt_formula),
                       ("Hf (cal/mol) *:", self.spn_hf),
                       ("Hf in kcal:", self.chk_kcal),
                       ("Reference T:", self.spn_tk),
                       ("Standard T:", self.chk_std_tk),
                       ("Density *:", self.spn_density_cea)]:
            cea_lay.addRow(mono_label(lbl), w)
        main.addWidget(self.cea_box)

        # Weight-track-only fields
        self.wt_box = QGroupBox("Weight-Track-Only Properties")
        wt_lay = QFormLayout(self.wt_box)
        wt_lay.setSpacing(6)

        self.spn_density_wt = _dspin(0.001, 30.0, 1.0, 3, 0.1, " g/cc")
        self.chk_binder_sys = QCheckBox("Part of binder system (contributes NCO or OH)")
        self.chk_binder_sys.stateChanged.connect(self._toggle_binder_sys)

        self.cmb_func_group = QComboBox()
        self.cmb_func_group.addItems(["OH", "NCO", "EPOXIDE", "Other"])
        self.cmb_func_group.setEnabled(False)

        self.cmb_weq_method = QComboBox()
        self.cmb_weq_method.addItems(self.WEQ_INPUT_METHODS)
        self.cmb_weq_method.setEnabled(False)
        self.cmb_weq_method.currentIndexChanged.connect(self._update_weq_inputs)

        self.spn_weq_direct = _dspin(0.1, 99999, 111.0, 2, 1.0, " g/eq")
        self.spn_weq_direct.setEnabled(False)

        # Additional fields for derived Weq methods
        self.weq_extra_lbl = mono_label("Value:")
        self.spn_weq_extra = _dspin(0.001, 99999, 47.1, 3, 0.1)
        self.spn_weq_extra.setEnabled(False)
        self.weq_extra_lbl.setEnabled(False)
        self.lbl_weq_result = mono_label("  Weq = -", C["amber"])

        for lbl, w in [("Density *:", self.spn_density_wt),
                       ("Binder system:", self.chk_binder_sys),
                       ("Functional group:", self.cmb_func_group),
                       ("Weq method:", self.cmb_weq_method),
                       ("Direct Weq:", self.spn_weq_direct),
                       (self.weq_extra_lbl, self.spn_weq_extra),
                       ("Computed Weq:", self.lbl_weq_result)]:
            wt_lay.addRow(lbl if isinstance(lbl, QWidget) else mono_label(lbl), w)

        self.spn_weq_extra.valueChanged.connect(self._update_weq_result)
        self.spn_weq_direct.valueChanged.connect(self._update_weq_result)

        self.wt_box.hide()
        main.addWidget(self.wt_box)

        # -- Functional group for CEA ingredients too -----------------------
        self.grp_func_cea = QGroupBox("Binder / Curative Properties")
        fc_lay = QFormLayout(self.grp_func_cea)
        fc_lay.setSpacing(6)
        self.cmb_func_cea = QComboBox()
        self.cmb_func_cea.addItems(["(none)", "OH", "NCO", "EPOXIDE", "Other"])
        self.spn_weq_cea = _dspin(0, 99999, 0, 2, 1.0, " g/eq")
        self.spn_weq_cea.setToolTip("Equivalent weight for cure calculator. Leave 0 if not applicable.")
        for lbl, w in [("Functional group:", self.cmb_func_cea),
                       ("Weq (g/eq):", self.spn_weq_cea)]:
            fc_lay.addRow(mono_label(lbl), w)
        main.addWidget(self.grp_func_cea)

        # -- Notes ----------------------------------------------------------
        self.txt_notes = QTextEdit()
        self.txt_notes.setMaximumHeight(60)
        self.txt_notes.setPlaceholderText("Optional notes (safety, typical usage, sources, etc.)")
        main.addWidget(mono_label("Notes:"))
        main.addWidget(self.txt_notes)

        # -- Validation message ---------------------------------------------
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet(f"color:{C['red']}; font-size:11px;")
        self.lbl_error.setWordWrap(True)
        main.addWidget(self.lbl_error)

        # -- Buttons --------------------------------------------------------
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setText(
            "Update Ingredient" if self._editing else "Save Ingredient"
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        main.addWidget(btns)

        self._toggle_cea(Qt.CheckState.Checked.value)
        if self._editing:
            self._load_existing()

    # -- Toggle helpers -----------------------------------------------------
    def _toggle_density_status(self, *_args):
        has_density = self.cmb_density_status.currentData() != "none"
        self.spn_density_cea.setEnabled(has_density)
        self.spn_density_wt.setEnabled(has_density)

    def _toggle_cea(self, state):
        cea = bool(state)
        self.cea_box.setVisible(cea)
        self.wt_box.setVisible(not cea)
        self.grp_func_cea.setVisible(cea)

    def _toggle_tk(self, state):
        std = bool(state)
        self.spn_tk.setEnabled(not std)
        if std:
            self.spn_tk.setValue(298.15)

    def _toggle_hf_units(self, state):
        if bool(state):
            self.spn_hf.setPrefix("kcal  ")
            self.spn_hf.setRange(-9999, 9999)
        else:
            self.spn_hf.setPrefix("cal  ")
            self.spn_hf.setRange(-9999999, 9999999)

    def _toggle_binder_sys(self, state):
        on = bool(state)
        self.cmb_func_group.setEnabled(on)
        self.cmb_weq_method.setEnabled(on)
        self._update_weq_inputs()

    def _update_weq_inputs(self):
        on = self.chk_binder_sys.isChecked()
        idx = self.cmb_weq_method.currentIndex()
        self.spn_weq_direct.setEnabled(on and idx == 0)
        self.spn_weq_extra.setEnabled(on and idx > 0)
        self.weq_extra_lbl.setEnabled(on and idx > 0)
        method_hints = ["", "% NCO value:", "Hydroxyl number (mg KOH/g):", "Hydroxyl value (mmol/g):"]
        if idx < len(method_hints):
            self.weq_extra_lbl.setText(method_hints[idx] or "Value:")
        self._update_weq_result()

    def _update_weq_result(self):
        if not self.chk_binder_sys.isChecked():
            self.lbl_weq_result.setText("  Weq = -")
            return
        try:
            idx = self.cmb_weq_method.currentIndex()
            if idx == 0:
                weq = self.spn_weq_direct.value()
            elif idx == 1:
                weq = DB.weq_from_percent_nco(self.spn_weq_extra.value())
            elif idx == 2:
                weq = DB.weq_from_hydroxyl_number(self.spn_weq_extra.value())
            elif idx == 3:
                weq = DB.weq_from_hydroxyl_value(self.spn_weq_extra.value())
            else:
                weq = 0.0
            self.lbl_weq_result.setText(f"  Weq = {weq:.3f} g/eq")
        except Exception as e:
            self.lbl_weq_result.setText(f"  Error: {e}")

    def _enforce_formula_format(self, text: str):
        """Keep formula field uppercase; reject invalid characters."""
        clean = "".join(c for c in text.upper() if c.isalpha() or c.isdigit() or c in ". ")
        if clean != text:
            pos = self.txt_formula.cursorPosition()
            self.txt_formula.blockSignals(True)
            self.txt_formula.setText(clean)
            self.txt_formula.setCursorPosition(min(pos, len(clean)))
            self.txt_formula.blockSignals(False)

    def _computed_weq(self) -> float:
        """Return the resolved Weq from whatever method is active."""
        if self.chk_cea.isChecked():
            return float(self.spn_weq_cea.value())
        if not self.chk_binder_sys.isChecked():
            return 0.0
        idx = self.cmb_weq_method.currentIndex()
        try:
            if idx == 0:
                return float(self.spn_weq_direct.value())
            if idx == 1:
                return DB.weq_from_percent_nco(self.spn_weq_extra.value())
            if idx == 2:
                return DB.weq_from_hydroxyl_number(self.spn_weq_extra.value())
            if idx == 3:
                return DB.weq_from_hydroxyl_value(self.spn_weq_extra.value())
        except Exception:
            pass
        return 0.0

    def _load_existing(self):
        ing = self._editing or {}
        self.txt_name.setText(ing.get("name", ""))
        self.txt_aliases.setText(", ".join(ing.get("aliases", [])))
        idx = self.cmb_category.findData(int(ing.get("category", 8000)))
        self.cmb_category.setCurrentIndex(idx if idx >= 0 else 0)
        self.txt_notes.setPlainText(ing.get("notes", ""))
        status_idx = self.cmb_density_status.findData(DB.density_status(ing))
        self.cmb_density_status.setCurrentIndex(status_idx if status_idx >= 0 else 0)

        has_cea = bool(ing.get("cea_formula", "").strip())
        self.chk_cea.setChecked(has_cea)
        self._toggle_cea(Qt.CheckState.Checked.value if has_cea else 0)
        if has_cea:
            self.txt_formula.setText(ing.get("cea_formula", ""))
            self.chk_kcal.setChecked(False)
            self.spn_hf.setValue(float(ing.get("h_cal", 0.0)))
            t_k = float(ing.get("t_k", 298.15))
            self.chk_std_tk.setChecked(abs(t_k - 298.15) < 1e-6)
            if abs(t_k - 298.15) >= 1e-6:
                self.spn_tk.setValue(t_k)
            self.spn_density_cea.setValue(float(ing.get("density", 0.0)) or 1.0)
            func_g = ing.get("functional_group", "") or "(none)"
            idx = self.cmb_func_cea.findText(func_g if func_g != "" else "(none)")
            self.cmb_func_cea.setCurrentIndex(idx if idx >= 0 else 0)
            self.spn_weq_cea.setValue(float(ing.get("Weq", 0.0)))
        else:
            self.spn_density_wt.setValue(float(ing.get("density", 0.0)) or 1.0)
            func_g = ing.get("functional_group", "")
            binder_on = bool(func_g or float(ing.get("Weq", 0.0)) > 0.0)
            self.chk_binder_sys.setChecked(binder_on)
            self._toggle_binder_sys(Qt.CheckState.Checked.value if binder_on else 0)
            if func_g:
                idx = self.cmb_func_group.findText(func_g)
                self.cmb_func_group.setCurrentIndex(idx if idx >= 0 else 0)
            self.cmb_weq_method.setCurrentIndex(0)
            self.spn_weq_direct.setValue(float(ing.get("Weq", 0.0)))
            self._update_weq_result()

    # -- Validation ---------------------------------------------------------
    def _validate(self) -> Optional[str]:
        """Return an error message string, or None if inputs are valid."""
        name = self.txt_name.text().strip()
        if not name:
            return "Name is required."
        if " " in name:
            return "Name must not contain spaces (use underscores)."

        # Check for duplicate name
        editing_id = self._editing.get("id") if self._editing else None
        existing_names = [
            i["name"].upper()
            for i in DB.get_all_ingredients()
            if i.get("id") != editing_id
        ]
        if name.upper() in existing_names:
            return f"An ingredient named '{name}' already exists in the database."

        if self.chk_cea.isChecked():
            formula = self.txt_formula.text().strip()
            if not formula:
                return "CEA formula is required when 'Include in CEA' is checked."
            # Basic formula syntax check: expect pairs of ELEMENT COUNT
            tokens = formula.split()
            if len(tokens) < 2 or len(tokens) % 2 != 0:
                return (
                    "Formula must be element-count pairs, e.g. 'C 7.337 H 10.982 O 0.058'.\n"
                    "Number of tokens must be even."
                )
        else:
            if self.chk_binder_sys.isChecked():
                try:
                    weq = self._computed_weq()
                    if weq <= 0:
                        return "Computed Weq must be greater than zero for binder-system ingredients."
                except Exception as e:
                    return f"Weq calculation error: {e}"

        return None

    # -- Save ---------------------------------------------------------------
    def _save(self):
        err = self._validate()
        if err:
            self.lbl_error.setText(err)
            return

        existing = self._editing or {}
        name     = self.txt_name.text().strip().upper()
        aliases  = [a.strip() for a in self.txt_aliases.text().split(",") if a.strip()]
        old_name = existing.get("name", "").strip().upper()
        if old_name and old_name != name and all(a.upper() != old_name for a in aliases):
            aliases.insert(0, old_name)
        category = self.cmb_category.currentData()
        notes    = self.txt_notes.toPlainText().strip()
        ingredient_id = existing.get("id", DB.next_user_id())
        particles = list(existing.get("particles", [0]))
        phase = existing.get("phase", "")

        if self.chk_cea.isChecked():
            # Resolve Hf: convert kcal a cal if needed
            hf_raw = self.spn_hf.value()
            hf_cal = hf_raw * 1000.0 if self.chk_kcal.isChecked() else hf_raw
            t_k    = 298.15 if self.chk_std_tk.isChecked() else self.spn_tk.value()
            func_g = self.cmb_func_cea.currentText()
            if func_g == "(none)":
                func_g = ""
            ingredient = {
                "id":              ingredient_id,
                "name":            name,
                "aliases":         aliases,
                "category":        category,
                "cea_formula":     self.txt_formula.text().strip().upper(),
                "h_cal":           hf_cal,
                "t_k":             t_k,
                "density":         self.spn_density_cea.value(),
                "Weq":             float(self.spn_weq_cea.value()),
                "particles":       particles,
                "functional_group": func_g,
                "phase":           phase,
                "notes":           notes,
            }
        else:
            func_g = self.cmb_func_group.currentText() if self.chk_binder_sys.isChecked() else ""
            weq    = self._computed_weq()
            ingredient = {
                "id":              ingredient_id,
                "name":            name,
                "aliases":         aliases,
                "category":        category,
                "cea_formula":     "",          # No CEA data
                "h_cal":           0.0,
                "t_k":             298.15,
                "density":         self.spn_density_wt.value(),
                "Weq":             weq,
                "particles":       particles,
                "functional_group": func_g,
                "phase":           phase,
                "notes":           notes,
            }

        status = self.cmb_density_status.currentData()
        if status == "none":
            ingredient["density"] = 0.0
        if status != "measured":
            ingredient["density_status"] = status
        if existing.get("density_note") and DB.density_status(existing) == status:
            ingredient["density_note"] = existing["density_note"]

        DB.save_user_ingredient(ingredient)
        self.ingredient_saved.emit()
        self.accept()


class IngredientPickerDialog(QDialog):
    """Searchable popup for choosing an ingredient row from the database."""

    def __init__(self, parent=None, title: str = "Select Ingredient",
                 initial_name: Optional[str] = None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setModal(True)
        self.setWindowTitle(title)
        self.resize(1180, 640)
        self._selected_name = None
        self._initial_name = (initial_name or "").strip().upper()
        self._all_items: list[dict] = []
        self._filtered_rows: list[dict] = []
        self._search_index: list[tuple[dict, str]] = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(120)
        self._search_timer.timeout.connect(self._populate)

        main = QVBoxLayout(self)
        main.setSpacing(8)
        main.setContentsMargins(14, 14, 14, 14)

        controls = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search by name, alias, formula, category, or note...")
        self.txt_search.textChanged.connect(self._schedule_populate)
        controls.addWidget(self.txt_search, 1)

        self.cmb_category = QComboBox()
        self.cmb_category.addItem("All categories", None)
        for code, label in sorted(CATEGORY_NAMES.items()):
            self.cmb_category.addItem(label, code)
        self.cmb_category.currentIndexChanged.connect(self._populate)
        controls.addWidget(self.cmb_category)

        self.lbl_count = mono_label("0 ingredients", C["text3"])
        controls.addWidget(self.lbl_count)
        main.addLayout(controls)

        actions = QHBoxLayout()
        self.btn_new = QPushButton("New Ingredient...")
        self.btn_new.clicked.connect(self._add_new_ingredient)
        actions.addWidget(self.btn_new)

        self.btn_edit = QPushButton("Edit Selected...")
        self.btn_edit.clicked.connect(self._edit_selected_ingredient)
        self.btn_edit.setEnabled(False)
        actions.addWidget(self.btn_edit)

        self.btn_reload = QPushButton("Reload Database")
        self.btn_reload.clicked.connect(self._reload_items)
        actions.addWidget(self.btn_reload)
        actions.addStretch()
        main.addLayout(actions)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels(
            ["Ingredient", "Type", "Phase", "CEA", "Func Group", "Density", "Hf", "Weq"]
        )
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.verticalHeader().setDefaultSectionSize(26)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.itemDoubleClicked.connect(lambda *_args: self._accept_selection())
        self.tbl.currentCellChanged.connect(self._update_details)
        left_lay.addWidget(self.tbl, 1)
        split.addWidget(left)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)

        self.lbl_selected = mono_label("Select an ingredient to see details.", C["amber"], 12)
        right_lay.addWidget(self.lbl_selected)

        self.txt_details = QTextEdit()
        self.txt_details.setReadOnly(True)
        self.txt_details.setMinimumWidth(380)
        self.txt_details.setPlaceholderText("Ingredient details will appear here.")
        right_lay.addWidget(self.txt_details, 1)
        split.addWidget(right)
        split.setSizes([700, 420])

        main.addWidget(split, 1)

        self.lbl_hint = mono_label(
            "Double-click an ingredient or select a row and press Choose.",
            C["text3"],
        )
        main.addWidget(self.lbl_hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Choose")
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        main.addWidget(buttons)

        self._reload_items(self._initial_name or None)
        self.txt_search.setFocus()

    def _rebuild_index(self):
        self._all_items = DB.get_all_ingredients()
        self._search_index = [
            (
                ing,
                " ".join(
                    [
                        ing.get("name", ""),
                        " ".join(ing.get("aliases", [])),
                        ing.get("cea_formula", ""),
                        CATEGORY_NAMES.get(int(ing.get("category", 8000)), "Unknown"),
                        ing.get("notes", ""),
                        ing.get("phase", ""),
                        ing.get("functional_group", ""),
                    ]
                ).upper(),
            )
            for ing in self._all_items
        ]

    def _reload_items(self, keep_name: Optional[str] = None):
        self._rebuild_index()
        if keep_name:
            self._initial_name = keep_name.strip().upper()
        self._populate()

    def _restore_selection(self, wanted_name: Optional[str]):
        target = (wanted_name or "").strip().upper()
        if not target:
            return
        for row_idx, ing in enumerate(self._filtered_rows):
            if ing.get("name", "").strip().upper() == target:
                self.tbl.setCurrentCell(row_idx, 0)
                self.tbl.scrollToItem(self.tbl.item(row_idx, 0))
                self._update_details(row_idx)
                return

    def _selected_ingredient(self) -> Optional[dict]:
        row = self.tbl.currentRow()
        if 0 <= row < len(self._filtered_rows):
            return self._filtered_rows[row]
        return None

    def _schedule_populate(self):
        self._search_timer.start()

    def _populate(self):
        search = self.txt_search.text().strip().upper()
        terms = [term for term in search.split() if term]
        wanted_cat = self.cmb_category.currentData()
        current_name = ""
        current_ing = self._selected_ingredient()
        if current_ing:
            current_name = current_ing.get("name", "")
        rows = []
        for ing, haystack in self._search_index:
            if wanted_cat is not None and int(ing.get("category", 8000)) != int(wanted_cat):
                continue
            if terms and not all(term in haystack for term in terms):
                continue
            rows.append(ing)

        self._filtered_rows = rows
        self.lbl_count.setText(f"{len(rows)} ingredient{'s' if len(rows) != 1 else ''}")
        self.tbl.setUpdatesEnabled(False)
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(0)
        self.tbl.setRowCount(len(rows))
        for row_idx, ing in enumerate(rows):
            self.tbl.setItem(row_idx, 0, QTableWidgetItem(ing.get("name", "")))
            cat = int(ing.get("category", 8000))
            self.tbl.setItem(
                row_idx, 1,
                QTableWidgetItem(CATEGORY_NAMES.get(cat, "Unknown"))
            )
            self.tbl.setItem(row_idx, 2, QTableWidgetItem(ing.get("phase", "") or "-"))
            self.tbl.setItem(
                row_idx, 3,
                QTableWidgetItem("Yes" if ing.get("cea_formula", "").strip() else "No")
            )
            self.tbl.setItem(row_idx, 4, QTableWidgetItem(ing.get("functional_group", "") or "-"))
            dens_item = QTableWidgetItem(DB.density_text(ing))
            if DB.density_status(ing) != "measured":
                dens_item.setForeground(QColor(C["amber"]))
                dens_item.setToolTip(ing.get("density_note", "") or "No density in the database.")
            self.tbl.setItem(row_idx, 5, dens_item)
            hf_cal = float(ing.get("h_cal", 0.0))
            self.tbl.setItem(
                row_idx, 6,
                QTableWidgetItem(f"{hf_cal / 1000.0:.3f}" if hf_cal != 0.0 else "-")
            )
            self.tbl.setItem(
                row_idx, 7,
                QTableWidgetItem(f"{float(ing.get('Weq', 0.0)):.2f}" if float(ing.get("Weq", 0.0)) > 0 else "-")
            )
            type_item = self.tbl.item(row_idx, 1)
            if type_item is not None:
                type_item.setForeground(QColor(CATEGORY_COLORS.get(cat, C["text2"])))
        if rows:
            self.tbl.setCurrentCell(0, 0)
            selected_row = 0
        else:
            self.lbl_selected.setText("No matching ingredients.")
            self.txt_details.clear()
            self.btn_edit.setEnabled(False)
            selected_row = -1
        self.tbl.blockSignals(False)
        self.tbl.setUpdatesEnabled(True)
        if selected_row >= 0:
            restore_name = self._initial_name or current_name
            self._restore_selection(restore_name)
            self._initial_name = ""
            if not self._selected_ingredient():
                self._update_details(selected_row)

    def _update_details(self, row: int, *_args):
        if not (0 <= row < len(self._filtered_rows)):
            self.lbl_selected.setText("No matching ingredients.")
            self.txt_details.clear()
            self.btn_edit.setEnabled(False)
            return

        ing = self._filtered_rows[row]
        self.btn_edit.setEnabled(True)
        name = ing.get("name", "")
        aliases = ing.get("aliases", [])
        cat = CATEGORY_NAMES.get(int(ing.get("category", 8000)), "Unknown")
        phase = ing.get("phase", "") or "-"
        func = ing.get("functional_group", "") or "-"
        dens_status = DB.density_status(ing)
        if dens_status == "none":
            density_html = f"<span style='color:{C['amber']};'>Not available</span>"
        else:
            density_html = f"{float(ing.get('density', 0.0)):.3f} g/cc"
            if dens_status == "estimated":
                density_html += f" <span style='color:{C['amber']}; font-weight:700;'>ESTIMATED</span>"
        if ing.get("density_note"):
            density_html += f"<br><span style='color:{C['text2']}; font-size:11px;'>{escape(ing['density_note'])}</span>"
        hf_cal = float(ing.get("h_cal", 0.0))
        weq = float(ing.get("Weq", 0.0))
        has_cea = bool(ing.get("cea_formula", "").strip())
        formula = ing.get("cea_formula", "").strip() or "No CEA formula stored"
        notes = ing.get("notes", "").strip() or "No notes"

        self.lbl_selected.setText(name)
        html = f"""
        <div style="font-family:'Segoe UI'; color:{C['text1']}; line-height:1.45;">
          <div style="font-family:Consolas,monospace; font-size:18px; font-weight:700; color:{C['amber']}; margin-bottom:8px;">{escape(name)}</div>
          <table style="width:100%; border-collapse:collapse; font-size:12px; margin-bottom:10px;">
            <tr><td style="padding:4px 8px 4px 0; color:{C['text2']};">Type</td><td style="padding:4px 0; color:{CATEGORY_COLORS.get(int(ing.get('category', 8000)), C['text1'])}; font-weight:700;">{escape(cat)}</td></tr>
            <tr><td style="padding:4px 8px 4px 0; color:{C['text2']};">Phase</td><td style="padding:4px 0;">{escape(phase)}</td></tr>
            <tr><td style="padding:4px 8px 4px 0; color:{C['text2']};">Solver status</td><td style="padding:4px 0;">{"CEA-ready" if has_cea else "Reference only"}</td></tr>
            <tr><td style="padding:4px 8px 4px 0; color:{C['text2']};">CEA data</td><td style="padding:4px 0;">{"Yes" if has_cea else "No"}</td></tr>
            <tr><td style="padding:4px 8px 4px 0; color:{C['text2']};">Functional group</td><td style="padding:4px 0;">{escape(func)}</td></tr>
            <tr><td style="padding:4px 8px 4px 0; color:{C['text2']};">Density</td><td style="padding:4px 0;">{density_html}</td></tr>
            <tr><td style="padding:4px 8px 4px 0; color:{C['text2']};">Heat of formation</td><td style="padding:4px 0;">{f"{hf_cal:,.1f} cal/mol  ({hf_cal / 1000.0:.3f} kcal/mol)" if hf_cal != 0.0 else "-"}</td></tr>
            <tr><td style="padding:4px 8px 4px 0; color:{C['text2']};">Weq</td><td style="padding:4px 0;">{f"{weq:.2f} g/eq" if weq > 0 else "-"}</td></tr>
          </table>
          <div style="margin-bottom:8px;"><span style="color:{C['text2']};">Aliases:</span> {escape(', '.join(aliases) if aliases else 'None')}</div>
          <div style="margin-bottom:8px;"><span style="color:{C['text2']};">CEA formula:</span> <code>{escape(formula)}</code></div>
          <div><span style="color:{C['text2']};">Notes:</span><br>{escape(notes)}</div>
        </div>
        """
        self.txt_details.setHtml(html)

    def _add_new_ingredient(self):
        dlg = AddIngredientDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_items(dlg.txt_name.text().strip().upper())

    def _edit_selected_ingredient(self):
        ing = self._selected_ingredient()
        if not ing:
            return
        dlg = AddIngredientDialog(self, existing_ingredient=ing)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_items(dlg.txt_name.text().strip().upper())

    def _accept_selection(self):
        items = self.tbl.selectedItems()
        if not items:
            return
        row = items[0].row()
        name_item = self.tbl.item(row, 0)
        if name_item is None:
            return
        self._selected_name = name_item.text().strip()
        self.accept()

    def selected_name(self) -> Optional[str]:
        return self._selected_name


# =============================================================================
#  INGREDIENT TABLE ROW DATA  (used by IngredientTable)
# =============================================================================

class IngredientRowData:
    """
    Data holder for one row in the unified ingredient table.
    Not a QWidget a the table renders it.
    """
    __slots__ = [
        "name",        # str  - DB primary name
        "wt_pct",      # float
        "include_cea", # bool a True = include in CEA run
        "func_override", # str or None
        "weq_override",# float or None
    ]

    def __init__(self, name: str = "AP_CUSTOM", wt_pct: float = 0.0,
                 include_cea: bool = True, weq_override: float = None,
                 func_override: Optional[str] = None):
        self.name         = name
        self.wt_pct       = wt_pct
        self.include_cea  = include_cea
        self.func_override = func_override
        self.weq_override = weq_override


# =============================================================================
#  INGREDIENT TABLE (unified, replaces binder section + solid ingredients)
# =============================================================================

class IngredientTable(QWidget):
    """
    Reusable ingredient table used for both the binder system and the main
    propellant ingredients list.

    show_func_col : bool a show the Functional Group override column
    show_weq_col  : bool a show the Weq override spinbox column
    """
    changed = pyqtSignal()

    COL_INCLUDE  = 0
    COL_NAME     = 1
    COL_PCT      = 2
    COL_TYPE     = 3
    COL_FUNC     = 4
    COL_WEQ      = 5
    COL_REMOVE   = 6
    N_COLS       = 7

    HEADERS = ["CEA", "Ingredient", "wt %", "Type", "Func Group", "Weq  (g/eq)", ""]

    def __init__(self, show_func_col: bool = True, show_weq_col: bool = True,
                 show_include_col: bool = True):
        super().__init__()
        self._show_include = show_include_col
        self._show_func = show_func_col
        self._show_weq  = show_weq_col
        self._pct_inputs_enabled = True
        self._pct_disabled_tooltip = ""
        self._pct_locked_rows: set[int] = set()
        self._pct_locked_tooltip = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.table = QTableWidget(0, self.N_COLS)
        self.table.setHorizontalHeaderLabels(self.HEADERS)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            self.table.styleSheet() +
            f"QTableWidget {{ alternate-background-color: {C['bg2']}; }}"
        )
        # Column widths a ALL Fixed so they never collapse when cells hold
        # QWidget objects (cellWidget) rather than plain QTableWidgetItems.
        # ResizeToContents does not measure widget-based cells correctly.
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_INCLUDE, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_NAME,    QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(self.COL_PCT,     QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_TYPE,    QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_FUNC,    QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_WEQ,     QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_REMOVE,  QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(self.COL_INCLUDE,  44)
        self.table.setColumnWidth(self.COL_NAME,     220)
        self.table.setColumnWidth(self.COL_PCT,       82)
        self.table.setColumnWidth(self.COL_TYPE,     112)
        self.table.setColumnWidth(self.COL_FUNC,     132)
        self.table.setColumnWidth(self.COL_WEQ,      118)
        self.table.setColumnWidth(self.COL_REMOVE,    28)
        # Hide optional columns based on constructor flags
        if not self._show_include:
            self.table.setColumnHidden(self.COL_INCLUDE, True)
        if not self._show_func:
            self.table.setColumnHidden(self.COL_FUNC, True)
        if not self._show_weq:
            self.table.setColumnHidden(self.COL_WEQ, True)
        # Horizontal scrollbar so all columns remain reachable in a narrow sidebar
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        # Vertical scrollbar hidden a height auto-fits all rows instead
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setMinimumHeight(60)   # Fallback floor only

        lay.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+  Add Ingredient")
        self.btn_add.setObjectName("small_btn")
        # Use lambda to discard the bool 'checked' argument that QPushButton.clicked
        # always passes a without this, 'name' receives False instead of "AP_CUSTOM"
        self.btn_add.clicked.connect(lambda _checked=False: self._add_row())
        btn_row.addWidget(self.btn_add)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._rows: list[IngredientRowData] = []
        self._refreshing = False   # Guard against recursive signals

        # Expanding horizontally, Fixed vertically so the table always shows all
        # rows without a vertical scrollbar and without leaving dead space.
        from PyQt6.QtWidgets import QSizePolicy as SP
        self.setSizePolicy(SP.Policy.Expanding, SP.Policy.Fixed)

    # -- Public helpers -----------------------------------------------------
    # -- Height management --------------------------------------------------
    def sizeHint(self):
        """
        Return the exact height needed to show all rows plus the header,
        with no dead space and no vertical scrollbar.

        Qt calls sizeHint() during layout passes, so this is more reliable
        than setFixedHeight() + QTimer because it runs at the right moment
        in the layout cycle rather than being deferred and potentially stale.
        """
        from PyQt6.QtCore import QSize
        header_h = self.table.horizontalHeader().height()
        rows_h   = sum(self.table.rowHeight(r) for r in range(self.table.rowCount()))
        scroll_h = self.table.horizontalScrollBar().sizeHint().height()
        # 4 px for top + bottom border; 32 px floor for at least one visible row
        table_h  = max(header_h + rows_h + 4 + scroll_h, header_h + 34)
        # Add height of the button row below the table (~28 px)
        total_h  = table_h + 28
        return QSize(super().sizeHint().width(), total_h)

    def minimumSizeHint(self):
        return self.sizeHint()

    def _fit_table_height(self):
        """
        Apply the computed height to the QTableWidget and notify the layout.
        Called after every _refresh_table() so the table never clips rows.
        """
        header_h = self.table.horizontalHeader().height()
        rows_h   = sum(self.table.rowHeight(r) for r in range(self.table.rowCount()))
        scroll_h = self.table.horizontalScrollBar().sizeHint().height()
        target   = max(header_h + rows_h + 4 + scroll_h, header_h + 34)
        self.table.setFixedHeight(target)
        # Tell the layout engine this widget's size has changed
        self.updateGeometry()

    def set_pct_inputs_enabled(self, enabled: bool, tooltip: str = ""):
        """Globally enable or lock wt% entry for the percent spinboxes."""
        self._pct_inputs_enabled = enabled
        self._pct_disabled_tooltip = tooltip if not enabled else ""
        for row_idx in range(self.table.rowCount()):
            spn = self.table.cellWidget(row_idx, self.COL_PCT)
            self._apply_pct_spinbox_state(spn, row_idx=row_idx)

    def set_pct_locked_rows(self, row_idxs: set[int], tooltip: str = ""):
        """Lock only the specified wt% rows while keeping the others editable."""
        self._pct_locked_rows = set(row_idxs)
        self._pct_locked_tooltip = tooltip
        for row_idx in range(self.table.rowCount()):
            spn = self.table.cellWidget(row_idx, self.COL_PCT)
            self._apply_pct_spinbox_state(spn, row_idx=row_idx)

    def set_row_wt_pct(self, row_idx: int, wt_pct: float):
        """Programmatically update one wt% spinbox without emitting row-change signals."""
        spn = self.table.cellWidget(row_idx, self.COL_PCT)
        if not isinstance(spn, QDoubleSpinBox):
            return
        spn.blockSignals(True)
        spn.setValue(max(0.0, wt_pct))
        spn.blockSignals(False)
        if 0 <= row_idx < len(self._rows):
            self._rows[row_idx].wt_pct = max(0.0, wt_pct)

    def set_rows(self, rows: list[dict]):
        """Replace the table contents from serialized row dictionaries."""
        self._rows = [
            IngredientRowData(
                row.get("name", "AP_CUSTOM"),
                row.get("wt_pct", 0.0),
                row.get("include_cea", True),
                row.get("weq_override"),
                row.get("func_override"),
            )
            for row in rows
        ]
        self._refresh_table()

    def _apply_pct_spinbox_state(self, spn, row_idx: Optional[int] = None,
                                 enabled: Optional[bool] = None,
                                 tooltip: Optional[str] = None,
                                 style: Optional[str] = None):
        """Apply the default editable/locked state or an explicit override."""
        if not isinstance(spn, QDoubleSpinBox):
            return
        if enabled is None:
            use_enabled = self._pct_inputs_enabled
            if row_idx is not None and row_idx in self._pct_locked_rows:
                use_enabled = False
        else:
            use_enabled = enabled
        use_tooltip = "" if use_enabled else (
            (
                self._pct_locked_tooltip
                if tooltip is None and row_idx is not None and row_idx in self._pct_locked_rows
                else self._pct_disabled_tooltip if tooltip is None else tooltip
            )
        )
        if style is None:
            use_style = (
                ""
                if use_enabled else
                f"background:{C['bg0']}; color:{C['text3']}; "
                f"border:1px solid {C['border']}; "
                f"font-family:Consolas,monospace; font-size:12px;"
            )
        else:
            use_style = style
        spn.setEnabled(use_enabled)
        spn.setToolTip(use_tooltip)
        spn.setStyleSheet(use_style)

    # -- NCO row freeze (cure-calc mode) ------------------------------------
    def unfreeze_all_rows(self):
        """Re-enable all wt% spinboxes (called when switching to manual mode)."""
        self._pct_locked_rows.clear()
        self._pct_locked_tooltip = ""
        self.set_pct_inputs_enabled(True)


    def add_ingredient(self, name: str, wt_pct: float,
                       include_cea: bool = True, weq_override=None,
                       func_override: Optional[str] = None):
        """Append a row with given data and refresh the table."""
        row = IngredientRowData(name, wt_pct, include_cea, weq_override, func_override)
        self._rows.append(row)
        self._refresh_table()

    def get_rows(self) -> list:
        """
        Return a list of dicts with keys: name, wt_pct, include_cea, weq_override.
        Reads live values from the table widgets.
        """
        results = []
        for r in range(self.table.rowCount()):
            chk  = self.table.cellWidget(r, self.COL_INCLUDE)
            spn  = self.table.cellWidget(r, self.COL_PCT)
            func_w = self.table.cellWidget(r, self.COL_FUNC)
            weq_w = self.table.cellWidget(r, self.COL_WEQ)
            if not spn:
                continue
            include_cea = chk.isChecked() if isinstance(chk, QCheckBox) else True
            func_override = None
            if isinstance(func_w, QComboBox) and func_w.currentIndex() > 0:
                func_override = func_w.currentText()
            weq_val = None
            if weq_w and isinstance(weq_w, QDoubleSpinBox) and weq_w.isEnabled():
                v = weq_w.value()
                weq_val = v if v > 0 else None
            results.append({
                "name":         self._rows[r].name if 0 <= r < len(self._rows) else "",
                "wt_pct":       spn.value(),
                "include_cea":  include_cea,
                "func_override": func_override,
                "weq_override": weq_val,
            })
        return results

    def refresh_names(self):
        """Refresh row labels and derived cells after a database edit."""
        for r in range(self.table.rowCount()):
            if not (0 <= r < len(self._rows)):
                continue
            btn = self.table.cellWidget(r, self.COL_NAME)
            name = self._rows[r].name
            if isinstance(btn, QPushButton):
                btn.setText(name)
                btn.setToolTip(f"Click to choose a different ingredient.\nCurrent: {name}")
            self._set_type_cell(r, name)
            self._set_func_cell(r, name, self._rows[r].func_override)
            self._set_weq_cell(r, name, self._rows[r].weq_override)

    def _pick_ingredient_name(self, current_name: str = "", title: str = "Select Ingredient") -> Optional[str]:
        dlg = IngredientPickerDialog(self, title, initial_name=current_name)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.selected_name()

    # -- Internal -----------------------------------------------------------
    def _add_row(self, name: str = "AP_CUSTOM", wt_pct: float = 0.0):
        if name == "AP_CUSTOM" and wt_pct == 0.0:
            picked_name = self._pick_ingredient_name("", "Add Ingredient")
            if not picked_name:
                return
            name = picked_name
        row = IngredientRowData(name, wt_pct, True, None)
        self._rows.append(row)
        self._refresh_table()

    def _remove_row(self, row_idx: int):
        if 0 <= row_idx < len(self._rows):
            self._rows.pop(row_idx)
        self._refresh_table()
        self.changed.emit()

    def _refresh_table(self):
        """Rebuild the table from self._rows. Heavy but simple."""
        if self._refreshing:
            return
        self._refreshing = True
        self.table.setRowCount(0)

        for row_idx, row_data in enumerate(self._rows):
            self.table.insertRow(row_idx)
            self.table.setRowHeight(row_idx, 30)

            # Col 0 a Include in CEA checkbox
            chk = QCheckBox()
            chk.setChecked(row_data.include_cea)
            chk.setStyleSheet("margin-left:12px;")
            ing = DB._find_ingredient(row_data.name)
            has_cea = bool(ing and ing.get("cea_formula", "").strip()) if ing else False
            if not has_cea:
                chk.setEnabled(False)
                chk.setToolTip("No CEA thermochemical data a weight-track only.")
            chk.stateChanged.connect(lambda _, ri=row_idx: self._on_row_changed(ri))
            self.table.setCellWidget(row_idx, self.COL_INCLUDE, chk)

            # Col 1 a Name chooser button
            btn_name = QPushButton(row_data.name)
            btn_name.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_name.setStyleSheet(
                f"QPushButton {{"
                f"background:{C['bg2']}; border:1px solid {C['border2']}; border-radius:5px;"
                f"padding:4px 8px; color:{C['text0']}; text-align:left;"
                f"font-family:'Consolas','Courier New',monospace; font-size:12px;"
                f"}}"
                f"QPushButton:hover {{ background:{C['bg3']}; border-color:{C['amber']}; }}"
            )
            btn_name.setToolTip(
                f"Click to choose a different ingredient.\nCurrent: {row_data.name}"
            )
            btn_name.clicked.connect(lambda _checked=False, ri=row_idx: self._choose_row_name(ri))
            self.table.setCellWidget(row_idx, self.COL_NAME, btn_name)

            # Col 2 a wt% spinner
            spn = _dspin(0.0, 100.0, row_data.wt_pct, 3, 0.1, " wt%")
            spn.valueChanged.connect(lambda _, ri=row_idx: self._on_row_changed(ri))
            self._apply_pct_spinbox_state(spn, row_idx=row_idx)
            self.table.setCellWidget(row_idx, self.COL_PCT, spn)

            # Col 3 a Type badge (read-only label)
            self._set_type_cell(row_idx, row_data.name)

            # Col 4 a Functional group label with override dropdown
            self._set_func_cell(row_idx, row_data.name, row_data.func_override)

            # Col 5 a Weq (editable spinbox if applicable)
            self._set_weq_cell(row_idx, row_data.name, row_data.weq_override)

            # Col 6 a Remove button
            btn = QPushButton("x")
            btn.setObjectName("danger_btn")
            btn.setFixedSize(26, 22)
            btn.clicked.connect(lambda _, ri=row_idx: self._remove_row(ri))
            self.table.setCellWidget(row_idx, self.COL_REMOVE, btn)

        self._refreshing = False
        self._fit_table_height()
        self.changed.emit()

    def _set_type_cell(self, row_idx: int, name: str):
        ing = DB._find_ingredient(name)
        if ing:
            cat = ing.get("category", 8000)
            label_text = CATEGORY_NAMES.get(cat, "Unknown")
            color = CATEGORY_COLORS.get(cat, C["text2"])
            has_cea = bool(ing.get("cea_formula", "").strip())
        else:
            label_text = "Unknown"
            color = C["text3"]
            has_cea = False
        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            f"color:{color}; font-family:Consolas,monospace; font-size:10px; "
            f"font-weight:700; padding:0 4px;"
        )
        if not has_cea:
            lbl.setToolTip("No CEA formula a this ingredient will be weight-tracked only.")
        self.table.setCellWidget(row_idx, self.COL_TYPE, lbl)

    def _set_func_cell(self, row_idx: int, name: str, override: Optional[str] = None):
        """Functional group dropdown a shows DB default, allows override."""
        ing = DB._find_ingredient(name)
        db_fg = ing.get("functional_group", "") if ing else ""
        cmb = QComboBox()
        cmb.addItems(["(DB default)", "OH", "NCO", "EPOXIDE", "Other", "(none)"])
        if override:
            idx = cmb.findText(override)
            cmb.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            cmb.setCurrentIndex(0)
        cmb.setToolTip(
            f"Database functional group: {db_fg or 'none'}\n"
            f"Select a different option to override for cure calc."
        )
        cmb.currentIndexChanged.connect(lambda _, ri=row_idx: self._on_func_changed(ri))
        self.table.setCellWidget(row_idx, self.COL_FUNC, cmb)

    def _set_weq_cell(self, row_idx: int, name: str, override=None):
        """Weq spinbox a pre-filled from DB, editable as override."""
        ing = DB._find_ingredient(name)
        db_weq = float(ing.get("Weq", 0.0)) if ing else 0.0
        cat    = int(ing.get("category", 8000)) if ing else 8000
        relevant = cat in (3000, 4000, 8000, 9000)
        func_cmb = self.table.cellWidget(row_idx, self.COL_FUNC)
        func_sel = func_cmb.currentText() if isinstance(func_cmb, QComboBox) else "(DB default)"
        override_active = func_sel in ("OH", "NCO", "EPOXIDE", "Other")
        none_selected = func_sel == "(none)"
        value = 0.0 if none_selected else (override if (override_active and override) else db_weq)
        spn = _dspin(0.0, 99999.0, value, 2, 1.0, " g/eq")
        spn.setEnabled(relevant and override_active)
        if not relevant:
            spn.setToolTip("Weq not applicable for this ingredient type.")
        elif none_selected:
            spn.setToolTip("No functional group selected - Weq is unused.")
        elif override_active:
            spn.setToolTip(
                f"DB Weq = {db_weq:.2f} g/eq. Edit only when overriding the functional group."
            )
        else:
            spn.setToolTip(
                f"Using database Weq = {db_weq:.2f} g/eq. Choose another functional group to edit."
            )
        spn.valueChanged.connect(lambda _, ri=row_idx: self._on_row_changed(ri))
        self.table.setCellWidget(row_idx, self.COL_WEQ, spn)

    def _choose_row_name(self, row_idx: int):
        """Choose a new ingredient for the row through the popup browser."""
        if not (0 <= row_idx < len(self._rows)):
            return
        current_name = self._rows[row_idx].name
        name = self._pick_ingredient_name(current_name, "Select Ingredient")
        if not name or name == current_name:
            return
        if 0 <= row_idx < len(self._rows):
            self._rows[row_idx].name = name
            self._rows[row_idx].func_override = None
            self._rows[row_idx].weq_override = None
        btn = self.table.cellWidget(row_idx, self.COL_NAME)
        if isinstance(btn, QPushButton):
            btn.setText(name)
            btn.setToolTip(f"Click to choose a different ingredient.\nCurrent: {name}")
        self._set_type_cell(row_idx, name)
        self._set_func_cell(row_idx, name)
        self._set_weq_cell(row_idx, name, None)
        # Re-check CEA availability
        chk = self.table.cellWidget(row_idx, self.COL_INCLUDE)
        if isinstance(chk, QCheckBox):
            ing = DB._find_ingredient(name)
            has_cea = bool(ing and ing.get("cea_formula", "").strip())
            chk.setEnabled(has_cea)
            if not has_cea:
                chk.setChecked(False)
        self.changed.emit()

    def _on_func_changed(self, row_idx: int):
        """Update Weq behavior when the functional-group override changes."""
        func_w = self.table.cellWidget(row_idx, self.COL_FUNC)
        weq_w  = self.table.cellWidget(row_idx, self.COL_WEQ)
        if not (0 <= row_idx < len(self._rows)):
            return
        name = self._rows[row_idx].name
        override = None
        if isinstance(weq_w, QDoubleSpinBox) and weq_w.isEnabled():
            override = weq_w.value() if weq_w.value() > 0 else None
        if 0 <= row_idx < len(self._rows):
            self._rows[row_idx].func_override = (
                func_w.currentText()
                if isinstance(func_w, QComboBox) and func_w.currentIndex() > 0
                else None
            )
        self._set_weq_cell(row_idx, name, override)
        self.changed.emit()

    def _sync_row_from_widgets(self, row_idx: int):
        """Persist the current widget state back into the row model."""
        if not (0 <= row_idx < len(self._rows)):
            return
        chk = self.table.cellWidget(row_idx, self.COL_INCLUDE)
        spn = self.table.cellWidget(row_idx, self.COL_PCT)
        func_w = self.table.cellWidget(row_idx, self.COL_FUNC)
        weq_w = self.table.cellWidget(row_idx, self.COL_WEQ)

        if isinstance(chk, QCheckBox):
            self._rows[row_idx].include_cea = chk.isChecked()
        if isinstance(spn, QDoubleSpinBox):
            spn.interpretText()
            self._rows[row_idx].wt_pct = spn.value()
        if isinstance(func_w, QComboBox) and func_w.currentIndex() > 0:
            self._rows[row_idx].func_override = func_w.currentText()
        else:
            self._rows[row_idx].func_override = None
        if isinstance(weq_w, QDoubleSpinBox) and weq_w.isEnabled():
            weq_w.interpretText()
            self._rows[row_idx].weq_override = weq_w.value() if weq_w.value() > 0.0 else None
        else:
            self._rows[row_idx].weq_override = None

    def _on_row_changed(self, row_idx: int):
        if not self._refreshing:
            self._sync_row_from_widgets(row_idx)
            self.changed.emit()

    def get_effective_func_group(self, row_idx: int, db_name: str) -> str:
        """
        Return the effective functional group for a row.
        If the user selected an override in the dropdown, use that.
        Otherwise fall back to the database value.
        """
        cmb = self.table.cellWidget(row_idx, self.COL_FUNC)
        if isinstance(cmb, QComboBox) and cmb.currentIndex() > 0:
            sel = cmb.currentText()
            if sel not in ("(DB default)", "(none)"):
                return sel
            if sel == "(none)":
                return ""
        ing = DB._find_ingredient(db_name)
        return ing.get("functional_group", "") if ing else ""
