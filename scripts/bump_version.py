#!/usr/bin/env python3
"""Version bump utility. Usage:

    python scripts/bump_version.py patch   # 0.1.0 → 0.1.1
    python scripts/bump_version.py minor   # 0.1.0 → 0.2.0
    python scripts/bump_version.py major   # 0.1.0 → 1.0.0
"""
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Files that contain version strings
VERSION_FILES = {
    PROJECT_ROOT / "lumina-py" / "pyproject.toml": r'version\s*=\s*"([^"]+)"',
    PROJECT_ROOT / "lumina-cpp" / "CMakeLists.txt": r'project\(lumina-cpp VERSION ([^\s]+)',
    PROJECT_ROOT / "lumina-py" / "src" / "main.py": r'version\s*=\s*"([^"]+)"',
}


def read_version() -> str:
    for path, pattern in VERSION_FILES.items():
        if path.exists():
            m = re.search(pattern, path.read_text(encoding="utf-8"))
            if m:
                return m.group(1)
    raise RuntimeError("No version found")


def bump(part: str) -> str:
    major, minor, patch = map(int, read_version().split("."))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown part: {part}")
    return f"{major}.{minor}.{patch}"


def write_version(new_ver: str):
    for path, pattern in VERSION_FILES.items():
        if path.exists():
            text = path.read_text(encoding="utf-8")
            def repl(m):
                return m.group(0).replace(m.group(1), new_ver)
            text = re.sub(pattern, repl, text)
            path.write_text(text, encoding="utf-8")
            print(f"  {path.name}: {new_ver}")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("patch", "minor", "major"):
        print(__doc__.strip())
        sys.exit(1)

    old_ver = read_version()
    new_ver = bump(sys.argv[1])
    print(f"Bumping version: {old_ver} → {new_ver}")
    write_version(new_ver)
    print(f"\nDone. Commit with:  git commit -m 'chore: bump {old_ver} → {new_ver}'")
    print(f"Tag with:          git tag v{new_ver}")


if __name__ == "__main__":
    main()
