#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import zipfile

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_from_game import (  # noqa: E402
    MANIFEST,
    MOD_DIR,
    PAK_OUTPUT,
    VANILLA_PROFILE,
    ZIP_OUTPUT,
    decode_profile,
    render_lua,
    validate_build,
)
from profile_patch import ProfilePatchError, patch_profile  # noqa: E402


def prepare_profile(profile_path: Path) -> tuple[bytes, str, str, object]:
    profile_path = profile_path.expanduser().resolve()
    if not profile_path.is_file():
        raise FileNotFoundError(f"defaultProfile.xml not found: {profile_path}")

    source_bytes = profile_path.read_bytes()
    source_text = decode_profile(source_bytes)
    patched_profile, info = patch_profile(source_text)
    rendered_lua = render_lua(info.gameplay.entry_action_name, info.pause.entry_action_name)
    return source_bytes, patched_profile, rendered_lua, info


def build(profile_path: Path) -> Path:
    source_bytes, patched_profile, rendered_lua, info = prepare_profile(profile_path)

    if MOD_DIR.exists():
        shutil.rmtree(MOD_DIR)
    MOD_DIR.mkdir(parents=True, exist_ok=True)
    (MOD_DIR / "Data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST, MOD_DIR / "mod.manifest")

    with zipfile.ZipFile(PAK_OUTPUT, "w", compression=zipfile.ZIP_STORED) as pak:
        pak.writestr(VANILLA_PROFILE, patched_profile.encode("utf-8"))
        pak.writestr("Scripts/Mods/clean_pause.lua", rendered_lua.encode("utf-8"))

    validate_build(info.gameplay.entry_action_name, info.pause.entry_action_name)

    if ZIP_OUTPUT.exists():
        ZIP_OUTPUT.unlink()
    with zipfile.ZipFile(ZIP_OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(MOD_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path("clean_pause") / path.relative_to(MOD_DIR))

    profile_digest = hashlib.sha256(source_bytes).hexdigest()
    archive_digest = hashlib.sha256(ZIP_OUTPUT.read_bytes()).hexdigest()
    print(f"Source profile: {profile_path.expanduser().resolve()}")
    print(f"Source profile SHA-256: {profile_digest}")
    print(f"Profile version: {info.profile_version}")
    print(
        "Clean Pause entry actions: "
        f"{info.gameplay.map_name}/{info.gameplay.entry_action_name}, "
        f"{info.pause.map_name}/{info.pause.entry_action_name}"
    )
    print("Vanilla release fallbacks retained: open_menu, open_pause_menu")
    print(f"Built: {ZIP_OUTPUT}")
    print(f"SHA-256: {archive_digest}")
    return ZIP_OUTPUT


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build KCD2 Clean Pause from an extracted retail defaultProfile.xml"
    )
    parser.add_argument(
        "profile",
        type=Path,
        help="Path to the exact Libs/Config/defaultProfile.xml extracted from the target game",
    )
    args = parser.parse_args()

    try:
        build(args.profile)
    except (FileNotFoundError, ProfilePatchError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
