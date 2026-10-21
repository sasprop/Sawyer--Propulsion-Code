"""Application entry point."""

import sys


def _selftest() -> int:
    """
    ``PropellantAnalyzer.exe --selftest``: run the default formulation through
    CEA without showing the window and write the result to
    ``<workspace>/selftest.txt``. Used to check a fresh build actually works.
    """
    import traceback

    from PyQt6.QtWidgets import QApplication

    from propellant_analyzer import __version__, paths

    paths.ensure_workspace()
    report = paths.WORKSPACE_DIR / "selftest.txt"
    app = QApplication(sys.argv[:1] + ["-platform", "offscreen"])
    app.setApplicationName("Propellant Analyzer self-test")
    try:
        from propellant_analyzer.cea_engine import run_cea
        from propellant_analyzer.input_panel import InputPanel

        r = run_cea(InputPanel().get_config())
        msg = (f"Propellant Analyzer v{__version__} self-test OK\n"
               f"C* {r['cstar']:.1f} ft/s | Isp vac {r['isp_vac']:.2f} s | "
               f"Isp amb {r['isp_amb']:.2f} s | Tc {r['Tc_K']:.0f} K\n")
        code = 0
    except Exception:
        msg = f"Propellant Analyzer v{__version__} self-test FAILED\n{traceback.format_exc()}"
        code = 1
    try:
        report.write_text(msg, encoding="utf-8")
    except OSError:
        pass
    if sys.stdout:
        print(msg)
    return code


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    from PyQt6.QtWidgets import QApplication

    from propellant_analyzer import APP_NAME, __version__
    from propellant_analyzer.paths import ensure_workspace
    from propellant_analyzer.theme import apply_theme  # also selects the QtAgg backend

    ensure_workspace()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    apply_theme(app)

    from propellant_analyzer.main_window import MainWindow

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
