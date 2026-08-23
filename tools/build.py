#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "src"
MANIFEST = ROOT / "mod" / "mod.manifest"
RELEASE_DIR = ROOT / "release" / "clean_pause"
PAK_PATH = RELEASE_DIR / "Data" / "clean_pause.pak"

LUA_ENTRY = "Scripts/Mods/clean_pause.lua"
PROFILE_ENTRY = "Libs/Config/cleanPauseProfile_v22.xml"
PROFILE_VERSION = "22"


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


def validate_profile(xml_bytes: bytes) -> None:
    root = ET.fromstring(xml_bytes)

    if root.tag != "profile":
        raise SystemExit(f"Unexpected action profile root: {root.tag!r}")
    if root.get("version") != PROFILE_VERSION:
        raise SystemExit(
            f"Action profile version must be {PROFILE_VERSION}, got {root.get('version')!r}"
        )

    maps = {node.get("name"): node for node in root.findall("actionmap")}
    controls = maps.get("clean_pause_controls")
    if controls is None:
        raise SystemExit("Missing clean_pause_controls action map")

    actions = {node.get("name"): node for node in controls.findall("action")}
    required_actions = {
        "clean_pause_start": "xi_start",
        "clean_pause_resume": "xi_b",
    }
    for action_name, xbox_input in required_actions.items():
        action = actions.get(action_name)
        if action is None:
            raise SystemExit(f"Missing action: {action_name}")
        if action.get("consoleCmd") != "1" or action.get("onPress") != "1":
            raise SystemExit(f"Action {action_name} must be an onPress console command")
        if action.get("xboxpad") != xbox_input:
            raise SystemExit(
                f"Action {action_name} must use {xbox_input}, got {action.get('xboxpad')!r}"
            )

    filters = {node.get("name"): node for node in root.findall("actionfilter")}

    block = filters.get("clean_pause_block_vanilla_pause")
    if block is None or block.get("type") != "actionFail":
        raise SystemExit("Missing clean_pause_block_vanilla_pause actionFail filter")
    if [node.get("name") for node in block.findall("filter")] != ["ui_start_pause"]:
        raise SystemExit("Vanilla-pause filter must block only ui_start_pause")

    clean_only = filters.get("clean_pause_only")
    if clean_only is None or clean_only.get("type") != "actionPass":
        raise SystemExit("Missing clean_pause_only actionPass filter")
    allowed = {node.get("name") for node in clean_only.findall("filter")}
    if allowed != {"clean_pause_start", "clean_pause_resume"}:
        raise SystemExit(f"Unexpected clean_pause_only allowlist: {sorted(allowed)}")


def validate() -> None:
    if not MANIFEST.is_file():
        raise SystemExit(f"Missing manifest: {MANIFEST}")

    if not PAK_PATH.is_file():
        raise SystemExit(f"Missing pak: {PAK_PATH}")

    with zipfile.ZipFile(PAK_PATH, "r") as pak:
        names = pak.namelist()

        for required in (LUA_ENTRY, PROFILE_ENTRY):
            if required not in names:
                raise SystemExit(f"PAK is missing required entry: {required}")

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

        validate_profile(pak.read(PROFILE_ENTRY))

        lua = pak.read(LUA_ENTRY).decode("utf-8")
        if "SUPPORTED_PROFILE_VERSION = 22" not in lua:
            raise SystemExit("Lua/profile version contract is out of sync")
        if 'CUSTOM_PROFILE = "Libs/Config/cleanPauseProfile_v22.xml"' not in lua:
            raise SystemExit("Lua/profile path contract is out of sync")


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
