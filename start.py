#!/usr/bin/env python3
"""
Lumina — One-Click Launcher

Detects available services (OpenAI, whisper, edge-tts, etc.) and starts
Lumina with sensible defaults. Falls back to mock mode if real services
are unavailable.

Usage:
    python start.py                  # Auto-detect, start with mock fallback
    python start.py --mock           # Force mock mode
    python start.py --no-mock        # Require real services
    python start.py --help           # Show full help
"""
import argparse
import os
import sys
import subprocess
import shutil
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.absolute()
LUMINA_PY = PROJECT_ROOT / "lumina-py"
REQUIREMENTS = LUMINA_PY / "requirements.txt"
CONFIG_FILE = LUMINA_PY / "config.yaml"
DOCS_FILE = PROJECT_ROOT / "docs" / "project_intro.md"


def print_banner():
    print(r"""
    __    _                 _
   / /   | |               (_)
  / /_ _| |_ _ __ ___  __ _ _ _ __
 / / _` | __| '_ ` _ \/ _` | | '_ \
/ / (_| | |_| | | | | | (_| | | | | |
\_/\__,_|\__|_| |_| |_|\__,_|_|_| |_|

  Virtual Human Live Streaming Platform
============================================
""")


def check_dependency(name: str, import_name: str = None) -> bool:
    try:
        __import__(import_name or name)
        return True
    except ImportError:
        return False


def check_proto_stubs() -> bool:
    proto_path = LUMINA_PY / "lumina-proto" / "build"
    return (proto_path.exists() and
            any(proto_path.glob("lumina_pb2*.py")))


def get_system_python() -> str:
    for candidate in ["python", "python3", "py"]:
        if shutil.which(candidate):
            try:
                subprocess.run([candidate, "--version"],
                               capture_output=True, check=True)
                return candidate
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
    return "python"


def run_start(args):
    python = get_system_python()
    os.chdir(str(LUMINA_PY))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(LUMINA_PY)

    if args.mock:
        env["LUMINA_MOCK"] = "1"
    elif args.no_mock:
        env["LUMINA_MOCK"] = "0"

    cmd = [python, "-m", "src.main"]
    if args.config:
        cmd.extend(["--config", args.config])

    print(f"Starting Lumina with: {' '.join(cmd)}")
    print(f"Working directory: {os.getcwd()}")
    print()

    try:
        proc = subprocess.Popen(cmd, env=env)
        if args.open_browser and not args.mock:
            import time
            time.sleep(3)
            webbrowser.open("http://localhost:8000/")
        elif args.open_browser and args.mock:
            print("[start] --open-browser skipped in mock mode (no UI server)")
        proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        proc.terminate()
        proc.wait()


def run_install(args):
    python = get_system_python()
    print("Installing Lumina Python dependencies...")

    subprocess.check_call(
        [python, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        cwd=str(LUMINA_PY),
    )
    print("Dependencies installed successfully!")


def run_proto(args):
    proto_bat = PROJECT_ROOT / "lumina-proto" / "build_proto.bat"
    if proto_bat.exists():
        print("Compiling Protocol Buffers...")
        subprocess.check_call([str(proto_bat)], cwd=str(proto_bat.parent))
        print("Proto compilation complete!")
    else:
        print("build_proto.bat not found at", proto_bat)


def run_check(args):
    print("Checking Lumina environment...\n")

    checks = [
        ("OpenAI SDK", check_dependency("openai"), "pip install openai"),
        ("FastAPI", check_dependency("fastapi"), "pip install fastapi"),
        ("gRPC", check_dependency("grpc"), "pip install grpcio"),
        ("edge-tts", check_dependency("edge_tts"), "pip install edge-tts"),
        ("Whisper", check_dependency("whisper"), "pip install openai-whisper"),
        ("Vosk", check_dependency("vosk"), "pip install vosk"),
        ("CrewAI", check_dependency("crewai"), "pip install crewai"),
        ("Proto stubs", check_proto_stubs(), "cd lumina-proto && build_proto.bat"),
    ]

    for name, ok, fix in checks:
        status = "\033[32mOK\033[0m" if ok else "\033[31mMISSING\033[0m"
        print(f"  [{status}] {name}")
        if not ok:
            print(f"          -> {fix}")

    print()

    deps_ok = all(ok for _, ok, _ in checks[:3])
    if deps_ok:
        print("Basic dependencies OK. You can run: python start.py")
    else:
        print("Some core dependencies missing. Run: python start.py install")


def main():
    parser = argparse.ArgumentParser(
        description="Lumina Virtual Human — One-Click Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start.py                   Auto-start with mock fallback
  python start.py --mock            Force mock mode (no real AI needed)
  python start.py install           Install Python dependencies
  python start.py check             Check environment
  python start.py proto             Compile gRPC stubs
        """,
    )

    parser.add_argument("command", nargs="?", default="start",
                        choices=["start", "install", "proto", "check"],
                        help="Command to run (default: start)")
    parser.add_argument("--mock", action="store_true",
                        help="Force mock mode (no real AI services needed)")
    parser.add_argument("--no-mock", action="store_true",
                        help="Require real AI services, fail if unavailable")
    parser.add_argument("--config", type=str,
                        help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("--open-browser", action="store_true",
                        help="Open browser after startup")
    parser.add_argument("--version", action="store_true",
                        help="Show version info")

    args = parser.parse_args()

    if args.version:
        print("Lumina v0.1.0")
        return

    print_banner()

    commands = {
        "start": run_start,
        "install": run_install,
        "proto": run_proto,
        "check": run_check,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
