"""
Cut a new version.

    python scripts/bump_version.py patch      # 1.0.0 -> 1.0.1  (bug fixes)
    python scripts/bump_version.py minor      # 1.0.1 -> 1.1.0  (new features)
    python scripts/bump_version.py major      # 1.1.0 -> 2.0.0  (breaking changes)
    python scripts/bump_version.py 1.4.2      # explicit

Updates src/propellant_analyzer/__init__.py, moves the "Unreleased" notes in
CHANGELOG.md under the new version heading, then commits and tags vX.Y.Z.
Push afterwards with:  git push && git push --tags
Add --no-git to only edit the files.
"""

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "src" / "propellant_analyzer" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 1
    text = INIT.read_text(encoding="utf-8")
    current = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', text)
    major, minor, patch = map(int, current.groups())
    part = args[0]
    if part == "major":
        new = f"{major + 1}.0.0"
    elif part == "minor":
        new = f"{major}.{minor + 1}.0"
    elif part == "patch":
        new = f"{major}.{minor}.{patch + 1}"
    elif re.fullmatch(r"\d+\.\d+\.\d+", part):
        new = part
    else:
        print(__doc__)
        return 1

    INIT.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{new}"', text), encoding="utf-8")
    if CHANGELOG.exists():
        log = CHANGELOG.read_text(encoding="utf-8")
        log = log.replace("## [Unreleased]", f"## [Unreleased]\n\n## [{new}] - {dt.date.today():%Y-%m-%d}", 1)
        CHANGELOG.write_text(log, encoding="utf-8")
    print(f"Version {'.'.join(current.groups())} -> {new}")

    if "--no-git" not in argv:
        subprocess.run(["git", "add", str(INIT), str(CHANGELOG)], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"Release v{new}"], cwd=ROOT, check=True)
        subprocess.run(["git", "tag", "-a", f"v{new}", "-m", f"v{new}"], cwd=ROOT, check=True)
        print(f"Committed and tagged v{new}. Now run:  git push && git push --tags")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
