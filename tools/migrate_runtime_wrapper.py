#!/usr/bin/env python3
"""One-shot cleanup after materializing the profiled runtime for issue #45.

The wrapper has already been expanded into clean_pause_native.cpp. This helper
removes only dead symbols that existed because of the old textual-include/macro
composition and gives the retained shared input core a normal name. Xbox 1.5.6
legacy discovery/framework adapters remain because the profiled runtime still
uses them intentionally.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native/src/clean_pause_native.cpp"


def cut(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"cleanup start marker not found: {start_marker}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"cleanup end marker not found: {end_marker}")
    return text[:start] + text[end:]


def cleanup() -> bool:
    text = CORE.read_text(encoding="utf-8")
    original = text

    # The profiled BootstrapThread logs the selected profile fingerprint directly;
    # this helper was used only by the now-dead legacy bootstrap.
    text = cut(
        text,
        "void LogWhGameFingerprint(HMODULE whGame)\n{",
        "bool LegacyFindRuntimeEnvironment_Xbox156Only",
    )

    # The active profiled path owns PauseGame/input installation. Keep only the
    # runtime-tested Xbox discovery/framework adapters used by that path.
    text = cut(
        text,
        "void __fastcall HookPauseGame(\n",
        "DWORD WINAPI LegacyBootstrapThread_Unreachable",
    )
    text = cut(
        text,
        "DWORD WINAPI LegacyBootstrapThread_Unreachable(void*)\n{",
        "} // namespace\n\nbool LegacyStart_Unreachable",
    )
    text = cut(
        text,
        "bool LegacyStart_Unreachable(HMODULE selfModule)\n{",
        "} // namespace clean_pause\n\nnamespace clean_pause {",
    )

    text = text.replace(
        "LegacyHookPostInputEventProfiledCore",
        "HookPostInputEventCore",
    )
    text = text.replace("the legacy core", "the shared core")
    text = text.replace("legacy core performs", "shared core performs")

    forbidden = (
        "LegacyStart_Unreachable",
        "LegacyStop_Unreachable",
        "LegacyBootstrapThread_Unreachable",
        "LegacyInstallPauseBarrierHook_Xbox156Only",
        "LegacyInstallInputHook_Xbox156Only",
        "LegacyHookPostInputEventProfiledCore",
        "void __fastcall HookPauseGame(\n",
        "void LogWhGameFingerprint(HMODULE whGame)",
        '#include "clean_pause_native.cpp"',
    )
    for token in forbidden:
        if token in text:
            raise RuntimeError(f"dead wrapper artifact survived cleanup: {token}")

    required = (
        "LegacyFindRuntimeEnvironment_Xbox156Only",
        "LegacyResolveGameFramework_Xbox156Only",
        "void __fastcall HookPostInputEventCore",
        "void __fastcall HookPostInputEventProfiled",
        "void __fastcall HookPauseGameProfiled",
        "DWORD WINAPI BootstrapThread(void*)",
        "bool Start(HMODULE selfModule)",
        "void Stop()",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"required runtime symbol missing after cleanup: {token}")

    if text == original:
        print("no cleanup needed")
        return False

    CORE.write_text(text, encoding="utf-8")
    print("materialized runtime cleanup complete")
    return True


if __name__ == "__main__":
    cleanup()
