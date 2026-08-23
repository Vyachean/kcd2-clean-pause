#!/usr/bin/env python3

from __future__ import annotations

import base64
import gzip
import hashlib
from pathlib import Path
import shutil
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
from profile_patch import ProfilePatchError

ROOT = Path(__file__).resolve().parents[1]
PATCHED_PROFILE_SOURCE = (
    ROOT / "vendor" / "kcd2" / "xbox-1.5.6" / "defaultProfile.clean-pause.xml.gz.b64"
)
EXPECTED_PATCHED_PROFILE_SHA256 = (
    "28e210454d749869b1fa26d4414ba3c055157e731856f9610d6ffce5ddfbc373"
)


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

    # Fail early if the versioned source is no longer valid UTF-8 XML text.
    decode_profile(profile)
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
