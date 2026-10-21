"""
Launch Propellant Analyzer from a source checkout:

    python run.py

(This is also the entry script PyInstaller freezes into the .exe.)
"""

import os
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from propellant_analyzer.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
