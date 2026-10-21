"""Colour tokens, Qt stylesheet, matplotlib defaults and category metadata."""

import matplotlib

matplotlib.use("QtAgg")
import matplotlib.pyplot as plt  # noqa: E402
from PyQt6.QtGui import QColor, QPalette  # noqa: E402

# =============================================================================
#  DESIGN TOKENS  (all colour/spacing decisions live here)
# =============================================================================
C = {
    "bg0":      "#090c10",
    "bg1":      "#0d1117",
    "bg2":      "#13181f",
    "bg3":      "#1c2330",
    "border":   "#21262d",
    "border2":  "#30363d",
    "amber":    "#e8a020",
    "amber_d":  "#b87a10",
    "amber_bg": "#1f1500",
    "blue":     "#58a6ff",
    "green":    "#3fb950",
    "red":      "#f85149",
    "text0":    "#f0f6fc",   # brightest - primary values
    "text1":    "#c9d1d9",   # body text
    "text2":    "#8b949e",   # labels / muted
    "text3":    "#6e7681",   # very muted (was #484f58, brightened for readability)
}

STYLE = f"""
QWidget {{
    background-color: {C['bg1']};
    color: {C['text1']};
    font-family: "Segoe UI", "SF Pro Display", sans-serif;
    font-size: 13px;
}}
QMainWindow  {{ background-color: {C['bg0']}; }}
QDialog      {{ background-color: {C['bg1']}; }}
QMenuBar     {{ background-color: {C['bg0']}; color: {C['text2']}; border-bottom: 1px solid {C['border']}; }}
QMenuBar::item:selected {{ background: {C['bg3']}; color: {C['text0']}; }}
QMenu        {{ background-color: {C['bg2']}; border: 1px solid {C['border2']}; color: {C['text1']}; }}
QMenu::item:selected {{ background: {C['amber_bg']}; color: {C['amber']}; }}
QScrollArea  {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: {C['bg1']}; width: 6px; border: none; }}
QScrollBar::handle:vertical {{ background: {C['border2']}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
    background: {C['bg2']}; border: 1px solid {C['border2']}; border-radius: 5px;
    padding: 5px 8px; color: {C['text0']};
    font-family: "Consolas", "Courier New", monospace; font-size: 12px;
}}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {C['amber']}; background: #141a0e;
}}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {{
    background: {C['bg3']}; border: none; width: 16px;
}}
QComboBox::drop-down {{ border: none; width: 20px; background: transparent; }}
QComboBox QAbstractItemView {{
    background: {C['bg2']}; border: 1px solid {C['border2']};
    selection-background-color: {C['amber_bg']}; color: {C['text0']};
}}
QPushButton {{
    background: {C['bg3']}; border: 1px solid {C['border2']}; border-radius: 5px;
    padding: 6px 14px; color: {C['text1']}; font-size: 12px;
}}
QPushButton:hover  {{ background: {C['border2']}; color: {C['text0']}; }}
QPushButton:pressed {{ background: {C['bg2']}; }}
QPushButton#run_btn {{
    background: {C['amber']}; color: {C['bg0']}; font-weight: 700;
    font-size: 13px; border: none; padding: 10px 20px;
    border-radius: 6px; letter-spacing: 1px;
}}
QPushButton#run_btn:hover {{ background: #f0b030; }}
QPushButton#run_btn:disabled {{ background: {C['bg3']}; color: {C['text3']}; }}
QPushButton#small_btn {{
    background: {C['bg2']}; border: 1px solid {C['border']}; padding: 3px 8px;
    font-size: 11px; color: {C['text2']}; border-radius: 4px;
}}
QPushButton#small_btn:hover {{ color: {C['text0']}; border-color: {C['border2']}; }}
QPushButton#danger_btn {{
    background: #2d0b0b; border: 1px solid #6e1a1a; padding: 3px 8px;
    font-size: 11px; color: {C['red']}; border-radius: 4px;
}}
QPushButton#danger_btn:hover {{ background: #3d1010; }}
QCheckBox, QRadioButton {{ color: {C['text2']}; spacing: 6px; font-size: 12px; }}
QCheckBox:checked, QRadioButton:checked {{ color: {C['text0']}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px; background: {C['bg2']};
    border: 1px solid {C['border2']}; border-radius: 3px;
}}
QRadioButton::indicator {{ border-radius: 7px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {C['amber']}; border-color: {C['amber']};
}}
QGroupBox {{
    border: 1px solid {C['border']}; border-radius: 7px; margin-top: 18px;
    padding: 12px 10px 8px 10px; background: {C['bg1']};
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 10px; top: 2px; color: {C['amber']};
    font-size: 10px; font-weight: 700; letter-spacing: 2px;
    font-family: "Consolas", monospace;
}}
QTabWidget::pane {{
    border: 1px solid {C['border']}; border-radius: 0 7px 7px 7px; background: {C['bg1']};
}}
QTabBar::tab {{
    background: {C['bg0']}; color: {C['text3']}; border: 1px solid {C['border']};
    border-bottom: none; padding: 7px 18px; margin-right: 2px;
    border-radius: 5px 5px 0 0; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
}}
QTabBar::tab:selected  {{ background: {C['bg1']}; color: {C['amber']}; border-bottom-color: {C['bg1']}; }}
QTabBar::tab:hover:!selected {{ color: {C['text2']}; }}
QTextEdit {{
    background: {C['bg0']}; color: {C['text2']};
    font-family: "Consolas", "Courier New", monospace; font-size: 11px;
    border: 1px solid {C['border']}; border-radius: 5px; padding: 8px;
}}
QTableWidget {{
    background: {C['bg0']}; border: 1px solid {C['border']}; gridline-color: {C['border']};
    color: {C['text1']}; font-family: "Consolas", monospace; font-size: 11px;
}}
QTableWidget::item:selected {{ background: {C['amber_bg']}; color: {C['amber']}; }}
QHeaderView::section {{
    background: {C['bg2']}; color: {C['text2']}; border: none;
    border-bottom: 1px solid {C['border2']}; border-right: 1px solid {C['border']};
    padding: 4px 6px; font-size: 10px; font-weight: 700; letter-spacing: 1px;
    font-family: "Consolas", monospace;
}}
QSplitter::handle {{ background: {C['border']}; width: 1px; }}
QStatusBar {{
    background: {C['bg0']}; color: {C['text3']}; font-size: 11px;
    font-family: "Consolas", monospace; border-top: 1px solid {C['border']};
}}
QDialogButtonBox QPushButton {{ min-width: 80px; }}
"""

plt.rcParams.update({
    "figure.facecolor":  C["bg1"],
    "axes.facecolor":    C["bg0"],
    "axes.edgecolor":    C["border2"],
    "axes.labelcolor":   C["text2"],
    "axes.grid":         True,
    "grid.color":        C["border"],
    "grid.linewidth":    0.6,
    "xtick.color":       C["text3"],
    "ytick.color":       C["text3"],
    "text.color":        C["text1"],
    "lines.linewidth":   2.0,
    "font.family":       "monospace",
    "font.size":         10,
    "legend.fontsize":   9,
    "legend.framealpha": 0.2,
    "legend.edgecolor":  C["border2"],
})

# Category display names
CATEGORY_NAMES = {
    1000: "Oxidizer",
    2000: "Metal Fuel",
    3000: "Binder",
    4000: "Curative",
    5000: "Burn Rate Catalyst",
    6000: "Burn Rate Suppressant",
    7000: "Plasticizer",
    8000: "Misc / Additive",
    9000: "Energetic Additive",
}

CATEGORY_COLORS = {
    1000: C["blue"],
    2000: "#c0a060",
    3000: "#7ec07e",
    4000: "#c07ec0",
    5000: C["amber"],
    6000: "#60b0c0",
    7000: "#c0c060",
    8000: C["text2"],
    9000: C["red"],
}


def apply_theme(app) -> None:
    """Apply the dark theme to a QApplication."""
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(C["bg1"]))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(C["text1"]))
    pal.setColor(QPalette.ColorRole.Base,            QColor(C["bg2"]))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(C["bg3"]))
    pal.setColor(QPalette.ColorRole.Text,            QColor(C["text0"]))
    pal.setColor(QPalette.ColorRole.Button,          QColor(C["bg3"]))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(C["text1"]))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(C["amber"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(C["bg0"]))
    app.setPalette(pal)
