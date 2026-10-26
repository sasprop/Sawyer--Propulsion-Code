"""Main window: menu bar, input sidebar, result tabs and status bar."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog, QMainWindow, QMessageBox, QPushButton, QSplitter, QStatusBar,
    QTabWidget,
)

from propellant_analyzer import APP_NAME, __version__
from propellant_analyzer.cea_engine import CeaWorker
from propellant_analyzer.config import read_config, write_config
from propellant_analyzer.ingredients_ui import AddIngredientDialog
from propellant_analyzer.input_panel import InputPanel
from propellant_analyzer.paths import CONFIG_DIR
from propellant_analyzer.run_history import RunHistory, record_from_result
from propellant_analyzer.tabs.charts import ChartsTab
from propellant_analyzer.tabs.chemistry import ChemistryTab
from propellant_analyzer.tabs.flame_color import FlameColorTab
from propellant_analyzer.tabs.performance import PerformanceTab
from propellant_analyzer.tabs.raw_output import CeaOutputTab
from propellant_analyzer.tabs.wiki import WikiTab

RUN_LABEL = ">   RUN ANALYSIS"
CONFIG_FILTER = "CEA Config (*.ceacfg);;All files (*)"
PROP_FILTER = "Propellant Config (*.propcfg);;JSON (*.json);;All files (*)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}  //  RocketCEA")
        self.resize(1500, 900)
        self.setMinimumSize(1100, 680)

        self._worker: Optional[CeaWorker] = None
        self._overlay_workers: list[CeaWorker] = []
        self._last_result: Optional[dict] = None
        self.history = RunHistory()
        self._build_menu()
        self._build_central()
        self._build_statusbar()

    # -- Layout ---------------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        actions = [
            ("New Config", "Ctrl+N", self._new_config),
            ("Load Config...", "Ctrl+O", self._load_config),
            ("Save Config...", "Ctrl+S", self._save_config),
            None,
            ("Load Propellant Config...", None, self._load_propellant_config),
            ("Save Propellant Config...", None, self._save_propellant_config),
            None,
            ("Quit", "Ctrl+Q", self.close),
        ]
        for spec in actions:
            if spec is None:
                file_menu.addSeparator()
                continue
            text, shortcut, slot = spec
            act = QAction(text, self)
            if shortcut:
                act.setShortcut(shortcut)
            act.triggered.connect(slot)
            file_menu.addAction(act)

        run_menu = mb.addMenu("Run")
        act_run = QAction("Run Analysis", self)
        act_run.setShortcut("Ctrl+R")
        act_run.triggered.connect(self._run)
        run_menu.addAction(act_run)

        db_menu = mb.addMenu("Database")
        act_add_ing = QAction("Add New Ingredient...", self)
        act_add_ing.triggered.connect(self._open_add_ingredient)
        db_menu.addAction(act_add_ing)

        view_menu = mb.addMenu("View")
        self.act_toggle_sidebar = QAction("Hide Sidebar", self)
        self.act_toggle_sidebar.setShortcut("Ctrl+B")
        self.act_toggle_sidebar.triggered.connect(self._toggle_sidebar)
        view_menu.addAction(self.act_toggle_sidebar)

        help_menu = mb.addMenu("Help")
        act_about = QAction(f"About {APP_NAME}", self)
        act_about.triggered.connect(self._about)
        help_menu.addAction(act_about)

    def _build_central(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.splitter = splitter
        self._sidebar_visible = True
        self._sidebar_last_sizes = [700, 900]

        self.inputs = InputPanel()
        splitter.addWidget(self.inputs)

        self.tabs = QTabWidget()
        self.tab_perf = PerformanceTab()
        self.tab_chart = ChartsTab(self.history)
        self.tab_chem = ChemistryTab()
        self.tab_flame = FlameColorTab()
        self.tab_wiki = WikiTab()
        self.tab_cea = CeaOutputTab()
        for tab, name in [
            (self.tab_perf, "PERFORMANCE"),
            (self.tab_chart, "ISP CHART"),
            (self.tab_chem, "CHEMISTRY"),
            (self.tab_flame, "FLAME COLOR"),
            (self.tab_wiki, "WIKI"),
            (self.tab_cea, "RAW CEA OUTPUT"),
        ]:
            self.tabs.addTab(tab, name)

        splitter.addWidget(self.tabs)
        splitter.setCollapsible(0, True)
        splitter.setSizes(self._sidebar_last_sizes)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self.inputs.btn_run.clicked.connect(self._run)
        self.tab_chart.add_config_requested.connect(self._add_config_overlay)
        self.inputs.preview_changed.connect(self._refresh_wiki)
        self._refresh_wiki()

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.btn_toggle_sidebar = QPushButton("Hide Sidebar")
        self.btn_toggle_sidebar.setObjectName("small_btn")
        self.btn_toggle_sidebar.clicked.connect(self._toggle_sidebar)
        self.status.addPermanentWidget(self.btn_toggle_sidebar)
        self.status.showMessage("Ready - configure ingredients and press > RUN ANALYSIS")

    # -- View ------------------------------------------------------------------

    def _toggle_sidebar(self):
        sizes = self.splitter.sizes()
        if self._sidebar_visible and sizes[0] > 0:
            self._sidebar_last_sizes = sizes
            self.inputs.hide()
            self.splitter.setSizes([0, sum(sizes)])
            self._sidebar_visible = False
            label = "Show Sidebar"
        else:
            restore = self._sidebar_last_sizes if self._sidebar_last_sizes[0] > 0 else [700, 900]
            self.inputs.show()
            self.splitter.setSizes(restore)
            self._sidebar_visible = True
            label = "Hide Sidebar"
        self.btn_toggle_sidebar.setText(label)
        self.act_toggle_sidebar.setText(label)

    def _refresh_wiki(self, *_args):
        self.tab_wiki.update_content(self.inputs.get_config(), self._last_result)

    def _about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> v{__version__}<br><br>"
            "Solid-propellant formulation, performance, chemistry and flame-colour "
            "screening built on NASA CEA via RocketCEA.",
        )

    # -- Config files ------------------------------------------------------------

    def _clear_results(self):
        self._last_result = None
        self._refresh_wiki()

    def _new_config(self):
        ret = QMessageBox.question(
            self, "New Config", "Clear all inputs and start a new config?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.inputs.load_config({})
            self._clear_results()

    def _ask_open(self, title: str, filt: str) -> str:
        path, _ = QFileDialog.getOpenFileName(self, title, str(CONFIG_DIR), filt)
        return path

    def _ask_save(self, title: str, filt: str, exts: tuple[str, ...]) -> str:
        name = self.inputs.txt_formula_name.text().strip() or "config"
        start = os.path.join(str(CONFIG_DIR), name + exts[0])
        path, _ = QFileDialog.getSaveFileName(self, title, start, filt)
        if path and not path.lower().endswith(exts):
            path += exts[0]
        return path

    def _load_config(self):
        path = self._ask_open("Load Config", CONFIG_FILTER)
        if not path:
            return
        try:
            self.inputs.load_config(read_config(path))
            self._clear_results()
            self.status.showMessage(f"Config loaded: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load config:\n{e}")

    def _save_config(self):
        path = self._ask_save("Save Config", CONFIG_FILTER, (".ceacfg",))
        if not path:
            return
        try:
            write_config(path, self.inputs.get_config())
            self.status.showMessage(f"Config saved: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save config:\n{e}")

    def _load_propellant_config(self):
        path = self._ask_open("Load Propellant Config", PROP_FILTER)
        if not path:
            return
        try:
            self.inputs.load_propellant_config(read_config(path))
            self._clear_results()
            self.status.showMessage(f"Propellant config loaded: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load propellant config:\n{e}")

    def _save_propellant_config(self):
        path = self._ask_save("Save Propellant Config", PROP_FILTER, (".propcfg", ".json"))
        if not path:
            return
        try:
            write_config(path, self.inputs.get_propellant_config())
            self.status.showMessage(f"Propellant config saved: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save propellant config:\n{e}")

    # -- Ingredient database -----------------------------------------------------

    def _open_add_ingredient(self):
        dlg = AddIngredientDialog(self)
        dlg.ingredient_saved.connect(self._on_ingredient_saved)
        dlg.exec()

    def _on_ingredient_saved(self):
        """A new ingredient was saved to the database - refresh every dropdown."""
        self.inputs.ing_table.refresh_names()
        self.inputs.binder_table.refresh_names()
        self.inputs.manual_table.refresh_names()
        self.status.showMessage("Ingredient saved and database refreshed.")

    # -- Analysis ------------------------------------------------------------------

    def _run(self):
        if self._worker is not None and self._worker.isRunning():
            self.status.showMessage("CEA analysis already running...")
            return
        self.inputs.btn_run.setEnabled(False)
        self.inputs.btn_run.setText("RUNNING...")
        self.status.showMessage("Running CEA analysis...")

        self._worker = CeaWorker(self.inputs.get_config())
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._worker.start()

    def _on_done(self, r: dict):
        self.inputs.btn_run.setEnabled(True)
        self.inputs.btn_run.setText(RUN_LABEL)

        self._last_result = r
        record = self.history.add(record_from_result(r))
        self.tab_perf.populate(r)
        self.tab_chart.populate(r, record)
        self.tab_chem.populate(r)
        self.tab_flame.populate(r)
        self.tab_cea.populate(r)
        self._refresh_wiki()

        wt_warn = ""
        if abs(r["total_all_wt"] - 100.0) > 0.1:
            wt_warn = f"  WARNING Total = {r['total_all_wt']:.3f} wt%"
        exc_warn = ""
        if r["excluded_summary"]:
            exc_warn = f"  WARNING {len(r['excluded_summary'])} ingredient(s) excluded from CEA"
        isp_str = f"Isp ideal {r['isp_ideal']:.2f} s  | " if r["isp_ideal"] else ""
        self.status.showMessage(
            f"Done  >  C* {r['cstar']:.1f} ft/s  |  "
            f"Isp vac {r['isp_vac']:.2f} s  |  "
            f"Isp amb {r['isp_amb']:.2f} s  |  "
            f"{isp_str}"
            f"Tc {r['Tc_K']:.0f} K"
            f"{wt_warn}{exc_warn}"
        )

    # -- Overlay a saved config on the chart ------------------------------------------

    def _add_config_overlay(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Overlay saved configs", str(CONFIG_DIR), CONFIG_FILTER)
        for path in paths:
            try:
                cfg = read_config(path)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load {os.path.basename(path)}:\n{e}")
                continue
            if "ingredients" not in cfg:
                continue
            base = {"pc_psia": 1000.0, "eps": 9.0, "pamb": 14.7, "cstar_eff": 1.0, "isp_eff": 1.0}
            base.update(cfg)
            label = os.path.splitext(os.path.basename(path))[0]
            worker = CeaWorker(base)
            worker.finished.connect(lambda r, w=worker, lb=label: self._on_overlay_done(w, r, lb))
            worker.error.connect(lambda msg, w=worker, lb=label: self._on_overlay_err(w, msg, lb))
            self._overlay_workers.append(worker)
            worker.start()
            self.status.showMessage(f"Running {label} for overlay...")

    def _on_overlay_done(self, worker: CeaWorker, r: dict, label: str):
        if worker in self._overlay_workers:
            self._overlay_workers.remove(worker)
        rec = self.history.add(record_from_result(r, source="config", label=f"{label} (config)"))
        self.tab_chart.add_overlay_record(rec)
        self.tabs.setCurrentWidget(self.tab_chart)
        self.status.showMessage(f"Overlay added: {label}  |  Isp vac {r['isp_vac']:.2f} s  |  Tc {r['Tc_K']:.0f} K")

    def _on_overlay_err(self, worker: CeaWorker, msg: str, label: str):
        if worker in self._overlay_workers:
            self._overlay_workers.remove(worker)
        QMessageBox.critical(self, "Overlay Error", f"{label} could not be run:\n\n{msg}")

    def _on_err(self, msg: str):
        self.inputs.btn_run.setEnabled(True)
        self.inputs.btn_run.setText(RUN_LABEL)
        self.status.showMessage(f"ERROR: {msg}")
        QMessageBox.critical(self, "CEA Analysis Error", f"Analysis failed:\n\n{msg}")
