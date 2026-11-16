"""Script: release_notes.py
Description:
    Extract one version's section from RELEASE-NOTES.md and write it out as the
    body of a GitHub Release.

    The build workflow runs this for every ``v*`` tag, so the notes published
    with the binaries cannot drift from the notes in the repository. The
    version is read from log.yaml, which already records it; a tag that does
    not match that version fails the build instead of publishing the wrong
    notes.

    A section starts at its level-2 heading and ends at the next one, so every
    subsection is part of the body. The heading itself is left out: the release
    title already carries the version.

    Heading forms accepted: ``## v1.0.0 - first release``, ``## 1.0.0``,
    ``## [1.0.0] - 2026-05-09``. The comparison ignores a leading ``v``, so a
    tag ``v1.0.0`` matches a ``## 1.0.0`` heading.

Usage:
    python utils/release_notes.py                          # print to stdout
    python utils/release_notes.py --output dist/release_notes.md
    python utils/release_notes.py --version 1.0.0         # override log.yaml
    python utils/release_notes.py --tag v1.0.0            # verify the tag matches

Exit codes:
    0  the section was extracted
    1  no section for that version in RELEASE-NOTES.md
    2  the requested version does not match log.yaml (or log.yaml is unreadable)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERSION_FILE = REPO_ROOT / "log.yaml"
DEFAULT_NOTES_FILE = REPO_ROOT / "RELEASE-NOTES.md"

EXIT_OK = 0
EXIT_NO_SECTION = 1
EXIT_VERSION_MISMATCH = 2

# A level-2 heading, which both starts a version section and terminates the one
# before it. The file's level-1 title is ignored.
LEVEL_TWO_HEADING = re.compile(r"^##(?!#)\s*(?P<text>.*?)\s*$", re.MULTILINE)

# The leading version token of a heading: "1.0.0", "v1.0.0", "[1.0.0]" and
# "[v1.0.0]" are all accepted, and anything after it ("- first release") is
# ignored.
HEADING_VERSION = re.compile(r"^\[?(?P<version>v?\d+(?:\.\d+)*)\]?")

# A horizontal rule separating releases, dropped when it trails the body.
TRAILING_RULE = re.compile(r"^-{3,}$")


def normalise(version: str) -> str:
    """Return a version without its leading ``v`` so tags and headings match."""
    return version.strip().lstrip("vV")


def read_version(path: Path) -> str:
    """Return the version recorded in log.yaml, or an empty string."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
    except (OSError, yaml.YAMLError):
        return ""
    return str(config.get("version") or "")


def extract_section(text: str, version: str) -> str | None:
    """Return the body of the section that belongs to ``version``."""
    headings = list(LEVEL_TWO_HEADING.finditer(text))
    wanted = normalise(version)

    for index, heading in enumerate(headings):
        match = HEADING_VERSION.match(heading.group("text"))
        if not match or normalise(match.group("version")) != wanted:
            continue

        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        lines = text[heading.end():end].splitlines()

        # Drop the blank line after the heading and the "---" rule that
        # separates this release from the next one.
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and (not lines[-1].strip() or TRAILING_RULE.match(lines[-1].strip())):
            lines.pop()

        return "\n".join(lines)

    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description="Extract one release's section from RELEASE-NOTES.md.",
    )
    parser.add_argument("--tag", help="the tag being released, e.g. v1.0.0")
    parser.add_argument("--version", help="the version to extract (default: log.yaml)")
    parser.add_argument("--notes", default=str(DEFAULT_NOTES_FILE), help="the release notes file")
    parser.add_argument("--version-file", default=str(DEFAULT_VERSION_FILE), help="the file holding the version")
    parser.add_argument("--output", help="write the notes to this file instead of stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Extract the notes and print or write them; return the exit code."""
    args = parse_args(argv)

    recorded = read_version(Path(args.version_file))
    if not recorded:
        print(f"ERROR: no version found in {args.version_file}", file=sys.stderr)
        return EXIT_VERSION_MISMATCH

    for requested in (args.tag, args.version):
        if requested and normalise(requested) != normalise(recorded):
            print(
                f"ERROR: {requested} does not match version {recorded} "
                f"in {args.version_file}",
                file=sys.stderr,
            )
            return EXIT_VERSION_MISMATCH

    version = args.version or args.tag or recorded

    try:
        text = Path(args.notes).read_text(encoding="utf-8")
    except OSError as error:
        print(f"ERROR: cannot read {args.notes}: {error}", file=sys.stderr)
        return EXIT_NO_SECTION

    section = extract_section(text, version)
    if section is None:
        print(f"ERROR: no '## {version}' section in {args.notes}", file=sys.stderr)
        return EXIT_NO_SECTION

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(section + "\n", encoding="utf-8")
        print(f"Wrote {output} ({len(section.splitlines())} lines)")
    else:
        print(section)

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
