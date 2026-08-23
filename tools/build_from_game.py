#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

from profile_patch import ProfilePatchError, patch_profile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "mod" / "mod.manifest"
LUA_SOURCE = ROOT / "src" / "Scripts" / "Mods" / "clean_pause.lua"
RELEASE_ROOT = ROOT / "release"
MOD_DIR = RELEASE_ROOT / "clean_pause"
PAK_OUTPUT = MOD_DIR / "Data" / "clean_pause.pak"
ZIP_OUTPUT = RELEASE_ROOT / "kcd2-clean-pause-xbox-1.5.6-test.zip"
VANILLA_PROFILE = "Libs/Config/defaultProfile.xml"
GAMEPLAY_TOKEN = "__CLEAN_PAUSE_GAMEPLAY_COMMAND__"
PAUSE_TOKEN = "__CLEAN_PAUSE_PAUSE_COMMAND__"


def locate_game_pak(game_root: Path) -> Path:
    game_root = game_root.expanduser().resolve()
    candidates = (
        game_root / "Data" / "IPL_GameData.pak",
        game_root / "data" / "IPL_GameData.pak",
        game_root / "IPL_GameData.pak",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"IPL_GameData.pak not found under {game_root}; pass the KCD2 folder that contains Data"
    )


def read_pak_member(pak_path: Path, member: str) -> bytes:
    with zipfile.ZipFile(pak_path, "r") as pak:
        by_lower = {name.lower(): name for name in pak.namelist()}
        real_name = by_lower.get(member.lower())
        if real_name is None:
            raise ProfilePatchError(f"{pak_path.name} does not contain {member}")
        return pak.read(real_name)


def decode_profile(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ProfilePatchError("defaultProfile.xml is not UTF-8; refusing to rewrite unknown encoding")


def _safe_command(name: str) -> str:
    if not name or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in name):
        raise ProfilePatchError(f"unsafe routed command name: {name!r}")
    return name


def render_lua(gameplay_action: str, pause_action: str) -> str:
    gameplay_action = _safe_command(gameplay_action)
    pause_action = _safe_command(pause_action)
    source = LUA_SOURCE.read_text(encoding="utf-8")
    if source.count(GAMEPLAY_TOKEN) != 1 or source.count(PAUSE_TOKEN) != 1:
        raise ProfilePatchError("runtime routed-command placeholder contract changed")
    return source.replace(GAMEPLAY_TOKEN, gameplay_action).replace(PAUSE_TOKEN, pause_action)


def inspect_game(game_root: Path) -> tuple[Path, str, object]:
    pak_path = locate_game_pak(game_root)
    vanilla_bytes = read_pak_member(pak_path, VANILLA_PROFILE)
    vanilla_text = decode_profile(vanilla_bytes)
    patched, info = patch_profile(vanilla_text)
    return pak_path, patched, info


def build(game_root: Path) -> Path:
    pak_path, patched_profile, info = inspect_game(game_root)
    rendered_lua = render_lua(info.gameplay.action_name, info.pause.action_name)

    if MOD_DIR.exists():
        shutil.rmtree(MOD_DIR)
    MOD_DIR.mkdir(parents=True, exist_ok=True)
    (MOD_DIR / "Data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST, MOD_DIR / "mod.manifest")

    with zipfile.ZipFile(PAK_OUTPUT, "w", compression=zipfile.ZIP_STORED) as pak:
        pak.writestr(VANILLA_PROFILE, patched_profile.encode("utf-8"))
        pak.writestr("Scripts/Mods/clean_pause.lua", rendered_lua.encode("utf-8"))

    validate_build(info.gameplay.action_name, info.pause.action_name)

    if ZIP_OUTPUT.exists():
        ZIP_OUTPUT.unlink()
    with zipfile.ZipFile(ZIP_OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(MOD_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path("clean_pause") / path.relative_to(MOD_DIR))

    digest = hashlib.sha256(ZIP_OUTPUT.read_bytes()).hexdigest()
    print(f"Game data: {pak_path}")
    print(f"Profile version: {info.profile_version}")
    print(
        "Routed Start actions: "
        f"{info.gameplay.map_name}/{info.gameplay.action_name}, "
        f"{info.pause.map_name}/{info.pause.action_name}"
    )
    print(f"Built: {ZIP_OUTPUT}")
    print(f"SHA-256: {digest}")
    return ZIP_OUTPUT


def validate_build(gameplay_action: str, pause_action: str) -> None:
    if not PAK_OUTPUT.is_file():
        raise ProfilePatchError(f"missing generated PAK: {PAK_OUTPUT}")

    with zipfile.ZipFile(PAK_OUTPUT, "r") as pak:
        names = set(pak.namelist())
        expected = {VANILLA_PROFILE, "Scripts/Mods/clean_pause.lua"}
        if names != expected:
            raise ProfilePatchError(f"unexpected generated PAK members: {sorted(names)}")
        if any(pak.getinfo(name).compress_type != zipfile.ZIP_STORED for name in names):
            raise ProfilePatchError("generated game PAK must use stored entries")

        profile = decode_profile(pak.read(VANILLA_PROFILE))
        try:
            patch_profile(profile)
        except ProfilePatchError as exc:
            if "already contains Clean Pause additions" not in str(exc):
                raise
        else:
            raise ProfilePatchError("generated profile did not retain Clean Pause markers")

        lua = pak.read("Scripts/Mods/clean_pause.lua").decode("utf-8")
        if GAMEPLAY_TOKEN in lua or PAUSE_TOKEN in lua:
            raise ProfilePatchError("generated Lua still contains a routed-command placeholder")
        if f'local GAMEPLAY_COMMAND = "{gameplay_action}"' not in lua:
            raise ProfilePatchError("generated Lua gameplay command does not match patched profile")
        if f'local PAUSE_COMMAND = "{pause_action}"' not in lua:
            raise ProfilePatchError("generated Lua pause command does not match patched profile")
        forbidden = (
            "ActionMapManager.InitActionMaps(",
            "ActionMapManager.LoadFromXML(",
            "ActionMapManager.EnableActionFilter(",
            "Player.OnAction =",
        )
        for needle in forbidden:
            if needle in lua:
                raise ProfilePatchError(f"forbidden runtime input mutation found: {needle}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build KCD2 Clean Pause from the installed game's exact defaultProfile.xml"
    )
    parser.add_argument(
        "game_root",
        type=Path,
        help="KCD2 installation folder containing Data/IPL_GameData.pak",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="validate the known Xbox 1.5.6 Start routes without writing a mod",
    )
    args = parser.parse_args()

    try:
        if args.inspect_only:
            pak_path, _patched, info = inspect_game(args.game_root)
            print(f"Game data: {pak_path}")
            print(f"Profile version: {info.profile_version}")
            print(
                "Routed Start actions: "
                f"{info.gameplay.map_name}/{info.gameplay.action_name}, "
                f"{info.pause.map_name}/{info.pause.action_name}"
            )
        else:
            build(args.game_root)
    except (FileNotFoundError, zipfile.BadZipFile, ProfilePatchError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
