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
    B_PRESS_ACTION,
    CONSOLE_COMMAND_ATTR,
    CONTROLS_MAP,
    DEFAULT_KEYBOARD_PAUSE_INPUT,
    GAMEPLAY_ENTRY_ACTION,
    MENU_ACTION,
    PAUSE_ENTRY_ACTION,
    RESUME_ACTION,
    START_RELEASE_BLOCK_ACTION,
    ProfilePatchError,
)

ROOT = Path(__file__).resolve().parents[1]
PATCHED_PROFILE_PARTS_DIR = (
    ROOT / "vendor" / "kcd2" / "xbox-1.5.6" / "profile.b64.parts"
)
EXPECTED_PART_SHA256 = {
    "00.txt": "7b8fc4053dc408a0783a5b53857b9640358cab25e0b144e690de05e891d6d681",
    "01.txt": "e823cf557248c2a6fc2ae76fc2de1c2b8414d398fe5e1cf89c10f46dac1c5892",
    "02.txt": "ff4885d1bf7036eade092fa1f901310f6867e2ef7f1aa4e1e5493e7237297a53",
    "03.txt": "4c8420f4fb0935cb283aeace522e0b97fd8fc52d24c6e673666dfe04365c7849",
    "04.txt": "89a849ffbaef2f204277771dd89dc998a734b2c66db545030c069528edac861d",
    "05.txt": "7bd04edb4e07490879482547515dc2d304f6de8e85cfdceaf43a695f298d0297",
    "06.txt": "78f0b00825e96bd5bb77a30dbbbc6f668a47a062ff49d1a4109bd04bbc2e6b52",
    "07.txt": "a5517364ae06791ead5038f129c1902d84f22bdee74bc2645bc484d43f9364b2",
}
EXPECTED_ENCODED_SHA256 = (
    "01b70dab6d8cfbdb502bfd683d4341ef9121c9a22b0440c06653e946413c9880"
)
EXPECTED_PATCHED_PROFILE_SHA256 = (
    "9838db3747f7f36e0c9c281b8770bc7300998515407515b65493b8e9a9bcd14e"
)


def _action(root: ET.Element, map_name: str, action_name: str) -> ET.Element:
    maps = [m for m in root.findall("actionmap") if m.get("name") == map_name]
    if len(maps) != 1:
        raise ProfilePatchError(f"release profile has unexpected action map count: {map_name}")
    actions = [a for a in maps[0].findall("action") if a.get("name") == action_name]
    if len(actions) != 1:
        raise ProfilePatchError(
            f"release profile has unexpected action count: {map_name}/{action_name}"
        )
    return actions[0]


def _require_console_command(action: ET.Element, label: str) -> None:
    if action.get(CONSOLE_COMMAND_ATTR) != "1":
        raise ProfilePatchError(f"{label} is missing exact {CONSOLE_COMMAND_ATTR}=1")
    if action.get("consoleCmd") is not None:
        raise ProfilePatchError(f"{label} contains wrong-case consoleCmd attribute")


def _require_vanilla_release_fallback(action: ET.Element, label: str) -> None:
    if action.get("onRelease") != "1" or action.get("onPress") is not None:
        raise ProfilePatchError(f"{label} is not release-only vanilla fallback")
    if action.get(CONSOLE_COMMAND_ATTR) is not None or action.get("consoleCmd") is not None:
        raise ProfilePatchError(f"{label} must not be a console command")
    if action.get("keyboard") != "_keybinds_ref_" or action.get("xboxpad") != "xi_start":
        raise ProfilePatchError(f"{label} lost the retail pause bindings")


def _validate_release_profile_contract(profile_text: str) -> None:
    try:
        root = ET.fromstring(profile_text)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"release profile is invalid XML: {exc}") from exc

    _require_vanilla_release_fallback(
        _action(root, "open_menu", "open_menu"), "open_menu/open_menu"
    )
    _require_vanilla_release_fallback(
        _action(root, "open_pause_menu", "open_pause_menu"),
        "open_pause_menu/open_pause_menu",
    )

    for map_name, entry_name in (
        ("open_menu", GAMEPLAY_ENTRY_ACTION),
        ("open_pause_menu", PAUSE_ENTRY_ACTION),
    ):
        entry = _action(root, map_name, entry_name)
        if entry.get("onPress") != "1" or entry.get("onRelease") is not None:
            raise ProfilePatchError(f"{map_name}/{entry_name} is not press-only")
        if entry.get("keyboard") != DEFAULT_KEYBOARD_PAUSE_INPUT:
            raise ProfilePatchError(f"{map_name}/{entry_name} does not bind Escape")
        if entry.get("xboxpad") != "xi_start":
            raise ProfilePatchError(f"{map_name}/{entry_name} does not bind Xbox Start")
        _require_console_command(entry, f"{map_name}/{entry_name}")

    controls = [m for m in root.findall("actionmap") if m.get("name") == CONTROLS_MAP]
    if len(controls) != 1:
        raise ProfilePatchError("release profile is missing clean_pause_controls")
    if controls[0].get("priority") != "overlays" or controls[0].get("exclusivity") != "1":
        raise ProfilePatchError("release controls map must be exclusive at overlays priority")
    actions = {a.get("name"): a for a in controls[0].findall("action")}
    if set(actions) != {
        MENU_ACTION,
        START_RELEASE_BLOCK_ACTION,
        B_PRESS_ACTION,
        RESUME_ACTION,
    }:
        raise ProfilePatchError("release controls map action set changed unexpectedly")

    _require_console_command(actions[MENU_ACTION], MENU_ACTION)
    if actions[MENU_ACTION].get("onPress") != "1":
        raise ProfilePatchError("menu handoff must run on Start/Escape press")

    start_release = actions[START_RELEASE_BLOCK_ACTION]
    if (
        start_release.get("onRelease") != "1"
        or start_release.get("onPress") is not None
        or start_release.get(CONSOLE_COMMAND_ATTR) is not None
    ):
        raise ProfilePatchError("Start/Escape release sink contract changed")

    b_press = actions[B_PRESS_ACTION]
    if b_press.get("onPress") != "1" or b_press.get(CONSOLE_COMMAND_ATTR) is not None:
        raise ProfilePatchError("B press sink contract changed")

    _require_console_command(actions[RESUME_ACTION], RESUME_ACTION)
    if actions[RESUME_ACTION].get("onRelease") != "1":
        raise ProfilePatchError("B resume must run on release")

    no_menu = next(
        (f for f in root.findall("actionfilter") if f.get("name") == "no_menu"), None
    )
    if no_menu is None:
        raise ProfilePatchError("release profile lost retail no_menu filter")
    no_menu_names = {a.get("name") for a in no_menu.findall("action")}
    if "open_menu" not in no_menu_names or GAMEPLAY_ENTRY_ACTION not in no_menu_names:
        raise ProfilePatchError("no_menu filter does not mirror the Clean Pause gameplay entry")


def _read_encoded_release_source() -> str:
    if not PATCHED_PROFILE_PARTS_DIR.is_dir():
        raise ProfilePatchError(
            f"missing release-profile parts directory: {PATCHED_PROFILE_PARTS_DIR}"
        )

    actual_names = {path.name for path in PATCHED_PROFILE_PARTS_DIR.glob("*.txt")}
    expected_names = set(EXPECTED_PART_SHA256)
    if actual_names != expected_names:
        raise ProfilePatchError(
            "release-profile chunk set mismatch: "
            f"expected {sorted(expected_names)}, got {sorted(actual_names)}"
        )

    chunks: list[str] = []
    for name in sorted(EXPECTED_PART_SHA256):
        path = PATCHED_PROFILE_PARTS_DIR / name
        chunk = path.read_text(encoding="ascii")
        if any(ch.isspace() for ch in chunk):
            raise ProfilePatchError(f"release-profile chunk {name} contains whitespace")
        digest = hashlib.sha256(chunk.encode("ascii")).hexdigest()
        if digest != EXPECTED_PART_SHA256[name]:
            raise ProfilePatchError(
                f"release-profile chunk {name} SHA-256 mismatch: "
                f"expected {EXPECTED_PART_SHA256[name]}, got {digest}"
            )
        chunks.append(chunk)

    encoded = "".join(chunks)
    digest = hashlib.sha256(encoded.encode("ascii")).hexdigest()
    if digest != EXPECTED_ENCODED_SHA256:
        raise ProfilePatchError(
            "assembled release-profile source SHA-256 mismatch: "
            f"expected {EXPECTED_ENCODED_SHA256}, got {digest}"
        )
    return encoded


def read_release_profile() -> bytes:
    encoded = _read_encoded_release_source()
    try:
        compressed = base64.b64decode(encoded, validate=True)
        profile = gzip.decompress(compressed)
    except (ValueError, OSError) as exc:
        raise ProfilePatchError(f"invalid assembled release profile source: {exc}") from exc

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
    rendered_lua = render_lua(GAMEPLAY_ENTRY_ACTION, PAUSE_ENTRY_ACTION)

    if MOD_DIR.exists():
        shutil.rmtree(MOD_DIR)
    MOD_DIR.mkdir(parents=True, exist_ok=True)
    (MOD_DIR / "Data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST, MOD_DIR / "mod.manifest")

    with zipfile.ZipFile(PAK_OUTPUT, "w", compression=zipfile.ZIP_STORED) as pak:
        pak.writestr(VANILLA_PROFILE, profile)
        pak.writestr("Scripts/Mods/clean_pause.lua", rendered_lua.encode("utf-8"))

    validate_build(GAMEPLAY_ENTRY_ACTION, PAUSE_ENTRY_ACTION)

    if ZIP_OUTPUT.exists():
        ZIP_OUTPUT.unlink()
    with zipfile.ZipFile(ZIP_OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(MOD_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path("clean_pause") / path.relative_to(MOD_DIR))

    digest = hashlib.sha256(ZIP_OUTPUT.read_bytes()).hexdigest()
    print(f"Release profile parts: {PATCHED_PROFILE_PARTS_DIR}")
    print(f"Release profile SHA-256: {EXPECTED_PATCHED_PROFILE_SHA256}")
    print("Target: KCD2 Xbox Store / Xbox app / Game Pass 1.5.6")
    print(
        "Clean Pause entry actions: "
        f"open_menu/{GAMEPLAY_ENTRY_ACTION}, open_pause_menu/{PAUSE_ENTRY_ACTION}"
    )
    print("Vanilla release fallbacks retained: open_menu, open_pause_menu")
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
