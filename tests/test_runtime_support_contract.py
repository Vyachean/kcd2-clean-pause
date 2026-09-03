import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = (ROOT / "native/src/kcd2_runtime_support.h").read_text(encoding="utf-8")
BUBBLES = (ROOT / "native/src/clean_pause_bubbles.cpp").read_text(encoding="utf-8")
HUD_MASK = (ROOT / "native/src/clean_pause_hud_mask.cpp").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class RuntimeSupportContractTests(unittest.TestCase):
    def test_shared_support_owns_memory_rtti_and_hook_primitives(self):
        for definition in (
            "struct CompleteObjectLocator64",
            "inline bool IsReadable(",
            "inline bool IsExecutable(",
            "inline bool ValidateVtable(",
            "inline bool ResolveCompleteObjectByRtti(",
            "inline bool InstallHook(",
        ):
            self.assertIn(definition, SUPPORT)

        for source in (BUBBLES, HUD_MASK):
            self.assertIn('#include "kcd2_runtime_support.h"', source)
            self.assertNotIn("struct CompleteObjectLocator64", source)
            self.assertNotIn("bool IsReadable(const void*", source)
            self.assertNotIn("bool IsExecutable(const void*", source)
            self.assertNotIn("bool ValidateVtable(void*", source)
            self.assertNotIn("bool ResolveCompleteObjectByRtti(", source)
            self.assertNotIn("bool InstallHook(void*", source)

    def test_shared_hook_helper_rolls_back_failed_enable_completely(self):
        hook = SUPPORT[SUPPORT.index("inline bool InstallHook(") :]
        enable = hook.index("MH_EnableHook(target)")
        remove = hook.index("MH_RemoveHook(target)")
        clear = hook.index("*original = nullptr")
        self.assertLess(enable, remove)
        self.assertLess(remove, clear)
        self.assertIn("installedTarget = target", hook[clear:])

    def test_support_header_is_part_of_both_native_editions(self):
        runtime = CMAKE[
            CMAKE.index("set(CLEAN_PAUSE_RUNTIME_SOURCES") :
            CMAKE.index("function(configure_clean_pause_target")
        ]
        self.assertIn("src/kcd2_runtime_support.h", runtime)
        self.assertGreaterEqual(CMAKE.count("${CLEAN_PAUSE_RUNTIME_SOURCES}"), 2)


if __name__ == "__main__":
    unittest.main()
