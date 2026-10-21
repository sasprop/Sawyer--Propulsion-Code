"""Small shared widgets and helpers used across the input panel and tabs."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDoubleSpinBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from propellant_analyzer.theme import C


def sep_line() -> QFrame:
    """Thin horizontal separator line."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color: {C['border']}; margin: 2px 0;")
    return f


def badge_label(text: str, kind: str = "amber") -> QLabel:
    """Colour-coded pill label for status badges."""
    colors = {
        "amber": (C["amber_bg"], C["amber"],  "#5a3800"),
        "green": ("#0d2818",     C["green"],  "#1a4731"),
        "red":   ("#2d0b0b",     C["red"],    "#6e1a1a"),
        "blue":  ("#0d1a2d",     C["blue"],   "#1a3a6e"),
        "grey":  (C["bg2"],      C["text3"],  C["border"]),
    }
    bg, fg, border = colors.get(kind, colors["amber"])
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background:{bg}; color:{fg}; border:1px solid {border}; "
        f"border-radius:3px; padding:1px 6px; "
        f"font-size:10px; font-weight:700; font-family:Consolas,monospace;"
    )
    lbl.setFixedHeight(18)
    return lbl


def mono_label(text: str, color: str = None, size: int = 11) -> QLabel:
    """Monospace label helper."""
    lbl = QLabel(text)
    col = color or C["text2"]
    lbl.setStyleSheet(
        f"color:{col}; font-family:Consolas,monospace; font-size:{size}px;"
    )
    return lbl


class MetricCard(QFrame):
    """
    Key-result display card. Uses a left amber accent bar instead of a
    border-top, which was rendering as an ugly thick orange stripe across
    the whole label area at small heights.
    """
    def __init__(self, label: str):
        super().__init__()
        # Outer frame a subtle border, no border-top bar
        self.setStyleSheet(
            f"QFrame {{ background:{C['bg2']}; border:1px solid {C['border2']}; "
            f"border-radius:6px; }}"
        )
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left amber accent bar (3 px wide coloured widget)
        accent = QFrame()
        accent.setFixedWidth(3)
        accent.setStyleSheet(
            f"background:{C['amber']}; border:none; border-radius:3px 0 0 3px;"
        )
        outer.addWidget(accent)

        # Content
        content = QWidget()
        content.setStyleSheet("background:transparent; border:none;")
        lay = QVBoxLayout(content)
        lay.setSpacing(3)
        lay.setContentsMargins(10, 8, 10, 8)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(
            f"color:{C['text2']}; font-size:10px; font-weight:700; "
            f"letter-spacing:1.5px; font-family:Consolas,monospace;"
        )
        self._val = QLabel("-")
        self._val.setStyleSheet(
            f"color:{C['amber']}; font-family:Consolas,monospace; "
            f"font-size:24px; font-weight:700;"
        )
        self._sub = QLabel("")
        self._sub.setStyleSheet(
            f"color:{C['text3']}; font-size:10px; font-family:Consolas,monospace;"
        )
        for w in [self._lbl, self._val, self._sub]:
            lay.addWidget(w)

        outer.addWidget(content)

    def update(self, value: str, sub: str = ""):
        self._val.setText(value)
        self._sub.setText(sub)


class DataRow(QWidget):
    """Label : value row with optional status badge."""
    def __init__(self, label: str, min_label_width: int = 230):
        super().__init__()
        self.setMinimumHeight(24)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"color:{C['text2']}; font-family:Consolas,monospace; font-size:11px;"
        )
        self._lbl.setMinimumWidth(min_label_width)

        self.val = QLabel("-")
        self.val.setStyleSheet(
            f"color:{C['text0']}; font-family:Consolas,monospace; "
            f"font-size:12px; font-weight:600;"
        )
        self.val.setWordWrap(True)
        self.val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        lay.addWidget(self._lbl)
        lay.addWidget(self.val)
        lay.addStretch()
        self._badge: Optional[QLabel] = None

    def set(self, value: str, badge_text: str = "", badge_kind: str = "amber"):
        self.val.setText(value)
        if self._badge:
            self._badge.deleteLater()
            self._badge = None
        if badge_text:
            self._badge = badge_label(badge_text, badge_kind)
            self.layout().insertWidget(2, self._badge)

    def recolor(self, hex_color: str):
        """Override the value label colour."""
        self.val.setStyleSheet(
            f"color:{hex_color}; font-family:Consolas,monospace; "
            f"font-size:12px; font-weight:700;"
        )


class SectionCard(QGroupBox):
    """GroupBox with amber title and a VBox layout inside."""
    def __init__(self, title: str):
        super().__init__(title)
        self.lay = QVBoxLayout(self)
        self.lay.setSpacing(1)
        self.lay.setContentsMargins(6, 8, 6, 6)

    def add(self, widget: QWidget):
        self.lay.addWidget(widget)

    def add_layout(self, layout):
        self.lay.addLayout(layout)


def _dspin(lo, hi, val, dec, step, suffix="") -> QDoubleSpinBox:
    """Factory for a QDoubleSpinBox with common settings."""
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(max(int(dec), 6))
    s.setSingleStep(step)
    s.setKeyboardTracking(False)
    s.setValue(val)
    if suffix:
        s.setSuffix(suffix)
    line_edit = s.lineEdit()
    if line_edit is not None:
        line_edit.editingFinished.connect(s.interpretText)
    return s
