from __future__ import annotations

from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from profile_patch import patch_profile  # noqa: E402
from profile_probe_patch import (  # noqa: E402
    GAMEPLAY_PROBE_ACTION,
    PAUSE_PROBE_ACTION,
    make_diagnostic_profile,
    validate_diagnostic_profile,
)

FIXTURE = ROOT / "tests" / "fixtures" / "defaultProfile_minimal.xml"


class DiagnosticProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        vanilla = FIXTURE.read_text(encoding="utf-8")
        self.rc2, _ = patch_profile(vanilla)
        self.diagnostic = make_diagnostic_profile(self.rc2)
        self.root = ET.fromstring(self.diagnostic)

    def action(self, map_name: str, action_name: str) -> ET.Element:
        action_map = next(
            m for m in self.root.findall("actionmap") if m.get("name") == map_name
        )
        return next(a for a in action_map.findall("action") if a.get("name") == action_name)

    def test_restores_vanilla_pause_activation_and_bindings(self) -> None:
        for map_name, action_name in (
            ("open_menu", "open_menu"),
            ("open_pause_menu", "open_pause_menu"),
        ):
            action = self.action(map_name, action_name)
            self.assertEqual(action.get("onPress"), "1")
            self.assertEqual(action.get("onRelease"), "1")
            self.assertEqual(action.get("keyboard"), "_keybinds_ref_")
            self.assertEqual(action.get("xboxpad"), "xi_start")
            self.assertIsNone(action.get("consoleCMD"))
            self.assertIsNone(action.get("consoleCmd"))

    def test_probe_is_f10_only_and_does_not_touch_controller(self) -> None:
        for map_name, action_name in (
            ("open_menu", GAMEPLAY_PROBE_ACTION),
            ("open_pause_menu", PAUSE_PROBE_ACTION),
        ):
            action = self.action(map_name, action_name)
            self.assertEqual(action.get("onPress"), "1")
            self.assertIsNone(action.get("onRelease"))
            self.assertEqual(action.get("keyboard"), "f10")
            self.assertEqual(action.get("consoleCMD"), "1")
            self.assertIsNone(action.get("xboxpad"))
            self.assertIsNone(action.get("pspad"))

    def test_rewrites_rc2_filter_references_to_probe_names(self) -> None:
        all_names = {
            a.get("name")
            for action_filter in self.root.findall("actionfilter")
            for a in action_filter.findall("action")
        }
        self.assertNotIn("clean_pause_enter_gameplay", all_names)
        self.assertNotIn("clean_pause_enter_pause_context", all_names)
        self.assertIn(PAUSE_PROBE_ACTION, all_names)

    def test_controls_map_is_retained(self) -> None:
        controls = [
            m for m in self.root.findall("actionmap") if m.get("name") == "clean_pause_controls"
        ]
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].get("priority"), "overlays")
        self.assertEqual(controls[0].get("exclusivity"), "1")
        validate_diagnostic_profile(self.diagnostic)


if __name__ == "__main__":
    unittest.main()
