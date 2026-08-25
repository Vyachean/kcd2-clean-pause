import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
BLUR = (ROOT / "native/src/clean_pause_blur.cpp").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class BlurContractTests(unittest.TestCase):
    def test_blur_controller_is_shared_by_both_editions(self):
        self.assertIn("src/clean_pause_blur.cpp", CMAKE)
        self.assertIn("src/clean_pause_blur.h", CMAKE)
        self.assertGreaterEqual(CMAKE.count("${CLEAN_PAUSE_RUNTIME_SOURCES}"), 2)

    def test_disable_snapshots_and_disables_both_dof_controls(self):
        self.assertIn('System.GetCVar("wh_cl_NearDof")', BLUR)
        self.assertIn('System.GetCVar("r_DepthOfField")', BLUR)
        self.assertNotIn("System.GetCVarValue", BLUR)
        self.assertIn('System.SetCVar("wh_cl_NearDof", 0)', BLUR)
        self.assertIn('System.SetCVar("r_DepthOfField", 0)', BLUR)

    def test_restore_replays_saved_values_instead_of_forcing_defaults(self):
        self.assertIn(
            'System.SetCVar("wh_cl_NearDof", __kcd2_clean_pause_prev_near_dof)',
            BLUR,
        )
        self.assertIn(
            'System.SetCVar("r_DepthOfField", __kcd2_clean_pause_prev_depth_of_field)',
            BLUR,
        )
        restore = BLUR[BLUR.index("constexpr const char* kRestoreScript"):]
        self.assertNotIn('System.SetCVar("wh_cl_NearDof", 1)', restore)
        self.assertNotIn('System.SetCVar("r_DepthOfField", 1)', restore)

    def test_clean_pause_requires_blur_suppression_before_ownership(self):
        enter = NATIVE[
            NATIVE.index("bool TryEnterCleanPause") : NATIVE.index("void HandleHiddenInput")
        ]
        self.assertLess(
            enter.index("if (!blur::Disable())"),
            enter.index("g_cleanHidden.store(true"),
        )
        self.assertIn("leaving ordinary visible pause menu (fail-open)", enter)

    def test_visible_menu_handoffs_restore_before_render_ownership_is_released(self):
        hidden = NATIVE[
            NATIVE.index("void HandleHiddenInput") : NATIVE.index("void __fastcall HookPostInputEvent")
        ]
        start_block = hidden[
            hidden.index("if (IsPauseKey(key))") : hidden.index("if (key == KeyId::XiB)")
        ]
        b_block = hidden[
            hidden.index("if (key == KeyId::XiB)") : hidden.index("// Once a real Menu@0 render")
        ]
        for block in (start_block, b_block):
            self.assertLess(
                block.index("RestoreBlurBestEffort"),
                block.index("g_cleanHidden.store(false"),
            )

    def test_transient_restore_failure_remains_retryable(self):
        self.assertIn("g_suppressed.store(true", BLUR)
        self.assertIn("disable_blur_rollback", BLUR)
        self.assertIn("deferred outside-Clean-Pause retry", NATIVE)

    def test_restore_never_executes_lua_from_nested_vanilla_input(self):
        helper = NATIVE[
            NATIVE.index("void RestoreBlurBestEffort") : NATIVE.index("bool ValidateObjectVtable")
        ]
        self.assertIn("if (g_forwardDepth != 0)", helper)
        self.assertLess(helper.index("if (g_forwardDepth != 0)"), helper.index("blur::Restore()"))


if __name__ == "__main__":
    unittest.main()
