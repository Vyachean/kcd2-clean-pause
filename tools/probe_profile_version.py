#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

TARGET = "Libs/Config/defaultProfile.xml"


def iter_paks(root: Path):
    candidates = []
    data = root / "Data"
    if data.is_dir():
        candidates.extend(data.rglob("*.pak"))
    candidates.extend(root.glob("*.pak"))
    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        yield path


def find_profile(root: Path):
    target_lower = TARGET.lower()
    for pak_path in iter_paks(root):
        try:
            with zipfile.ZipFile(pak_path, "r") as pak:
                entry = next(
                    (
                        name
                        for name in pak.namelist()
                        if name.replace("\\", "/").lower() == target_lower
                        or name.replace("\\", "/").lower().endswith("/" + target_lower)
                    ),
                    None,
                )
                if entry is None:
                    continue
                return pak_path, pak.read(entry)
        except (zipfile.BadZipFile, OSError):
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read the retail KCD2 defaultProfile.xml from game PAKs and print "
            "its action-map profile version. This tool is read-only."
        )
    )
    parser.add_argument(
        "game_root",
        type=Path,
        help="KCD2 game/content directory that contains Data/",
    )
    args = parser.parse_args()

    root = args.game_root.expanduser().resolve()
    if not root.exists():
        print(f"ERROR: path does not exist: {root}", file=sys.stderr)
        return 2

    found = find_profile(root)
    if found is None:
        print(
            f"ERROR: {TARGET} was not found in readable PAK files under {root}",
            file=sys.stderr,
        )
        return 3

    pak_path, xml_bytes = found
    try:
        profile = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        print(f"ERROR: profile XML could not be parsed: {exc}", file=sys.stderr)
        return 4

    version = profile.attrib.get("version")
    if version is None:
        print(f"ERROR: root element has no version attribute: <{profile.tag}>", file=sys.stderr)
        return 5

    print(f"PAK: {pak_path}")
    print(f"Profile root: {profile.tag}")
    print(f"Profile version: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
