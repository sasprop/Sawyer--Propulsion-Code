"""CHEMISTRY tab: oxygen balance and atom inventory."""

from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from propellant_analyzer.theme import C
from propellant_analyzer.widgets import DataRow, SectionCard


class ChemistryTab(QWidget):
    """Oxygen balance + atom inventory display."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        cols = QHBoxLayout()
        cols.setSpacing(10)

        ob = SectionCard("OXYGEN BALANCE")
        self.dr_avail  = DataRow("Oxygen available")
        self.dr_o_al   = DataRow("Oxygen consumed  (Al -> Al2O3)")
        self.dr_o_c    = DataRow("Oxygen consumed  (C -> CO)")
        self.dr_o_bal  = DataRow("Oxygen balance")
        self.dr_status = DataRow("Status")
        for dr in [self.dr_avail, self.dr_o_al, self.dr_o_c,
                   self.dr_o_bal, self.dr_status]:
            ob.add(dr)
        cols.addWidget(ob)

        atom_grp = SectionCard("ATOM INVENTORY  (mol / 100g, CEA ingredients)")
        self.atom_container = QWidget()
        self.atom_lay       = QGridLayout(self.atom_container)
        self.atom_lay.setSpacing(4)
        atom_grp.add(self.atom_container)
        cols.addWidget(atom_grp)

        lay.addLayout(cols)
        lay.addStretch()

    def populate(self, r: dict):
        ob = r["ob"]
        self.dr_avail.set(f"{ob['o_available']:.6f} mol/100g")
        self.dr_o_al.set(f"{ob['o_for_al2o3']:.6f} mol/100g")
        self.dr_o_c.set(f"{ob['o_for_co']:.6f} mol/100g")
        self.dr_o_bal.set(f"{ob['o_remaining']:+.6f} mol/100g")
        status = ob["balance_status"]
        status_colors = {
            "Oxygen Excess":   C["amber"],
            "Oxygen Deficit":  C["red"],
            "Stoichiometric":  C["green"],
        }
        self.dr_status.set(status)
        self.dr_status.recolor(status_colors.get(status, C["text0"]))

        # Rebuild atom grid
        while self.atom_lay.count():
            item = self.atom_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, (el, moles) in enumerate(sorted(r["atoms"].items())):
            cell = QFrame()
            cell.setStyleSheet(
                f"QFrame {{background:{C['bg0']}; border:1px solid {C['border']}; "
                f"border-radius:5px; padding:1px;}}"
            )
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(8, 3, 8, 3)
            cl.setSpacing(10)
            sym = QLabel(el)
            sym.setStyleSheet(
                f"color:{C['blue']}; font-family:Consolas,monospace; "
                f"font-weight:700; font-size:13px;"
            )
            val = QLabel(f"{moles:.5f}")
            val.setStyleSheet(
                f"color:{C['text2']}; font-family:Consolas,monospace; font-size:11px;"
            )
            cl.addWidget(sym)
            cl.addWidget(val)
            self.atom_lay.addWidget(cell, idx // 3, idx % 3)
