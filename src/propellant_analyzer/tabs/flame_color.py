"""FLAME COLOR tab: likely visible emitters in the exhaust (see flame_color.py)."""

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from propellant_analyzer.theme import C
from propellant_analyzer.widgets import MetricCard, SectionCard, sep_line


class FlameColorTab(QWidget):
    """Screen RocketCEA exit species for likely visible flame-color contributors."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.mc_hue = MetricCard("Likely Hue")
        self.mc_species = MetricCard("Top Emitter")
        self.mc_color_total = MetricCard("Color-Active Exit %")
        self.mc_clarity = MetricCard("Plume Clarity")
        self.mc_score = MetricCard("Visibility Score")
        for card in [self.mc_hue, self.mc_species, self.mc_color_total, self.mc_clarity, self.mc_score]:
            cards.addWidget(card)
        lay.addLayout(cards)

        cols = QHBoxLayout()
        cols.setSpacing(10)

        fam_grp = SectionCard("COLOR FAMILY TOTALS")
        self.family_container = QWidget()
        self.family_lay = QGridLayout(self.family_container)
        self.family_lay.setSpacing(6)
        fam_grp.add(self.family_container)
        cols.addWidget(fam_grp)

        note_grp = SectionCard("INTERPRETATION NOTES")
        self.lbl_summary = QLabel("Run analysis to screen exit species for likely flame-color emitters.")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet(
            f"color:{C['text1']}; font-family:Consolas,monospace; font-size:11px;"
        )
        self.lbl_notes = QLabel(
            "This tab highlights gas-phase and radical emitters from NASA CEA output. "
            "Observed plume color can still be dominated by condensed particles or broadband thermal radiation."
        )
        self.lbl_notes.setWordWrap(True)
        self.lbl_notes.setStyleSheet(
            f"color:{C['text2']}; font-family:Consolas,monospace; font-size:11px;"
        )
        note_grp.add(self.lbl_summary)
        note_grp.add(sep_line())
        note_grp.add(self.lbl_notes)
        cols.addWidget(note_grp)

        lay.addLayout(cols)

        tbl_grp = SectionCard("COLOR-ACTIVE SPECIES")
        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels([
            "Color",
            "Species",
            "Inj %",
            "Chamber %",
            "Throat %",
            "Exit %",
            "Band",
            "Why It Matters",
        ])
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setAlternatingRowColors(False)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        tbl_grp.add(self.tbl)
        lay.addWidget(tbl_grp, 1)

    def _clear_family_grid(self):
        while self.family_lay.count():
            item = self.family_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def populate(self, r: dict):
        flame = r.get("flame_analysis", {})
        contributors = flame.get("contributors", [])
        family_rows = flame.get("family_rows", [])

        self.mc_hue.update(flame.get("dominant_family") or "-", "heuristic dominant family")
        top_species = flame.get("strongest_species")
        top_sub = (f"{flame.get('strongest_exit_pct', 0.0):.4f} mol% at exit"
                   if top_species else "")
        self.mc_species.update(top_species or "-", top_sub)
        self.mc_color_total.update(f"{flame.get('visible_exit_total_pct', 0.0):.4f}", "sum of mapped exit emitters")
        self.mc_clarity.update(
            f"{flame.get('plume_clarity', 1.0):.3f}",
            (
                f"{flame.get('plume_obscuration', 'Minimal')} obscuration  |  "
                f"Al2O3 products {flame.get('alumina_smoke_exit_pct', 0.0):.4f} mol% exit"
            ),
        )
        self.mc_score.update(
            f"{flame.get('dominant_score', 0.0):.4f}" if family_rows else "-",
            "weighted score after alumina smoke penalty",
        )

        self.lbl_summary.setText(flame.get("summary") or "No flame-color analysis data.")
        self.lbl_notes.setText("\n".join(flame.get("notes", [])))

        self._clear_family_grid()
        if family_rows:
            for idx, row in enumerate(family_rows):
                cell = QFrame()
                cell.setStyleSheet(
                    f"QFrame {{background:{C['bg0']}; border:1px solid {C['border']}; "
                    f"border-radius:5px; padding:2px;}}"
                )
                cl = QVBoxLayout(cell)
                cl.setContentsMargins(8, 6, 8, 6)
                cl.setSpacing(2)

                fam = QLabel(row["family"])
                fam.setStyleSheet(
                    f"color:{row['hex']}; font-family:Consolas,monospace; "
                    f"font-size:12px; font-weight:700;"
                )
                pct = QLabel(f"{row['exit_pct']:.4f} mol% exit")
                pct.setStyleSheet(
                    f"color:{C['text1']}; font-family:Consolas,monospace; font-size:11px;"
                )
                score = QLabel(f"score {row['score']:.4f}  (raw {row['raw_score']:.4f})")
                score.setStyleSheet(
                    f"color:{C['text3']}; font-family:Consolas,monospace; font-size:10px;"
                )
                cl.addWidget(fam)
                cl.addWidget(pct)
                cl.addWidget(score)
                self.family_lay.addWidget(cell, idx // 3, idx % 3)
        else:
            msg = QLabel("No mapped color families found in the current exit-composition screen.")
            msg.setWordWrap(True)
            msg.setStyleSheet(
                f"color:{C['text3']}; font-family:Consolas,monospace; font-size:11px;"
            )
            self.family_lay.addWidget(msg, 0, 0)

        self.tbl.setRowCount(len(contributors))
        for row_idx, item in enumerate(contributors):
            values = [
                item["family"],
                item["species_display"],
                f"{item['inj_pct']:.6f}",
                f"{item['chm_pct']:.6f}",
                f"{item['tht_pct']:.6f}",
                f"{item['exit_pct']:.6f}",
                item["strength"],
                f"{item['label']}: {item['wavelength']}. {item['note']}",
            ]
            for col_idx, value in enumerate(values):
                qitem = QTableWidgetItem(value)
                if col_idx == 0:
                    qitem.setForeground(QColor(item["family_hex"]))
                self.tbl.setItem(row_idx, col_idx, qitem)
        self.tbl.resizeRowsToContents()
