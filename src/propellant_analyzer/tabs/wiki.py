"""WIKI tab: methodology and variable reference, filled with the current inputs."""

from html import escape
from typing import Optional

from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from propellant_analyzer import database as DB
from propellant_analyzer.paths import DEFAULT_OUTPUT_DIR
from propellant_analyzer.theme import C


class WikiTab(QWidget):
    """Wiki-style reference for the variables and outputs used by the current app."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        lay.addWidget(self.text)
        self.update_content({})

    def _table_html(self, rows: list[tuple[str, str, str, str, str]]) -> str:
        out = [
            "<table style='width:100%; border-collapse:collapse; font-size:12px;'>",
            "<tr>"
            f"<th style='text-align:left; border-bottom:1px solid {C['border2']}; padding:6px; color:{C['amber']};'>Variable</th>"
            f"<th style='text-align:left; border-bottom:1px solid {C['border2']}; padding:6px; color:{C['amber']};'>Current</th>"
            f"<th style='text-align:left; border-bottom:1px solid {C['border2']}; padding:6px; color:{C['amber']};'>Meaning</th>"
            f"<th style='text-align:left; border-bottom:1px solid {C['border2']}; padding:6px; color:{C['amber']};'>Importance</th>"
            f"<th style='text-align:left; border-bottom:1px solid {C['border2']}; padding:6px; color:{C['amber']};'>Influences</th>"
            "</tr>",
        ]
        for name, current, meaning, importance, influences in rows:
            out.append(
                "<tr>"
                f"<td style='vertical-align:top; padding:6px; border-bottom:1px solid {C['border']};'><code>{escape(name)}</code></td>"
                f"<td style='vertical-align:top; padding:6px; border-bottom:1px solid {C['border']};'>{escape(current)}</td>"
                f"<td style='vertical-align:top; padding:6px; border-bottom:1px solid {C['border']};'>{escape(meaning)}</td>"
                f"<td style='vertical-align:top; padding:6px; border-bottom:1px solid {C['border']};'>{escape(importance)}</td>"
                f"<td style='vertical-align:top; padding:6px; border-bottom:1px solid {C['border']};'>{escape(influences)}</td>"
                "</tr>"
            )
        out.append("</table>")
        return "".join(out)

    def update_content(self, cfg: dict, r: Optional[dict] = None):
        cfg = cfg or {}
        db_count = len(DB.get_all_ingredients())
        run_rows = [
            ("formula_name", str(cfg.get("formula_name", "HTPB-AP BASELINE")), "Human-readable formula name used in saved files and result headings.", "Low engineering impact, high organization value.", "Output filenames, tabs, saved configs."),
            ("formula_tag", str(cfg.get("formula_tag", "")), "Short tag for quick identification.", "Useful when comparing many formulas.", "Labels and saved outputs."),
            ("formula_notes", (cfg.get("formula_notes", "") or "")[:80] + ("..." if len(cfg.get("formula_notes", "")) > 80 else ""), "Freeform notes about the formula, processing, or assumptions.", "Documentation only.", "Saved configs and wiki context."),
            ("cure_mode", str(cfg.get("cure_mode", "calc")), "Binder-system workflow mode. Cure Calculator auto-computes the main binder/curative split; Manual preserves direct wt% entry.", "High if you are balancing curatives manually.", "Binder-table editability and liquid wt% behavior."),
            ("nco_oh_ratio", f"{float(cfg.get('nco_oh_ratio', 0.89)):.3f}", "Target NCO:OH equivalent ratio used by the cure calculator.", "High for polyurethane binder stoichiometry and processing margin.", "Binder/curative split and cure-check status."),
            ("pc_psia", f"{float(cfg.get('pc_psia', 1000.0)):.3f} psia", "Chamber pressure sent to RocketCEA.", "Very high. This is one of the main thermochemical state variables.", "c*, Isp, temperatures, gamma, species composition, flame-color screen."),
            ("eps", f"{float(cfg.get('eps', 9.0)):.3f}", "Nozzle expansion ratio (exit area / throat area) used by the CEA run.", "Very high for exit pressure, ambient Isp, and species freeze/equilibrium trends.", "Nozzle analysis, Isp chart, flame-color exit composition."),
            ("alt_mode / pamb", f"{cfg.get('alt_mode', 'manual')} / {float(cfg.get('pamb', 14.7)):.4f} psia", "Ambient-pressure mode. Manual uses the entered pressure; fixed and range derive it from altitude inputs.", "High whenever sea-level versus altitude performance matters.", "Ambient Isp, overexpansion check, separation warning."),
            ("cstar_eff", f"{float(cfg.get('cstar_eff', 1.0)):.4f}", "Efficiency factor applied to theoretical c*.", "Medium when comparing theoretical versus expected hardware performance.", "Displayed c* value."),
            ("isp_eff", f"{float(cfg.get('isp_eff', 1.0)):.4f}", "Efficiency factor applied to theoretical Isp outputs.", "Medium to high for expected delivered performance estimates.", "Vacuum/ambient/ideal Isp displays and charts."),
            ("output_dir", str(cfg.get("output_dir", DEFAULT_OUTPUT_DIR)), "Folder used when saving raw output files.", "Low technical impact.", "Saved text output path."),
        ]

        ingredient_rows = [
            ("include_cea", "per-row checkbox", "Whether a row participates in the thermochemical CEA blend or is only weight-tracked.", "Very high for accurate chemistry.", "Blend composition, c*, Isp, temperatures, species output."),
            ("ingredient", "per-row selection", "Database ingredient record chosen for the row.", "Very high because it sets formula, density, aliases, category, and notes.", "Every downstream calculation that uses that row."),
            ("wt_pct", "per-row value", "Weight-percent contribution of the ingredient row.", "Very high because the blend must be physically meaningful and near 100 wt% total.", "All CEA outputs and cure-calculator totals."),
            ("type", "derived", "Category label from the ingredient database.", "Medium for workflow and interpretation.", "How the app groups rows and which guidance appears."),
            ("func_override", "optional", "Functional-group override for cure calculations.", "High when database defaults do not match the intended reactive role.", "OH/NCO bookkeeping and Weq behavior."),
            ("weq_override", "optional", "Equivalent-weight override used when the functional group is overridden.", "High when cure stoichiometry is being tuned from measured material data.", "NCO/OH split and cure-check status."),
        ]

        output_rows = [
            ("Performance tab", "live output", "Primary c*, Isp, nozzle expansion, and key thermodynamic outputs.", "Primary engineering summary.", "Read-only result presentation."),
            ("ISP / temperature chart", "live output", "Sweeps expansion ratio to show either vacuum/ambient Isp or chamber/throat/exit temperature (Kelvin, deg C or deg F). Hover anywhere for a readout of every curve at that eps. Every run is kept in the Run History panel (also across sessions); tick runs, or add saved configs, to overlay one chosen curve from each, with dots at each run's design eps.", "High for nozzle and thermal trade studies and for comparing formulations.", "Charted post-processing of RocketCEA results."),
            ("Chemistry tab", "live output", "Oxygen balance and atom inventory from the CEA-participating ingredients.", "Medium to high for formulation sanity checks.", "Interpretation of oxidizer/fuel balance."),
            ("Flame Color tab", "live output", "Screens exit species for likely visible emitters and applies an alumina-smoke penalty to color visibility.", "High when plume appearance matters.", "Exit-species interpretation and heuristic color ranking."),
            ("Raw CEA Output", "text export", "Full NASA CEA text dump plus saved-file export.", "High for detailed verification and troubleshooting.", "Direct access to the underlying solver output."),
        ]

        flame_rows = [
            ("Mapped emitters", "gas/radical species", "The app checks RocketCEA injector/chamber/throat/exit species against a curated emitter map for Na, K, Li, Sr, Ca, Ba, Cu, CH, C2, CN, and OH.", "High for color screening.", "Flame Color table and family totals."),
            ("Raw family score", "heuristic sum", "Before smoke penalties, each mapped species contributes approximately `exit mol% x species weight` to one color family. Sodium is weighted heavily because it is visually dominant; copper, strontium, barium, lithium, and radicals have lower but still important weights.", "High for ranking which families the chemistry wants to produce.", "Dominant color family before plume washout."),
            ("Visibility score", "higher is better", "The main displayed score is the family score after the plume-clarity penalty is applied. Higher means the predicted color-active emitters are stronger and more likely to remain visible through the plume. Lower means the effect is weaker, more washed out, or likely to be overwhelmed by smoke / broadband emission.", "High for comparing formulas against each other. It is a screening metric, not a measured brightness.", "Likely Hue, Dominant Score, family cards, interpretation notes."),
            ("Plume clarity", "0 to 1 factor", "A multiplier that reduces color visibility when the exit mix contains a lot of alumina smoke products such as AL2O3(a) and AL2O3(L). 1.0 means little smoke penalty; lower values mean a whiter, more opaque plume is likely to dilute the apparent color.", "Very high for aluminized propellants.", "Adjusted family scores and interpretation notes."),
            ("Alumina smoke exit %", "screening metric", "Approximate total exit mole percent of mapped condensed alumina species. More alumina usually means more white smoke and lower color purity, even if the chemistry contains strong emitters.", "High when metal loading is significant.", "Plume clarity and smoke notes."),
            ("Dominant hue", "best current family", "The color family with the strongest adjusted visibility score after smoke penalties are applied.", "Medium. Good quick summary, but it can hide second-place families that may still tint the flame.", "Headline color shown in the Flame Color tab."),
        ]

        flame_scale_rows = [
            ("0 to 1", "Weak screen", "Very low adjusted visibility. The colorant may be too dilute, the emitters may not be favored thermochemically, or smoke may be washing the hue out badly. Expect little reliable color purity."),
            ("1 to 5", "Noticeable but uncertain", "Often enough to justify further testing, but still vulnerable to sodium contamination, alumina smoke, afterburning, and broadband incandescent light from particles."),
            ("5 to 15", "Promising", "Usually a strong screening result for this app. The chemistry is producing meaningful color-active species even after plume penalties. This is a good range to compare candidate formulas."),
            ("15+", "Very strong screen", "Excellent heuristic result. Higher is better here, but it still does not guarantee a clean observed flame because the score is not a calibrated photometric intensity."),
        ]

        if r:
            snapshot = [
                ("cstar", f"{float(r.get('cstar', 0.0)):.2f} ft/s", "Delivered c* after the chosen efficiency factor.", "High.", "Performance cards."),
                ("isp_vac / isp_amb", f"{float(r.get('isp_vac', 0.0)):.2f} / {float(r.get('isp_amb', 0.0)):.2f} s", "Vacuum and ambient specific impulse.", "High.", "Performance cards and charts."),
                ("Tc / gamma", f"{float(r.get('Tc_K', 0.0)):.2f} K / {float(r.get('gamma_ch', 0.0)):.4f}", "Chamber temperature and ratio of specific heats.", "High.", "Nozzle analysis and species state."),
                ("dominant flame hue", str(r.get('flame_analysis', {}).get('dominant_family') or "-"), "Current dominant flame-color family from the heuristic screen.", "Medium.", "Flame Color tab."),
            ]
        else:
            snapshot = [
                ("run snapshot", "No run yet", "Run analysis to populate current performance numbers.", "Medium.", "Performance and output tabs."),
            ]

        html = f"""
        <div style="font-family:'Segoe UI'; color:{C['text1']}; line-height:1.45;">
          <h2 style="color:{C['amber']}; margin-bottom:6px;">Program Methodology & Variable Wiki</h2>
          <p>This page documents the variables currently used by the CEA app, what they mean, why they matter, and what they influence. The goal is not just to define labels, but to explain how the variables affect the run and how to interpret the output.</p>
          <p>The current merged ingredient library contains <b>{db_count}</b> searchable entries. Popup details pull directly from the ingredient database, so better notes, aliases, and category metadata improve both usability and the quality of formulation review.</p>

          <h3 style="color:{C['amber']};">Formula / Run Variables</h3>
          {self._table_html(run_rows)}

          <h3 style="color:{C['amber']};">Ingredient Row Variables</h3>
          {self._table_html(ingredient_rows)}

          <h3 style="color:{C['amber']};">Output Tabs</h3>
          {self._table_html(output_rows)}

          <h3 style="color:{C['amber']};">Flame-Color Methodology</h3>
          {self._table_html(flame_rows)}

          <h3 style="color:{C['amber']};">How To Read The Visibility Score</h3>
          <p>
            The visibility score is a ranking tool. <b>Higher is better</b> if your goal is a more visible and more chemically supported flame hue.
            The score is not a literal brightness in candela and it is not a guarantee of what a camera or eye will see during a real motor firing.
            It is best used to compare one formulation against another inside this same app, using the same pressure and expansion assumptions.
          </p>
          <p>
            A formula can have a strong colorant chemistry but still look disappointing if a separate plume effect dominates the eye. Common causes are:
            sodium contamination turning everything yellow, white alumina smoke from aluminum washing out the hue, incandescent metal droplets adding broadband light,
            and afterburning outside the nozzle changing the apparent plume color.
          </p>
          {self._table_html([(band, label, meaning, "Use as an internal comparison guide, not an absolute pass/fail rule.", "How you judge candidate formulations before test firing.") for band, label, meaning in flame_scale_rows])}

          <h3 style="color:{C['amber']};">Practical Flame-Color Interpretation</h3>
          <p>
            <b>Plume clarity</b> is the smoke penalty factor. Values near <code>1.0</code> are better because they mean the app expects less color washout from alumina.
            Values below roughly <code>0.5</code> mean the predicted hue may still be chemically present, but the visible plume could look pale, smoky, or nearly white.
          </p>
          <p>
            <b>Alumina smoke exit %</b> should be read as a warning light, not a direct opacity law. Higher values are generally worse for color purity. A heavily aluminized formula can still make lots of copper,
            strontium, or barium emitters, but the visible result may be pastel or washed out because the plume itself becomes bright and opaque.
          </p>
          <p>
            <b>Dominant hue</b> simply means “highest adjusted family score right now.” If the top two families are close together, the real plume may look mixed, shift with operating condition,
            or be very sensitive to small ingredient changes. The detailed species table is there so you can see whether the hue is driven by one strong emitter or by a broad mix of weaker contributors.
          </p>

          <h3 style="color:{C['amber']};">Flat Step In The Exit Temperature Curve</h3>
          <p>
            For aluminized propellants the exit temperature in the ISP chart stops falling and holds at exactly
            <b>2327 K</b> over a band of expansion ratios, then starts falling again. That is real equilibrium
            thermochemistry, not a glitch: 2327 K is the melting point of Al2O3. As the gas expands, the liquid
            alumina droplets freeze, and the latent heat of fusion they release holds the gas temperature at the
            melting point until all of the alumina is solid (CEA lists AL2O3(L) and AL2O3(a) together in that band).
            The chart shades the band. It appears near the eps where Te would otherwise cross 2327 K, so it moves
            with chamber pressure and aluminium loading, and can be absent if Te never reaches 2327 K.
          </p>
          <p>
            In a real nozzle the particles lag the gas and can supercool, so the measured plume will not show a
            sharp plateau. Treat the step as a property of the shifting-equilibrium model. The jump in the
            ambient Isp curve at larger eps is a separate effect: it sits in the range where RocketCEA's ambient-Isp
            estimate assumes the nozzle flow has separated, and comes from that separated-nozzle approximation,
            not from the chemistry.
          </p>

          <h3 style="color:{C['amber']};">Ingredient Density Flags</h3>
          <p>
            Every ingredient density is either <b>measured</b> (allprop.dat or a literature value), <b>estimated</b>,
            or <b>not available</b>. Estimated densities come from atomic-volume increments fitted to the allprop.dat
            entries with known densities (typically within about 9%, occasionally 25%). They show as "(est.)" in the
            ingredient browser, and a run that uses one is flagged on the Performance tab. When any ingredient has no
            density the blend density cannot be computed; the app then uses RocketCEA's reactant density if available,
            otherwise reports N/A and names the ingredient.
          </p>

          <h3 style="color:{C['amber']};">Ingredient Database & Curation Notes</h3>
          <p>
            The ingredient browser is intended to mix three kinds of information: solver-ready CEA cards, weight-tracked reference materials, and practical formulation notes.
            Not every useful propellant additive has a full NASA-CEA-ready thermo card on hand. When a material is present only as a reference entry, it can still be cataloged, searched, compared,
            and documented while awaiting a better thermochemical card.
          </p>
          <p>
            High-value data sources for future database expansion include NASA CEA / ThermoBuild species sets, NIST Chemistry WebBook condensed-phase thermochemistry,
            JANAF tables, Active Thermochemical Tables (ATcT), and curated combustion databases such as Burcat-derived NASA polynomial collections. Those sources are especially useful when upgrading
            a reference ingredient into a real CEA-capable ingredient.
          </p>
          <p>
            For flame-color work, the most useful extra metadata are: whether the ingredient is a colorant source, whether it is a halogen donor, whether it tends to create smoke or incandescent light,
            and whether it is mainly a catalyst versus a bulk oxidizer or fuel. Those notes affect formulation strategy even when the raw thermochemical inputs look similar.
          </p>

          <h3 style="color:{C['amber']};">Current Snapshot</h3>
          {self._table_html(snapshot)}

          <p style="margin-top:12px; color:{C['text2']};">
            Flame-color interpretation is heuristic. The app uses RocketCEA equilibrium product composition at the nozzle exit,
            then maps known emitters and reduces the resulting visibility score when alumina smoke products are high.
            That helps rank formulations, but it is not a substitute for plume spectroscopy, static-fire observation, or a full radiative / condensed-phase plume model.
          </p>
        </div>
        """
        self.text.setHtml(html)
