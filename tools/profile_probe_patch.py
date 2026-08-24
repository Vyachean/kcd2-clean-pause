#!/usr/bin/env python3

from __future__ import annotations

import xml.etree.ElementTree as ET

from profile_patch import (
    CONSOLE_COMMAND_ATTR,
    CONTROLS_MAP,
    GAMEPLAY_ACTION,
    GAMEPLAY_ENTRY_ACTION,
    GAMEPLAY_MAP,
    PAUSE_ACTION,
    PAUSE_ENTRY_ACTION,
    PAUSE_MAP,
    ProfilePatchError,
)

GAMEPLAY_PROBE_ACTION = "clean_pause_probe_gameplay"
PAUSE_PROBE_ACTION = "clean_pause_probe_pause_context"
PROBE_KEY = "f10"


def _map(root: ET.Element, name: str) -> ET.Element:
    found = [m for m in root.findall("actionmap") if m.get("name") == name]
    if len(found) != 1:
        raise ProfilePatchError(f"expected exactly one action map {name}, found {len(found)}")
    return found[0]


def _action(action_map: ET.Element, name: str) -> ET.Element:
    found = [a for a in action_map.findall("action") if a.get("name") == name]
    if len(found) != 1:
        raise ProfilePatchError(
            f"expected exactly one {action_map.get('name')}/{name}, found {len(found)}"
        )
    return found[0]


def _restore_vanilla_and_convert_entry(
    root: ET.Element,
    map_name: str,
    vanilla_name: str,
    entry_name: str,
    probe_name: str,
) -> None:
    action_map = _map(root, map_name)
    vanilla = _action(action_map, vanilla_name)
    entry = _action(action_map, entry_name)

    if vanilla.get("onRelease") != "1" or vanilla.get("onPress") is not None:
        raise ProfilePatchError(f"unexpected rc2 vanilla fallback contract: {map_name}/{vanilla_name}")
    if vanilla.get("keyboard") != "_keybinds_ref_" or vanilla.get("xboxpad") != "xi_start":
        raise ProfilePatchError(f"unexpected rc2 vanilla bindings: {map_name}/{vanilla_name}")
    if vanilla.get(CONSOLE_COMMAND_ATTR) is not None or vanilla.get("consoleCmd") is not None:
        raise ProfilePatchError(f"rc2 vanilla fallback became console command: {map_name}/{vanilla_name}")

    if entry.get("onPress") != "1" or entry.get(CONSOLE_COMMAND_ATTR) != "1":
        raise ProfilePatchError(f"unexpected rc2 custom entry contract: {map_name}/{entry_name}")
    if entry.get("keyboard") != "escape" or entry.get("xboxpad") != "xi_start":
        raise ProfilePatchError(f"unexpected rc2 custom entry bindings: {map_name}/{entry_name}")

    # Restore the exact activation modes of the retail pause action. All other
    # retail binding metadata was deliberately preserved by the rc2 patcher.
    vanilla.set("onPress", "1")

    # Reuse the existing custom-action slot as a keyboard-only diagnostic probe.
    # This makes the diagnostic release a tiny deterministic transform of the
    # already integrity-checked rc2 source instead of vendoring another 100 KB XML.
    entry.set("name", probe_name)
    entry.set("keyboard", PROBE_KEY)
    entry.attrib.pop("xboxpad", None)
    entry.attrib.pop("pspad", None)


def _rename_filter_references(root: ET.Element) -> None:
    replacements = {
        GAMEPLAY_ENTRY_ACTION: GAMEPLAY_PROBE_ACTION,
        PAUSE_ENTRY_ACTION: PAUSE_PROBE_ACTION,
    }
    for action_filter in root.findall("actionfilter"):
        for action in action_filter.findall("action"):
            replacement = replacements.get(action.get("name"))
            if replacement:
                action.set("name", replacement)


def make_diagnostic_profile(rc2_profile_text: str) -> str:
    try:
        root = ET.fromstring(rc2_profile_text)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"rc2 release profile is invalid XML: {exc}") from exc

    if root.tag != "profile":
        raise ProfilePatchError(f"expected profile root, got {root.tag}")

    controls = [m for m in root.findall("actionmap") if m.get("name") == CONTROLS_MAP]
    if len(controls) != 1 or controls[0].get("priority") != "overlays" or controls[0].get("exclusivity") != "1":
        raise ProfilePatchError("rc2 release profile lost clean_pause_controls")

    _restore_vanilla_and_convert_entry(
        root,
        GAMEPLAY_MAP,
        GAMEPLAY_ACTION,
        GAMEPLAY_ENTRY_ACTION,
        GAMEPLAY_PROBE_ACTION,
    )
    _restore_vanilla_and_convert_entry(
        root,
        PAUSE_MAP,
        PAUSE_ACTION,
        PAUSE_ENTRY_ACTION,
        PAUSE_PROBE_ACTION,
    )
    _rename_filter_references(root)

    result = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    validate_diagnostic_profile(result)
    return result


def validate_diagnostic_profile(profile_text: str) -> None:
    try:
        root = ET.fromstring(profile_text)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"diagnostic profile is invalid XML: {exc}") from exc

    for map_name, vanilla_name, probe_name in (
        (GAMEPLAY_MAP, GAMEPLAY_ACTION, GAMEPLAY_PROBE_ACTION),
        (PAUSE_MAP, PAUSE_ACTION, PAUSE_PROBE_ACTION),
    ):
        action_map = _map(root, map_name)
        vanilla = _action(action_map, vanilla_name)
        probe = _action(action_map, probe_name)

        if vanilla.get("onPress") != "1" or vanilla.get("onRelease") != "1":
            raise ProfilePatchError(f"diagnostic release modified vanilla activation: {map_name}/{vanilla_name}")
        if vanilla.get("keyboard") != "_keybinds_ref_" or vanilla.get("xboxpad") != "xi_start":
            raise ProfilePatchError(f"diagnostic release modified vanilla bindings: {map_name}/{vanilla_name}")
        if vanilla.get(CONSOLE_COMMAND_ATTR) is not None or vanilla.get("consoleCmd") is not None:
            raise ProfilePatchError(f"diagnostic release converted vanilla pause to console command: {map_name}/{vanilla_name}")

        if probe.get("onPress") != "1" or probe.get("onRelease") is not None:
            raise ProfilePatchError(f"diagnostic probe is not press-only: {map_name}/{probe_name}")
        if probe.get("keyboard") != PROBE_KEY or probe.get(CONSOLE_COMMAND_ATTR) != "1":
            raise ProfilePatchError(f"diagnostic probe is not an F10 console command: {map_name}/{probe_name}")
        if probe.get("xboxpad") is not None or probe.get("pspad") is not None:
            raise ProfilePatchError(f"diagnostic probe touches controller input: {map_name}/{probe_name}")

    controls = [m for m in root.findall("actionmap") if m.get("name") == CONTROLS_MAP]
    if len(controls) != 1 or controls[0].get("priority") != "overlays" or controls[0].get("exclusivity") != "1":
        raise ProfilePatchError("diagnostic controls map contract changed")

    stale = {GAMEPLAY_ENTRY_ACTION, PAUSE_ENTRY_ACTION}
    for action_filter in root.findall("actionfilter"):
        names = {a.get("name") for a in action_filter.findall("action")}
        if names & stale:
            raise ProfilePatchError(
                f"diagnostic filter {action_filter.get('name')} still references rc2 entry actions"
            )


__all__ = [
    "GAMEPLAY_PROBE_ACTION",
    "PAUSE_PROBE_ACTION",
    "PROBE_KEY",
    "make_diagnostic_profile",
    "validate_diagnostic_profile",
]
