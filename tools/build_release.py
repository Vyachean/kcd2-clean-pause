#!/usr/bin/env python3

from __future__ import annotations

import base64
import gzip
import hashlib
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import zipfile

from build_from_game import (
    MANIFEST,
    MOD_DIR,
    PAK_OUTPUT,
    VANILLA_PROFILE,
    ZIP_OUTPUT,
    decode_profile,
    render_lua,
    validate_build,
)
from profile_patch import (
    CONSOLE_COMMAND_ATTR,
    CONTROLS_MAP,
    MENU_ACTION,
    RESUME_ACTION,
    ProfilePatchError,
)

ROOT = Path(__file__).resolve().parents[1]
PATCHED_PROFILE_SOURCE = (
    ROOT / "vendor" / "kcd2" / "xbox-1.5.6" / "defaultProfile.clean-pause.xml.gz.b64"
)
EXPECTED_PATCHED_PROFILE_SHA256 = (
    "6e92323a53b8a42c15a1b8dd217f71dd5e4939e93b6792dbd8d9bde4b7b519e3"
)


def _require_console_command(action: ET.Element, label: str) -> None:
    if action.get(CONSOLE_COMMAND_ATTR) != "1":
        raise ProfilePatchError(f"{label} is missing exact {CONSOLE_COMMAND_ATTR}=1")
    if action.get("consoleCmd") is not None:
        raise ProfilePatchError(f"{label} contains wrong-case consoleCmd attribute")


def _validate_release_profile_contract(profile_text: str) -> None:
    try:
        root = ET.fromstring(profile_text)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"release profile is invalid XML: {exc}") from exc

    def routed(map_name: str, action_name: str) -> ET.Element:
        maps = [m for m in root.findall("actionmap") if m.get("name") == map_name]
        if len(maps) != 1:
            raise ProfilePatchError(f"release profile has unexpected action map count: {map_name}")
        actions = [a for a in maps[0].findall("action") if a.get("name") == action_name]
        if len(actions) != 1:
            raise ProfilePatchError(f"release profile has unexpected routed action count: {map_name}/{action_name}")
        return actions[0]

    _require_console_command(routed("open_menu", "open_menu"), "open_menu/open_menu")
    _require_console_command(
        routed("open_pause_menu", "open_pause_menu"),
        "open_pause_menu/open_pause_menu",
    )

    controls = [m for m in root.findall("actionmap") if m.get("name") == CONTROLS_MAP]
    if len(controls) != 1:
        raise ProfilePatchError("release profile is missing clean_pause_controls")
    actions = {a.get("name"): a for a in controls[0].findall("action")}
    if MENU_ACTION not in actions or RESUME_ACTION not in actions:
        raise ProfilePatchError("release profile is missing Clean Pause console actions")
    _require_console_command(actions[MENU_ACTION], MENU_ACTION)
    _require_console_command(actions[RESUME_ACTION], RESUME_ACTION)


def read_release_profile() -> bytes:
    if not PATCHED_PROFILE_SOURCE.is_file():
        raise ProfilePatchError(f"missing release profile source: {PATCHED_PROFILE_SOURCE}")

    try:
        compressed = base64.b64decode(
            PATCHED_PROFILE_SOURCE.read_text(encoding="ascii").strip(), validate=True
        )
        profile = gzip.decompress(compressed)
    except (ValueError, OSError) as exc:
        raise ProfilePatchError(f"invalid release profile source: {exc}") from exc

    digest = hashlib.sha256(profile).hexdigest()
    if digest != EXPECTED_PATCHED_PROFILE_SHA256:
        raise ProfilePatchError(
            "release profile SHA-256 mismatch: "
            f"expected {EXPECTED_PATCHED_PROFILE_SHA256}, got {digest}"
        )

    profile_text = decode_profile(profile)
    _validate_release_profile_contract(profile_text)
    return profile


def build() -> Path:
    profile = read_release_profile()
    rendered_lua = render_lua("open_menu", "open_pause_menu")

    if MOD_DIR.exists():
        shutil.rmtree(MOD_DIR)
    MOD_DIR.mkdir(parents=True, exist_ok=True)
    (MOD_DIR / "Data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST, MOD_DIR / "mod.manifest")

    with zipfile.ZipFile(PAK_OUTPUT, "w", compression=zipfile.ZIP_STORED) as pak:
        pak.writestr(VANILLA_PROFILE, profile)
        pak.writestr("Scripts/Mods/clean_pause.lua", rendered_lua.encode("utf-8"))

    validate_build("open_menu", "open_pause_menu")

    if ZIP_OUTPUT.exists():
        ZIP_OUTPUT.unlink()
    with zipfile.ZipFile(ZIP_OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(MOD_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path("clean_pause") / path.relative_to(MOD_DIR))

    digest = hashlib.sha256(ZIP_OUTPUT.read_bytes()).hexdigest()
    print(f"Release profile source: {PATCHED_PROFILE_SOURCE}")
    print(f"Release profile SHA-256: {EXPECTED_PATCHED_PROFILE_SHA256}")
    print("Target: KCD2 Xbox Store / Xbox app / Game Pass 1.5.6")
    print("Routed Start actions: open_menu/open_menu, open_pause_menu/open_pause_menu")
    print(f"Built: {ZIP_OUTPUT}")
    print(f"SHA-256: {digest}")
    return ZIP_OUTPUT


def main() -> None:
    try:
        build()
    except (OSError, zipfile.BadZipFile, ProfilePatchError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
