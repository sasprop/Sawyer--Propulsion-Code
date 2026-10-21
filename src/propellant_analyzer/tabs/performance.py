"""PERFORMANCE tab: c*, Isp, nozzle expansion state and key propellant properties."""

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from propellant_analyzer.theme import C
from propellant_analyzer.widgets import DataRow, MetricCard, SectionCard


class PerformanceTab(QWidget):
    """Performance metrics: key results + nozzle analysis + propellant properties."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        # -- Metric cards ---------------------------------------------------
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.mc_cstar     = MetricCard("C*  (ft/s)")
        self.mc_isp_vac   = MetricCard("Isp Vacuum  (s)")
        self.mc_isp_amb   = MetricCard("Isp Ambient  (s)")
        self.mc_isp_ideal = MetricCard("Isp Ideal Exp  (s)")
        for mc in [self.mc_cstar, self.mc_isp_vac, self.mc_isp_amb, self.mc_isp_ideal]:
            cards.addWidget(mc)
        lay.addLayout(cards)

        # -- Two-column: nozzle + propellant properties ---------------------
        cols = QHBoxLayout()
        cols.setSpacing(10)

        noz = SectionCard("NOZZLE EXPANSION ANALYSIS")
        self.dr_eps_ideal  = DataRow("Ideal expansion ratio")
        self.dr_eps_config = DataRow("Config expansion ratio")
        self.dr_pe         = DataRow("Exit pressure  (Pe)")
        self.dr_pamb_r     = DataRow("Ambient pressure")
        self.dr_sep        = DataRow("Flow separation (0.4xPamb)")
        for dr in [self.dr_eps_ideal, self.dr_eps_config, self.dr_pe,
                   self.dr_pamb_r, self.dr_sep]:
            noz.add(dr)
        cols.addWidget(noz)

        ch = SectionCard("IMPORTANT PROPELLANT PROPERTIES")
        self.dr_tc      = DataRow("Chamber temperature  (Tc)")
        self.dr_tt      = DataRow("Throat temperature   (Tt)")
        self.dr_te      = DataRow("Exit temperature     (Te)")
        self.dr_gamma   = DataRow("Chamber gamma")
        self.dr_mw      = DataRow("Exit molar mass")
        self.dr_density = DataRow("Reactant density")
        for dr in [self.dr_tc, self.dr_tt, self.dr_te, self.dr_gamma,
                   self.dr_mw, self.dr_density]:
            ch.add(dr)
        cols.addWidget(ch)
        lay.addLayout(cols)

        # -- CEA exclusion note ---------------------------------------------
        self.lbl_excluded = QLabel("")
        self.lbl_excluded.setStyleSheet(
            f"color:{C['amber']}; font-family:Consolas,monospace; font-size:11px;"
        )
        self.lbl_excluded.setWordWrap(True)
        lay.addWidget(self.lbl_excluded)
        lay.addStretch()

    def populate(self, r: dict):
        eff = r["cfg"]["isp_eff"]
        sub_cstar = (f"theoretical: {r['cstar_th']:.1f} ft/s"
                     if r["cfg"]["cstar_eff"] != 1.0 else "")
        self.mc_cstar.update(f"{r['cstar']:.1f}", sub_cstar)
        self.mc_isp_vac.update(f"{r['isp_vac']:.2f}",
                               f"th: {r['isp_vac_th']:.2f}" if eff != 1.0 else "")
        self.mc_isp_amb.update(f"{r['isp_amb']:.2f}", r["mode"])
        self.mc_isp_ideal.update(
            f"{r['isp_ideal']:.2f}" if r["isp_ideal"] else "N/A",
            f"at eps = {r['eps_ideal_val']:.3f}" if r["eps_ideal_val"] else "",
        )

        # Nozzle rows
        if r["eps_ideal_val"]:
            self.dr_eps_ideal.set(
                f"{r['eps_ideal_val']:.3f}  (Me = {r['Me_ideal']:.3f})"
            )
        cfg_eps = r.get("eps_used", r["cfg"]["eps"])
        if r["eps_ideal_val"]:
            ideal_diff = abs(cfg_eps - r["eps_ideal_val"])
            if ideal_diff < 0.01:
                kind, state = "green", "IDEAL"
            elif cfg_eps > r["eps_ideal_val"]:
                kind, state = "red",   "OVEREXPANDED"
            else:
                kind, state = "blue",  "UNDEREXPANDED"
            self.dr_eps_config.set(f"{cfg_eps:.2f}", state, kind)
        else:
            self.dr_eps_config.set(f"{cfg_eps:.2f}")

        if r["Pe"]:
            flow  = "OVEREXPANDED" if r["overexpanded"] else "UNDEREXPANDED"
            fkind = "red" if r["overexpanded"] else "blue"
            self.dr_pe.set(f"{r['Pe']:.4f} psia", flow, fkind)
        self.dr_pamb_r.set(f"{r['Pamb']:.4f} psia")
        sep_state = "SEPARATING" if r["separating"] else "attached"
        self.dr_sep.set(
            f"{r['Psep']:.4f} psia",
            sep_state,
            "red" if r["separating"] else "green",
        )

        # Propellant properties
        self.dr_tc.set(f"{r['Tc_K']:.1f} K  ({r['Tc_K']-273.15:.1f} degC)")
        self.dr_tt.set(f"{r['Tt_K']:.1f} K")
        self.dr_te.set(f"{r['Te_K']:.1f} K")
        self.dr_gamma.set(f"{r['gamma_ch']:.4f}")
        self.dr_mw.set(
            f"{r['mol_wt_exit']:.4f} g/mol" if r["mol_wt_exit"] else "N/A"
        )
        if r["reactant_density_gcc"]:
            self.dr_density.set(
                f"{r['reactant_density_gcc']:.4f} g/cc  "
                f"({r['reactant_density_lbin3']:.5f} lb/in^3)",
                "blend" if r.get("reactant_density_source") == "Ingredient blend density" else "CEA",
                "green" if r.get("reactant_density_source") == "Ingredient blend density" else "grey",
            )
        else:
            self.dr_density.set("N/A")

        # CEA exclusion note
        if r["excluded_summary"]:
            names = ", ".join(e["name"] for e in r["excluded_summary"])
            pcts  = sum(e["wt_pct"] for e in r["excluded_summary"])
            self.lbl_excluded.setText(
                f"WARNING CEA EXCLUDED ({pcts:.3f} wt% total): {names}\n"
                f"    These ingredients were not included in the thermochemical calculation. "
                f"Their weight contributes to the binder system total."
            )
        else:
            self.lbl_excluded.setText("")
