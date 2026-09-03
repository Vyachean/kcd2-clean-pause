import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = (ROOT / "native/src/clean_pause_native.h").read_text(encoding="utf-8")
PROFILED = (ROOT / "native/src/clean_pause_native_profiled.cpp").read_text(encoding="utf-8")
GUARD = (ROOT / "native/src/process_guard.cpp").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
ASI_INSTALL = (ROOT / "native/INSTALL_ASI.txt").read_text(encoding="utf-8")


class ProcessLifetimeContractTests(unittest.TestCase):
    def test_public_api_does_not_claim_full_hot_unload(self):
        self.assertIn("process-lifetime state", HEADER)
        self.assertIn("does not remove MinHook detours", HEADER)
        self.assertIn("hot unload/reload", HEADER)

    def test_runtime_guard_survives_for_process_lifetime(self):
        self.assertIn("Keep this handle for the lifetime of the process", GUARD)
        self.assertIn("support hot-unloading", GUARD)
        self.assertNotIn("CloseHandle(g_processGuard)", GUARD)

    def test_stop_is_teardown_signaling_not_hook_removal(self):
        stop = PROFILED[PROFILED.rindex("void Stop()") :]
        self.assertIn("g_stopping.store(true", stop)
        self.assertNotIn("MH_DisableHook", stop)
        self.assertNotIn("MH_RemoveHook", stop)
        self.assertNotIn("MH_Uninitialize", stop)

    def test_user_docs_require_process_restart_for_module_changes(self):
        self.assertIn("Hot unload/reload", README)
        self.assertIn("process-lifetime state", README)
        self.assertIn("Hot-unloading or hot-reloading", ASI_INSTALL)
        self.assertIn("Stop KCD2 before replacing, removing or moving", ASI_INSTALL)


if __name__ == "__main__":
    unittest.main()
