from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

from tools.build_from_profile import prepare_profile
from tools.profile_patch import GAMEPLAY_ENTRY_ACTION, PAUSE_ENTRY_ACTION

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "defaultProfile_minimal.xml"


class ExtractedProfileBuilderTests(unittest.TestCase):
    def test_prepare_profile_uses_exact_input_and_renders_runtime_commands(self) -> None:
        source_bytes, patched, lua, info = prepare_profile(FIXTURE)

        self.assertEqual(source_bytes, FIXTURE.read_bytes())
        self.assertEqual(
            hashlib.sha256(source_bytes).hexdigest(),
            hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        )
        self.assertEqual(info.profile_version, "0")
        self.assertIn('name="clean_pause_controls" priority="overlays" exclusivity="1"', patched)
        self.assertIn('name="open_menu" onRelease="1"', patched)
        self.assertIn(f'name="{GAMEPLAY_ENTRY_ACTION}"', patched)
        self.assertIn(f'name="{PAUSE_ENTRY_ACTION}"', patched)
        self.assertIn(f'local GAMEPLAY_COMMAND = "{GAMEPLAY_ENTRY_ACTION}"', lua)
        self.assertIn(f'local PAUSE_COMMAND = "{PAUSE_ENTRY_ACTION}"', lua)
        self.assertNotIn("__CLEAN_PAUSE_GAMEPLAY_COMMAND__", lua)
        self.assertNotIn("__CLEAN_PAUSE_PAUSE_COMMAND__", lua)


if __name__ == "__main__":
    unittest.main()
