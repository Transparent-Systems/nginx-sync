"""Build the Nginx Sync binary with PyInstaller.

Usage:
    python build_project.py                    # dist/nginx-sync (onefile)
    python build_project.py --layout onedir    # dist/nginx-sync/ folder
    python build_project.py --help

Nginx Sync is one command-line script (main.py), so there is a single target:
the binary is called ``nginx-sync`` (``nginx-sync.exe`` on Windows).

config.yaml, log.yaml and .env are deliberately *not* bundled. They are user
specific - server addresses, credentials, log settings - and the binary reads
them from the folder it lives in (see get_script_dir() in main.py), so a
release only has to ship the executable.

PyInstaller must be installed for the interpreter that runs this script
(python -m pip install -r requirements.txt).
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

# --- Configuration ---
MAIN_SCRIPT = "main.py"
APP_NAME = "nginx-sync"
DIST_DIR = "dist"
BUILD_DIR = "build"

# The project virtualenv, created by the README's "Setup Python Virtual
# Environment" step. Building with it is what keeps the dependencies (and
# therefore the binary) reproducible.
VENV_DIR = ".venv"

# requirements.txt pins python-dotenv 1.2.2 and PyInstaller 6.x, which need
# Python 3.10 or newer. Checking it here turns "pip could not find a version"
# into a message that says which interpreter ran and what to do about it.
MINIMUM_PYTHON = (3, 10)

# log.yaml is the file that already records the version, so reading it here
# avoids introducing a second place to keep in step.
VERSION_FILE = "log.yaml"
FALLBACK_VERSION = "0.0.0"

# Bundled into the binary so a copy shipped without configuration can still
# report its version (--version). A log.yaml next to the binary, or in the folder
# named by --config-dir, always takes precedence.
BUNDLED_FILES = ("log.yaml",)

# PyInstaller bundle layout. onefile packs everything into a single executable
# that unpacks itself on every start; onedir ships a folder whose executable
# starts immediately, at the cost of shipping the folder as a whole.
DEFAULT_LAYOUT = "onefile"
LAYOUTS = ("onefile", "onedir")


def binary_path(layout: str) -> Path:
    """Return where PyInstaller writes the binary for the given layout."""
    suffix = ".exe" if sys.platform == "win32" else ""
    if layout == "onedir":
        return Path(DIST_DIR) / APP_NAME / f"{APP_NAME}{suffix}"
    return Path(DIST_DIR) / f"{APP_NAME}{suffix}"


def read_version(path: str = VERSION_FILE) -> str:
    """Return the app version recorded in log.yaml, or a placeholder."""
    try:
        import yaml
    except ImportError:
        return FALLBACK_VERSION

    try:
        with open(path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
    except (OSError, yaml.YAMLError):
        return FALLBACK_VERSION

    return str(config.get("version") or FALLBACK_VERSION)


def build_command(layout: str) -> list[str]:
    """Return the PyInstaller command line for one build."""
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        APP_NAME,
        f"--{layout}",
        # The sync logs to the terminal as well as to logs/, so keep the console.
        "--console",
        # Keep a local build byte-comparable with the release built in CI: UPX
        # compression changes the executable and is not guaranteed to be
        # installed everywhere.
        "--noupx",
        "--noconfirm",
        # Keep the generated nginx-sync.spec out of the repository root.
        "--distpath",
        DIST_DIR,
        "--workpath",
        BUILD_DIR,
        "--specpath",
        BUILD_DIR,
    ]

    for name in BUNDLED_FILES:
        if os.path.exists(name):
            # An absolute source: --specpath moves the generated spec into
            # build/, and relative paths there are resolved against it.
            # os.pathsep, not ":", so the same option works on Windows.
            command.append(f"--add-data={os.path.abspath(name)}{os.pathsep}.")

    command.append(MAIN_SCRIPT)
    return command


def interpreter_error() -> str | None:
    """Return why this interpreter cannot build the app, or None when it can."""
    if sys.version_info >= MINIMUM_PYTHON:
        return None

    required = ".".join(str(part) for part in MINIMUM_PYTHON)
    running = ".".join(str(part) for part in sys.version_info[:3])
    return (
        f"ERROR: Python {required} or newer is required; this is {running}.\n"
        f"  interpreter: {sys.executable}\n"
        "  Create the virtualenv with a newer interpreter and use it explicitly:\n"
        f"    python3.12 -m venv {VENV_DIR}\n"
        f"    {VENV_DIR}/bin/python -m pip install -r requirements.txt\n"
        f"    {VENV_DIR}/bin/python build_project.py"
    )


def venv_warning() -> str | None:
    """Return a hint when the build ignores the project virtualenv, else None.

    An activated virtualenv only wins if `python` really resolves to
    .venv/bin/python; a pyenv shim or an alias earlier in PATH silently picks
    another interpreter, and the build then fails on an unexpected version.
    """
    venv = Path(VENV_DIR)
    if not (venv / "pyvenv.cfg").exists():
        return None

    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.exists():
        return None

    try:
        if Path(sys.prefix).resolve() == venv.resolve():
            return None
    except OSError:
        return None

    return (
        f"NOTE: building with {sys.executable}, not the project virtualenv.\n"
        f"  Use: {python} build_project.py"
    )


def build(layout: str = DEFAULT_LAYOUT) -> int:
    """Build the binary and return a process exit code."""
    problem = interpreter_error()
    if problem:
        print(problem)
        return 2

    warning = venv_warning()
    if warning:
        print(warning)

    if not os.path.exists(MAIN_SCRIPT):
        print(f"ERROR: {MAIN_SCRIPT} not found. Run this script from the repository root.")
        return 2

    if importlib.util.find_spec("PyInstaller") is None:
        print("ERROR: PyInstaller is not installed for this interpreter.")
        print(f"  interpreter: {sys.executable}")
        print(f"  install it with: {sys.executable} -m pip install -r requirements.txt")
        return 2

    output = binary_path(layout)
    command = build_command(layout)

    print(f"Building {output} ({layout}, version {read_version()}):")
    print("  " + " ".join(command))

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        print("\nERROR: PyInstaller build failed.")
        return error.returncode

    if not output.exists():
        print(f"\nERROR: PyInstaller finished but {output} is missing.")
        return 1

    megabytes = output.stat().st_size / (1024 * 1024)
    print(f"\nSUCCESS: {output} created ({megabytes:.1f} MB)")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description="Build the nginx-sync binary with PyInstaller.",
    )
    parser.add_argument(
        "--layout",
        choices=LAYOUTS,
        default=DEFAULT_LAYOUT,
        help="onefile (default) puts everything in one executable; "
        "onedir ships a folder that starts faster",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Build the binary using the arguments on the command line."""
    args = parse_args(argv)
    return build(args.layout)


if __name__ == "__main__":
    sys.exit(main())
