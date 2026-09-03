import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")


def function_body(start: str, end: str) -> str:
    return NATIVE[NATIVE.index(start):NATIVE.index(end, NATIVE.index(start))]


class MinHookRollbackContractTests(unittest.TestCase):
    def test_created_hooks_are_removed_when_enable_fails(self):
        cases = (
            (
                "bool EnsureHudSubtitleHook()",
                "void ResetHudSnapshots()",
                "MH_EnableHook(target)",
                "MH_RemoveHook(target);",
                "g_originalHudCallFunction = nullptr;",
            ),
            (
                "bool EnsureHudUpdateHook()",
                "void __fastcall HookMenuRender",
                "MH_EnableHook(target)",
                "MH_RemoveHook(target);",
                "g_originalHudUpdate = nullptr;",
            ),
            (
                "bool EnsureMenuRenderHook()",
                "bool ReadVerifiedMenuVisible",
                "MH_EnableHook(renderTarget)",
                "MH_RemoveHook(renderTarget);",
                "g_originalRender = nullptr;",
            ),
            (
                "bool InstallInputHook(const RuntimeEnvironment& environment)",
                "DWORD WINAPI BootstrapThread",
                "MH_EnableHook(g_postInputEventTarget)",
                "MH_RemoveHook(g_postInputEventTarget);",
                "g_originalPostInputEvent = nullptr;",
            ),
        )

        for start, end, enable, remove, reset in cases:
            with self.subTest(function=start):
                body = function_body(start, end)
                self.assertIn(enable, body)
                self.assertIn(remove, body)
                self.assertIn(reset, body)
                self.assertLess(body.index(enable), body.index(remove))
                self.assertLess(body.index(remove), body.index(reset))


if __name__ == "__main__":
    unittest.main()
