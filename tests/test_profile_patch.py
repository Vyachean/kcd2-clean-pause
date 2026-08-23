from __future__ import annotations

from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from tools.profile_patch import (
    B_PRESS_ACTION,
    CONSOLE_COMMAND_ATTR,
    CONTROLS_MAP,
    CONTROLS_PRIORITY,
    MENU_ACTION,
    RESUME_ACTION,
    ProfilePatchError,
    detect_pause_bindings,
    patch_profile,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "defaultProfile_minimal.xml"


class ProfilePatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = FIXTURE.read_text(encoding="utf-8")

    def test_detects_both_retail_start_routes(self) -> None:
        info = detect_pause_bindings(self.source)
        self.assertEqual(info.profile_version, "0")
        self.assertEqual((info.gameplay.map_name, info.gameplay.action_name), ("open_menu", "open_menu"))
        self.assertEqual((info.pause.map_name, info.pause.action_name), ("open_pause_menu", "open_pause_menu"))
        self.assertEqual(info.gameplay.xbox_input, "xi_start")
        self.assertEqual(info.pause.xbox_input, "xi_start")

    def test_patch_routes_both_vanilla_actions_and_preserves_bindings(self) -> None:
        patched, info = patch_profile(self.source)
        root = ET.fromstring(patched)

        for routed in (info.gameplay, info.pause):
            action_map = next(m for m in root.findall("actionmap") if m.get("name") == routed.map_name)
            action = next(a for a in action_map.findall("action") if a.get("name") == routed.action_name)
            self.assertEqual(action.get("onPress"), "1")
            self.assertEqual(action.get(CONSOLE_COMMAND_ATTR), "1")
            self.assertIsNone(action.get("consoleCmd"))
            self.assertIsNone(action.get("onRelease"))
            self.assertEqual(action.get("keyboard"), "_keybinds_ref_")
            self.assertEqual(action.get("noModifiers"), "1")
            self.assertEqual(action.get("xboxpad"), "xi_start")
            self.assertEqual(action.get("pspad"), "pad_start")

    def test_patch_uses_exact_kcd2_console_command_attribute_spelling(self) -> None:
        patched, _ = patch_profile(self.source)
        self.assertIn('consoleCMD="1"', patched)
        self.assertNotIn('consoleCmd="1"', patched)

    def test_patch_adds_exclusive_overlay_controls_map(self) -> None:
        patched, _ = patch_profile(self.source)
        root = ET.fromstring(patched)
        controls = [m for m in root.findall("actionmap") if m.get("name") == CONTROLS_MAP]
        self.assertEqual(len(controls), 1)
        controls = controls[0]
        self.assertEqual(controls.get("priority"), CONTROLS_PRIORITY)
        self.assertEqual(controls.get("exclusivity"), "1")

        actions = {a.get("name"): a for a in controls.findall("action")}
        self.assertEqual(actions[MENU_ACTION].get("onPress"), "1")
        self.assertEqual(actions[MENU_ACTION].get("xboxpad"), "xi_start")
        self.assertEqual(actions[MENU_ACTION].get(CONSOLE_COMMAND_ATTR), "1")
        self.assertIsNone(actions[MENU_ACTION].get("consoleCmd"))
        self.assertEqual(actions[B_PRESS_ACTION].get("onPress"), "1")
        self.assertEqual(actions[B_PRESS_ACTION].get("xboxpad"), "xi_b")
        self.assertIsNone(actions[B_PRESS_ACTION].get(CONSOLE_COMMAND_ATTR))
        self.assertEqual(actions[RESUME_ACTION].get("onRelease"), "1")
        self.assertEqual(actions[RESUME_ACTION].get("xboxpad"), "xi_b")
        self.assertEqual(actions[RESUME_ACTION].get(CONSOLE_COMMAND_ATTR), "1")
        self.assertIsNone(actions[RESUME_ACTION].get("consoleCmd"))

    def test_extends_relevant_action_pass_filters_but_not_action_fail(self) -> None:
        patched, _ = patch_profile(self.source)
        root = ET.fromstring(patched)
        fail_filter = next(f for f in root.findall("actionfilter") if f.get("name") == "no_pause_test")
        fail_names = {a.get("name") for a in fail_filter.findall("action")}
        self.assertEqual(fail_names, {"open_pause_menu"})

        pass_filter = next(f for f in root.findall("actionfilter") if f.get("name") == "pause_pass_test")
        pass_names = {a.get("name") for a in pass_filter.findall("action")}
        self.assertTrue({MENU_ACTION, B_PRESS_ACTION, RESUME_ACTION}.issubset(pass_names))

    def test_rejects_profile_without_overlay_priority(self) -> None:
        source = self.source.replace('<priority name="overlays" value="12"/>\n', "")
        with self.assertRaises(ProfilePatchError):
            patch_profile(source)

    def test_rejects_profile_without_exact_gameplay_start_route(self) -> None:
        source = self.source.replace('name="open_menu" onPress="1"', 'name="not_open_menu" onPress="1"', 1)
        with self.assertRaises(ProfilePatchError):
            patch_profile(source)

    def test_rejects_double_patch(self) -> None:
        patched, _ = patch_profile(self.source)
        with self.assertRaises(ProfilePatchError):
            patch_profile(patched)


if __name__ == "__main__":
    unittest.main()
