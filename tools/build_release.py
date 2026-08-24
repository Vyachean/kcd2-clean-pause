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
from profile_probe_patch import (
    GAMEPLAY_PROBE_ACTION,
    PAUSE_PROBE_ACTION,
    make_diagnostic_profile,
    validate_diagnostic_profile,
)

ROOT = Path(__file__).resolve().parents[1]
PATCHED_PROFILE_PARTS_DIR = (
    ROOT / "vendor" / "kcd2" / "xbox-1.5.6" / "profile.b64.parts"
)

# This is the already CI-verified rc2 source. The diagnostic release derives a
# temporary F10 profile from it at build time; no second copy of the retail XML
# is committed.
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
EXPECTED_RC2_PROFILE_SHA256 = (
    "9838db3747f7f36e0c9c281b8770bc7300998515407515b65493b8e9a9bcd14e"
)


def _read_encoded_rc2_source() -> str:
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


def read_rc2_source_profile() -> bytes:
    encoded = _read_encoded_rc2_source()
    try:
        profile = gzip.decompress(base64.b64decode(encoded, validate=True))
    except (ValueError, OSError) as exc:
        raise ProfilePatchError(f"invalid assembled rc2 profile source: {exc}") from exc

    digest = hashlib.sha256(profile).hexdigest()
    if digest != EXPECTED_RC2_PROFILE_SHA256:
        raise ProfilePatchError(
            "rc2 profile SHA-256 mismatch: "
            f"expected {EXPECTED_RC2_PROFILE_SHA256}, got {digest}"
        )
    return profile


def build() -> Path:
    rc2_profile = read_rc2_source_profile()
    diagnostic_text = make_diagnostic_profile(decode_profile(rc2_profile))
    validate_diagnostic_profile(diagnostic_text)
    diagnostic_profile = diagnostic_text.encode("utf-8")
    diagnostic_digest = hashlib.sha256(diagnostic_profile).hexdigest()

    rendered_lua = render_lua(GAMEPLAY_PROBE_ACTION, PAUSE_PROBE_ACTION)

    if MOD_DIR.exists():
        shutil.rmtree(MOD_DIR)
    MOD_DIR.mkdir(parents=True, exist_ok=True)
    (MOD_DIR / "Data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST, MOD_DIR / "mod.manifest")

    with zipfile.ZipFile(PAK_OUTPUT, "w", compression=zipfile.ZIP_STORED) as pak:
        pak.writestr(VANILLA_PROFILE, diagnostic_profile)
        pak.writestr("Scripts/Mods/clean_pause.lua", rendered_lua.encode("utf-8"))

    validate_build(GAMEPLAY_PROBE_ACTION, PAUSE_PROBE_ACTION)

    if ZIP_OUTPUT.exists():
        ZIP_OUTPUT.unlink()
    with zipfile.ZipFile(ZIP_OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(MOD_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path("clean_pause") / path.relative_to(MOD_DIR))

    archive_digest = hashlib.sha256(ZIP_OUTPUT.read_bytes()).hexdigest()
    print(f"Verified rc2 source profile SHA-256: {EXPECTED_RC2_PROFILE_SHA256}")
    print(f"Derived diagnostic profile SHA-256: {diagnostic_digest}")
    print("Vanilla Escape/Xbox Start activation restored unchanged")
    print("Diagnostic Clean Pause key: F10 (keyboard only)")
    print(f"Built: {ZIP_OUTPUT}")
    print(f"SHA-256: {archive_digest}")
    return ZIP_OUTPUT


def main() -> None:
    try:
        build()
    except (OSError, zipfile.BadZipFile, ProfilePatchError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
