import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "native/src"
RUNTIME_PATH = SOURCE_DIR / "clean_pause_native.cpp"
RUNTIME = RUNTIME_PATH.read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class RuntimeTranslationUnitContractTests(unittest.TestCase):
    def test_production_cpp_files_do_not_textually_include_other_cpp_files(self):
        cpp_include = re.compile(r'^\s*#\s*include\s*["<][^">]+\.cpp[">]', re.MULTILINE)
        offenders = []
        for path in sorted(SOURCE_DIR.glob("*.cpp")):
            if cpp_include.search(path.read_text(encoding="utf-8")):
                offenders.append(path.name)
        self.assertEqual([], offenders)

    def test_bootstrap_symbols_are_not_macro_substituted(self):
        for symbol in (
            "Start",
            "Stop",
            "BootstrapThread",
            "FindRuntimeEnvironment",
            "ResolveGameFramework",
            "InstallPauseBarrierHook",
            "InstallInputHook",
            "HookPostInputEvent",
        ):
            self.assertNotRegex(
                RUNTIME,
                rf"(?m)^\s*#\s*define\s+{re.escape(symbol)}\b",
            )

    def test_materialized_runtime_is_compiled_directly(self):
        self.assertTrue(RUNTIME_PATH.exists())
        self.assertFalse((SOURCE_DIR / "clean_pause_native_profiled.cpp").exists())
        self.assertIn("src/clean_pause_native.cpp", CMAKE)
        self.assertNotIn("src/clean_pause_native_profiled.cpp", CMAKE)

    def test_dead_wrapper_symbols_are_absent(self):
        for token in (
            "LegacyStart_Unreachable",
            "LegacyStop_Unreachable",
            "LegacyBootstrapThread_Unreachable",
            "LegacyInstallPauseBarrierHook_Xbox156Only",
            "LegacyInstallInputHook_Xbox156Only",
            "LegacyHookPostInputEventProfiledCore",
            "LegacyFindRuntimeEnvironment_Xbox156Only",
            "LegacyResolveGameFramework_Xbox156Only",
        ):
            self.assertNotIn(token, RUNTIME)
        self.assertIn("void __fastcall HookPostInputEventCore", RUNTIME)
        self.assertIn("bool ResolveProfileFramework", RUNTIME)


if __name__ == "__main__":
    unittest.main()
