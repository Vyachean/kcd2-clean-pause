from __future__ import annotations

from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from tools.profile_patch import (
    CONTROLS_MAP,
    INPUT_FILTER,
    RESUME_ACTION,
    ProfilePatchError,
    detect_pause_binding,
    patch_profile,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "defaultProfile_minimal.xml"


class ProfilePatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = FIXTURE.read_text(encoding="utf-8")

    def test_detects_retail_pause_map_not_generic_start_action(self) -> None:
        info = detect_pause_binding(self.source)
        self.assertEqual(info.profile_version, "0")
        self.assertEqual(info.pause_map, "open_pause_menu")
        self.assertEqual(info.pause_action, "open_pause_menu")
        self.assertEqual(info.xbox_input, "xi_start")
        self.assertEqual(info.ps_input, "pad_start")

    def test_patch_is_single_fire_and_preserves_bindings(self) -> None:
        patched, info = patch_profile(self.source)
        root = ET.fromstring(patched)

        self.assertEqual(root.get("version"), "0")
        pause_map = next(m for m in root.findall("actionmap") if m.get("name") == info.pause_map)
        action = next(a for a in pause_map.findall("action") if a.get("name") == info.pause_action)

        self.assertEqual(action.get("onPress"), "1")
        self.assertEqual(action.get("consoleCmd"), "1")
        self.assertIsNone(action.get("onRelease"))
        self.assertEqual(action.get("keyboard"), "_keybinds_ref_")
        self.assertEqual(action.get("noModifiers"), "1")
        self.assertEqual(action.get("xboxpad"), "xi_start")
        self.assertEqual(action.get("pspad"), "pad_start")

    def test_patch_adds_release_resume_map_and_action_pass_filter(self) -> None:
        patched, info = patch_profile(self.source)
        root = ET.fromstring(patched)

        controls = [m for m in root.findall("actionmap") if m.get("name") == CONTROLS_MAP]
        self.assertEqual(len(controls), 1)
        resume = next(a for a in controls[0].findall("action") if a.get("name") == RESUME_ACTION)
        self.assertEqual(resume.get("onRelease"), "1")
        self.assertIsNone(resume.get("onPress"))
        self.assertEqual(resume.get("xboxpad"), "xi_b")
        self.assertEqual(resume.get("pspad"), "pad_circle")
        self.assertEqual(resume.get("consoleCmd"), "1")

        filters = [f for f in root.findall("actionfilter") if f.get("name") == INPUT_FILTER]
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].get("type"), "actionPass")
        self.assertEqual(
            {a.get("name") for a in filters[0].findall("action")},
            {info.pause_action, RESUME_ACTION},
        )

    def test_existing_restriction_for_pause_action_is_preserved(self) -> None:
        patched, info = patch_profile(self.source)
        root = ET.fromstring(patched)
        no_pause = next(f for f in root.findall("actionfilter") if f.get("name") == "no_pause_test")
        self.assertIn(info.pause_action, {a.get("name") for a in no_pause.findall("action")})

    def test_rejects_profile_without_semantic_pause_start_binding(self) -> None:
        source = """<profile version=\"9\"><actionmap name=\"open_menu\"><action name=\"open_menu\" onPress=\"1\" xboxpad=\"xi_start\"/></actionmap></profile>"""
        with self.assertRaises(ProfilePatchError):
            patch_profile(source)

    def test_rejects_double_patch(self) -> None:
        patched, _ = patch_profile(self.source)
        with self.assertRaises(ProfilePatchError):
            patch_profile(patched)

    def test_supports_ui_start_pause_variant(self) -> None:
        source = """<profile version=\"22\"><actionmap name=\"ui_start_pause\" priority=\"pure_include\" exclusivity=\"0\"><action name=\"ui_start_pause\" onPress=\"1\" onRelease=\"1\" xboxpad=\"xi_start\" pspad=\"pad_start\"/></actionmap></profile>"""
        patched, info = patch_profile(source)
        self.assertEqual(info.pause_action, "ui_start_pause")
        self.assertIn('consoleCmd="1"', patched)
        self.assertIn(INPUT_FILTER, patched)


if __name__ == "__main__":
    unittest.main()
