#!/usr/bin/env python3
"""Mechanically materialize the current profiled translation unit as normal source.

This is a one-shot migration helper for issue #45. It preserves the symbol
substitution performed by clean_pause_native_profiled.cpp, then appends the
profiled bootstrap/capability implementation without textual .cpp inclusion.
It intentionally does not redesign runtime behavior.
"""

from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native/src/clean_pause_native.cpp"
PROFILED = ROOT / "native/src/clean_pause_native_profiled.cpp"
CMAKE = ROOT / "native/CMakeLists.txt"

RENAMES = {
    "Start": "LegacyStart_Unreachable",
    "Stop": "LegacyStop_Unreachable",
    "BootstrapThread": "LegacyBootstrapThread_Unreachable",
    "FindRuntimeEnvironment": "LegacyFindRuntimeEnvironment_Xbox156Only",
    "ResolveGameFramework": "LegacyResolveGameFramework_Xbox156Only",
    "InstallPauseBarrierHook": "LegacyInstallPauseBarrierHook_Xbox156Only",
    "InstallInputHook": "LegacyInstallInputHook_Xbox156Only",
    "HookPostInputEvent": "LegacyHookPostInputEventProfiledCore",
}

PROFILE_TAIL_MARKER = "namespace clean_pause {\nnamespace {\n"
INCLUDE_MARKER = '#include "clean_pause_native.cpp"'


def replace_identifiers(text: str) -> str:
    """Apply the wrapper's identifier macros outside comments and literals."""
    out: list[str] = []
    i = 0
    n = len(text)
    state = "code"

    while i < n:
        if state == "code":
            if text.startswith("//", i):
                out.append("//")
                i += 2
                state = "line_comment"
                continue
            if text.startswith("/*", i):
                out.append("/*")
                i += 2
                state = "block_comment"
                continue
            ch = text[i]
            if ch == '"':
                out.append(ch)
                i += 1
                state = "string"
                continue
            if ch == "'":
                out.append(ch)
                i += 1
                state = "char"
                continue
            if ch == "_" or ch.isalpha():
                j = i + 1
                while j < n and (text[j] == "_" or text[j].isalnum()):
                    j += 1
                token = text[i:j]
                out.append(RENAMES.get(token, token))
                i = j
                continue
            out.append(ch)
            i += 1
            continue

        if state == "line_comment":
            ch = text[i]
            out.append(ch)
            i += 1
            if ch == "\n":
                state = "code"
            continue

        if state == "block_comment":
            if text.startswith("*/", i):
                out.append("*/")
                i += 2
                state = "code"
            else:
                out.append(text[i])
                i += 1
            continue

        if state in {"string", "char"}:
            ch = text[i]
            out.append(ch)
            i += 1
            if ch == "\\" and i < n:
                out.append(text[i])
                i += 1
                continue
            if (state == "string" and ch == '"') or (state == "char" and ch == "'"):
                state = "code"
            continue

    if state in {"block_comment", "string", "char"}:
        raise RuntimeError(f"unterminated C++ lexical state: {state}")
    return "".join(out)


def migrate() -> bool:
    if not PROFILED.exists():
        print("profiled wrapper already absent; nothing to migrate")
        return False

    core = CORE.read_text(encoding="utf-8")
    profiled = PROFILED.read_text(encoding="utf-8")
    if INCLUDE_MARKER not in profiled:
        raise RuntimeError("profiled wrapper include marker not found")
    marker_index = profiled.find(PROFILE_TAIL_MARKER, profiled.index(INCLUDE_MARKER))
    if marker_index < 0:
        raise RuntimeError("profiled implementation tail marker not found")

    transformed_core = replace_identifiers(core)
    if '#include "kcd2_runtime_profile.h"' not in transformed_core:
        transformed_core = '#include "kcd2_runtime_profile.h"\n' + transformed_core

    tail = profiled[marker_index:]
    unified = transformed_core.rstrip() + "\n\n" + tail.lstrip()

    # Guard against accidentally preserving the mechanism being removed.
    for forbidden in (
        '#include "clean_pause_native.cpp"',
        "#define Start LegacyStart_Unreachable",
        "#define HookPostInputEvent LegacyHookPostInputEventProfiledCore",
    ):
        if forbidden in unified:
            raise RuntimeError(f"forbidden wrapper mechanism survived: {forbidden}")

    for required in (
        "LegacyFindRuntimeEnvironment_Xbox156Only",
        "LegacyResolveGameFramework_Xbox156Only",
        "LegacyHookPostInputEventProfiledCore",
        "ResolveSteamFrameworkSingleton",
        "HookPostInputEventProfiled",
        "bool Start(HMODULE selfModule)",
    ):
        if required not in unified:
            raise RuntimeError(f"required migrated symbol missing: {required}")

    CORE.write_text(unified, encoding="utf-8")
    PROFILED.unlink()

    cmake = CMAKE.read_text(encoding="utf-8")
    old = """  # Production entry compiles the mature runtime through a small profiled wrapper\n  # that replaces only build gating/environment discovery. Do not compile\n  # clean_pause_native.cpp separately: it is included by this translation unit.\n  src/clean_pause_native_profiled.cpp\n"""
    new = """  # The accepted profiled runtime is represented directly as normal source.\n  # Storefront/build discovery and the shared Clean Pause core remain behaviorally\n  # unchanged while issue #45 proceeds toward a smaller private API boundary.\n  src/clean_pause_native.cpp\n"""
    if old not in cmake:
        raise RuntimeError("expected profiled CMake source block not found")
    cmake = cmake.replace(old, new, 1)
    CMAKE.write_text(cmake, encoding="utf-8")
    return True


if __name__ == "__main__":
    changed = migrate()
    print("runtime wrapper migration complete" if changed else "no migration needed")
