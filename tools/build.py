#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "src"
MANIFEST = ROOT / "mod" / "mod.manifest"
RELEASE_DIR = ROOT / "release" / "clean_pause"
PAK_PATH = RELEASE_DIR / "Data" / "clean_pause.pak"


def build() -> Path:
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)

    PAK_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST, RELEASE_DIR / "mod.manifest")

    with zipfile.ZipFile(PAK_PATH, "w", compression=zipfile.ZIP_DEFLATED) as pak:
        for path in sorted(SOURCE_DIR.rglob("*")):
            if path.is_file():
                pak.write(path, path.relative_to(SOURCE_DIR).as_posix())

    validate()
    return RELEASE_DIR


def validate() -> None:
    if not MANIFEST.is_file():
        raise SystemExit(f"Missing manifest: {MANIFEST}")

    if not PAK_PATH.is_file():
        raise SystemExit(f"Missing pak: {PAK_PATH}")

    with zipfile.ZipFile(PAK_PATH, "r") as pak:
        names = pak.namelist()
        expected_entry = "Scripts/Mods/clean_pause.lua"

        if expected_entry not in names:
            raise SystemExit(f"PAK is missing required entry: {expected_entry}")

        if any(name.lower().startswith("data/") for name in names):
            raise SystemExit("PAK paths must be relative to Data, not contain Data/")

        unsupported = [
            name
            for name in names
            if pak.getinfo(name).compress_type
            not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
        ]
        if unsupported:
            raise SystemExit(f"Unsupported PAK compression for: {unsupported}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the KCD2 Clean Pause development mod")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate an existing release build instead of rebuilding it",
    )
    args = parser.parse_args()

    if args.check:
        validate()
        print(f"OK: {RELEASE_DIR}")
        return

    path = build()
    print(f"Built: {path}")


if __name__ == "__main__":
    main()
