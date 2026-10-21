"""
Every file path the app uses is resolved here, so nothing else hard-codes a
location.

Two kinds of files:

* Bundled resources (read-only): ``ingredients.json``, ``atomic_masses.txt``
  and the seed ``user_ingredients.json``. They live in ``propellant_analyzer/data``
  when running from source, and inside the PyInstaller bundle when frozen.

* User-writable files: the user ingredient library, saved configs and
  Formula Outputs.

  - Running from source (``python run.py``): kept inside the repository, so the
    ingredient library is versioned with git and outputs land in ``Formula Outputs/``
    next to the code, exactly like the old layout.
  - Running the packaged .exe: kept in ``Documents/Propellant Analyzer``, because
    the install folder may be read-only. On first launch the bundled ingredient
    library is copied there.

Set the ``PROPELLANT_ANALYZER_HOME`` environment variable to force a specific
workspace folder in either mode.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
FROZEN = bool(getattr(sys, "frozen", False))


def _resource_dir() -> Path:
    if FROZEN:
        # PyInstaller unpacks bundled data under sys._MEIPASS
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "propellant_analyzer" / "data"
    return PACKAGE_DIR / "data"


def _documents_dir() -> Path:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5 (My Documents); honours OneDrive redirection
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Documents"


def _workspace_dir() -> Path:
    override = os.environ.get("PROPELLANT_ANALYZER_HOME")
    if override:
        return Path(override).expanduser()
    if FROZEN:
        return _documents_dir() / "Propellant Analyzer"
    # src/propellant_analyzer -> repository root
    return PACKAGE_DIR.parent.parent


RESOURCE_DIR = _resource_dir()
WORKSPACE_DIR = _workspace_dir()

INGREDIENTS_DB = RESOURCE_DIR / "ingredients.json"
ATOMIC_MASSES = RESOURCE_DIR / "atomic_masses.txt"
SEED_USER_DB = RESOURCE_DIR / "user_ingredients.json"

if FROZEN or os.environ.get("PROPELLANT_ANALYZER_HOME"):
    USER_DB = WORKSPACE_DIR / "user_ingredients.json"
else:
    # From source, edit the tracked library in place so changes show up in git.
    USER_DB = SEED_USER_DB

DEFAULT_OUTPUT_DIR = WORKSPACE_DIR / "Formula Outputs"
CONFIG_DIR = WORKSPACE_DIR / "configs"


def ensure_workspace() -> None:
    """Create the user folders and seed the user ingredient library if needed."""
    for d in (DEFAULT_OUTPUT_DIR, CONFIG_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    if USER_DB != SEED_USER_DB and not USER_DB.exists() and SEED_USER_DB.exists():
        try:
            USER_DB.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SEED_USER_DB, USER_DB)
        except OSError:
            pass


def resolve_output_dir(saved: str | None) -> str:
    """
    Return a usable output folder. Configs saved by older versions point at
    folders that no longer exist (e.g. ``C:/RocketCEA/Propellant Analyzer 9000/...``);
    those fall back to the default instead of failing on save.
    """
    if saved:
        p = Path(saved).expanduser()
        if p.is_dir():
            return str(p)
    return str(DEFAULT_OUTPUT_DIR)
