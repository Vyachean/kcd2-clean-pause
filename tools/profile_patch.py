#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

CONTROLS_MAP = "clean_pause_controls"
CONTROLS_PRIORITY = "overlays"
MENU_ACTION = "clean_pause_open_menu"
B_PRESS_ACTION = "clean_pause_block_b_press"
RESUME_ACTION = "clean_pause_resume"
GAMEPLAY_MAP = "open_menu"
GAMEPLAY_ACTION = "open_menu"
PAUSE_MAP = "open_pause_menu"
PAUSE_ACTION = "open_pause_menu"


class ProfilePatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class RoutedAction:
    map_name: str
    action_name: str
    xbox_input: str
    ps_input: str | None


@dataclass(frozen=True)
class PatchInfo:
    profile_version: str | None
    gameplay: RoutedAction
    pause: RoutedAction


def _device_inputs(action: ET.Element, device: str) -> list[str]:
    values: list[str] = []
    direct = action.get(device)
    if direct:
        values.append(direct.lower())

    child = action.find(device)
    if child is not None:
        for input_data in child.findall("inputdata"):
            value = input_data.get("input")
            if value:
                values.append(value.lower())
    return values


def _find_exact_action(root: ET.Element, map_name: str, action_name: str) -> RoutedAction:
    maps = [m for m in root.findall("actionmap") if m.get("name") == map_name]
    if len(maps) != 1:
        raise ProfilePatchError(
            f'expected exactly one <actionmap name="{map_name}">, found {len(maps)}'
        )

    actions = [a for a in maps[0].findall("action") if a.get("name") == action_name]
    if len(actions) != 1:
        raise ProfilePatchError(
            f"expected exactly one {map_name}/{action_name} action, found {len(actions)}"
        )

    xbox_inputs = _device_inputs(actions[0], "xboxpad")
    if "xi_start" not in xbox_inputs:
        raise ProfilePatchError(
            f"{map_name}/{action_name} is not bound to xboxpad=xi_start; refusing to guess"
        )
    ps_inputs = _device_inputs(actions[0], "pspad")
    return RoutedAction(
        map_name=map_name,
        action_name=action_name,
        xbox_input="xi_start",
        ps_input=ps_inputs[0] if ps_inputs else None,
    )


def detect_pause_bindings(xml_text: str) -> PatchInfo:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"defaultProfile.xml is not valid XML: {exc}") from exc

    if root.tag != "profile":
        raise ProfilePatchError(f"expected <profile> root, got <{root.tag}>")

    priority_names = {
        p.get("name") for priorities in root.findall("priorities") for p in priorities.findall("priority")
    }
    if CONTROLS_PRIORITY not in priority_names:
        raise ProfilePatchError(
            f'profile does not define required priority "{CONTROLS_PRIORITY}"; refusing to invent ordering'
        )

    return PatchInfo(
        profile_version=root.get("version"),
        gameplay=_find_exact_action(root, GAMEPLAY_MAP, GAMEPLAY_ACTION),
        pause=_find_exact_action(root, PAUSE_MAP, PAUSE_ACTION),
    )


def _attr_pattern(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![\w:-]){re.escape(name)}\s*=\s*([\"'])(.*?)\1",
        re.IGNORECASE | re.DOTALL,
    )


def _remove_attr(tag: str, name: str) -> str:
    return re.sub(
        rf"\s+{re.escape(name)}\s*=\s*([\"']).*?\1",
        "",
        tag,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _set_attr(tag: str, name: str, value: str) -> str:
    pattern = _attr_pattern(name)
    if pattern.search(tag):
        return pattern.sub(f'{name}="{value}"', tag, count=1)

    insert_at = tag.rfind("/>")
    if insert_at < 0:
        insert_at = tag.rfind(">")
    if insert_at < 0:
        raise ProfilePatchError(f"malformed action tag while setting {name}")
    return tag[:insert_at].rstrip() + f' {name}="{value}" ' + tag[insert_at:]


def _find_named_block(text: str, tag: str, name: str) -> tuple[int, int]:
    open_pattern = re.compile(
        rf"<{tag}\b(?=[^>]*\bname\s*=\s*([\"']){re.escape(name)}\1)[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    match = open_pattern.search(text)
    if not match:
        raise ProfilePatchError(f'could not locate <{tag} name="{name}"> in source text')
    close = re.search(rf"</{tag}\s*>", text[match.end() :], re.IGNORECASE)
    if not close:
        raise ProfilePatchError(f"missing closing </{tag}> for {name}")
    end = match.end() + close.end()
    return match.start(), end


def _patch_existing_action(text: str, routed: RoutedAction) -> str:
    map_start, map_end = _find_named_block(text, "actionmap", routed.map_name)
    map_text = text[map_start:map_end]
    action_pattern = re.compile(
        rf"<action\b(?=[^>]*\bname\s*=\s*([\"']){re.escape(routed.action_name)}\1)[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    matches = list(action_pattern.finditer(map_text))
    if len(matches) != 1:
        raise ProfilePatchError(
            f"expected exactly one {routed.map_name}/{routed.action_name} action tag, found {len(matches)}"
        )

    action_match = matches[0]
    old_tag = action_match.group(0)
    new_tag = old_tag
    for attr in (
        "onRelease",
        "onHold",
        "always",
        "retriggerable",
        "holdTriggerDelay",
        "holdRepeatDelay",
        "pressTriggerDelay",
        "pressTriggerDelayRepeatOverride",
    ):
        new_tag = _remove_attr(new_tag, attr)
    new_tag = _set_attr(new_tag, "onPress", "1")
    new_tag = _set_attr(new_tag, "consoleCmd", "1")

    for attr in ("name", "xboxpad", "pspad", "keyboard", "noModifiers"):
        before = _attr_pattern(attr).search(old_tag)
        after = _attr_pattern(attr).search(new_tag)
        if (before.group(2) if before else None) != (after.group(2) if after else None):
            raise ProfilePatchError(
                f"patch unexpectedly changed {attr} on {routed.map_name}/{routed.action_name}"
            )

    patched_map = map_text[: action_match.start()] + new_tag + map_text[action_match.end() :]
    return text[:map_start] + patched_map + text[map_end:]


def _extend_relevant_action_pass_filters(text: str, routed_names: set[str]) -> str:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"profile became invalid before filter extension: {exc}") from exc

    filter_names: list[str] = []
    for action_filter in root.findall("actionfilter"):
        if (action_filter.get("type") or "").lower() != "actionpass":
            continue
        allowed = {a.get("name") for a in action_filter.findall("action")}
        if allowed & routed_names:
            name = action_filter.get("name")
            if not name:
                raise ProfilePatchError("relevant actionPass filter has no name")
            filter_names.append(name)

    if not filter_names:
        return text

    newline = "\r\n" if "\r\n" in text else "\n"
    indent = "\t" if "\t<actionmap" in text else "  "
    inner = indent * 2
    additions = (MENU_ACTION, B_PRESS_ACTION, RESUME_ACTION)

    patched = text
    for filter_name in filter_names:
        start, end = _find_named_block(patched, "actionfilter", filter_name)
        block = patched[start:end]
        close_match = re.search(r"</actionfilter\s*>", block, re.IGNORECASE)
        if not close_match:
            raise ProfilePatchError(f"missing closing actionfilter for {filter_name}")
        existing = ET.fromstring(block)
        existing_names = {a.get("name") for a in existing.findall("action")}
        lines = "".join(
            inner + f'<action name="{name}" />' + newline
            for name in additions
            if name not in existing_names
        )
        block = block[: close_match.start()] + lines + block[close_match.start() :]
        patched = patched[:start] + block + patched[end:]

    return patched


def patch_profile(xml_text: str) -> tuple[str, PatchInfo]:
    info = detect_pause_bindings(xml_text)
    markers = (CONTROLS_MAP, MENU_ACTION, B_PRESS_ACTION, RESUME_ACTION)
    if any(marker in xml_text for marker in markers):
        raise ProfilePatchError("profile already contains Clean Pause additions")

    patched = _patch_existing_action(xml_text, info.gameplay)
    patched = _patch_existing_action(patched, info.pause)

    newline = "\r\n" if "\r\n" in xml_text else "\n"
    indent = "\t" if "\t<actionmap" in xml_text else "  "
    inner = indent * 2

    controls_block = (
        newline
        + indent
        + f'<actionmap name="{CONTROLS_MAP}" priority="{CONTROLS_PRIORITY}" exclusivity="1">'
        + newline
        + inner
        + f'<action name="{MENU_ACTION}" onPress="1" xboxpad="xi_start" pspad="pad_start" noModifiers="1" consoleCmd="1" />'
        + newline
        + inner
        + f'<action name="{B_PRESS_ACTION}" onPress="1" xboxpad="xi_b" pspad="pad_circle" />'
        + newline
        + inner
        + f'<action name="{RESUME_ACTION}" onRelease="1" xboxpad="xi_b" pspad="pad_circle" consoleCmd="1" />'
        + newline
        + indent
        + "</actionmap>"
        + newline
    )

    _, pause_map_end = _find_named_block(patched, "actionmap", info.pause.map_name)
    patched = patched[:pause_map_end] + controls_block + patched[pause_map_end:]
    patched = _extend_relevant_action_pass_filters(
        patched, {info.gameplay.action_name, info.pause.action_name}
    )

    _validate_patch(patched, info)
    return patched, info


def _validate_routed_action(root: ET.Element, routed: RoutedAction) -> None:
    action_map = next(
        (m for m in root.findall("actionmap") if m.get("name") == routed.map_name), None
    )
    if action_map is None:
        raise ProfilePatchError(f"patched profile lost action map {routed.map_name}")
    actions = [a for a in action_map.findall("action") if a.get("name") == routed.action_name]
    if len(actions) != 1:
        raise ProfilePatchError(
            f"patched profile has unexpected {routed.map_name}/{routed.action_name} count"
        )
    action = actions[0]
    if action.get("consoleCmd") != "1" or action.get("onPress") != "1":
        raise ProfilePatchError(
            f"{routed.map_name}/{routed.action_name} is not a single-fire console command"
        )
    if any(action.get(name) is not None for name in ("onRelease", "onHold", "always")):
        raise ProfilePatchError(
            f"{routed.map_name}/{routed.action_name} still has a second activation mode"
        )
    if "xi_start" not in _device_inputs(action, "xboxpad"):
        raise ProfilePatchError(f"{routed.map_name}/{routed.action_name} lost xi_start")


def _validate_patch(patched: str, info: PatchInfo) -> None:
    try:
        root = ET.fromstring(patched)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"patched profile is invalid XML: {exc}") from exc

    if root.get("version") != info.profile_version:
        raise ProfilePatchError("patch changed the profile root version")

    _validate_routed_action(root, info.gameplay)
    _validate_routed_action(root, info.pause)

    controls = [m for m in root.findall("actionmap") if m.get("name") == CONTROLS_MAP]
    if len(controls) != 1:
        raise ProfilePatchError("expected exactly one Clean Pause controls map")
    controls_map = controls[0]
    if controls_map.get("priority") != CONTROLS_PRIORITY or controls_map.get("exclusivity") != "1":
        raise ProfilePatchError("Clean Pause controls map must be exclusive at overlay priority")

    def action(name: str) -> ET.Element:
        found = [a for a in controls_map.findall("action") if a.get("name") == name]
        if len(found) != 1:
            raise ProfilePatchError(f"expected exactly one controls action {name}")
        return found[0]

    menu = action(MENU_ACTION)
    if menu.get("onPress") != "1" or menu.get("xboxpad") != "xi_start" or menu.get("consoleCmd") != "1":
        raise ProfilePatchError("Clean Pause menu-handoff action contract is invalid")

    b_press = action(B_PRESS_ACTION)
    if b_press.get("onPress") != "1" or b_press.get("xboxpad") != "xi_b" or b_press.get("consoleCmd") is not None:
        raise ProfilePatchError("Clean Pause B press sink contract is invalid")

    resume = action(RESUME_ACTION)
    if resume.get("onRelease") != "1" or resume.get("onPress") is not None or resume.get("xboxpad") != "xi_b" or resume.get("consoleCmd") != "1":
        raise ProfilePatchError("Clean Pause resume action contract is invalid")

    routed = {info.gameplay.action_name, info.pause.action_name}
    for action_filter in root.findall("actionfilter"):
        if (action_filter.get("type") or "").lower() != "actionpass":
            continue
        names = {a.get("name") for a in action_filter.findall("action")}
        if names & routed:
            missing = {MENU_ACTION, B_PRESS_ACTION, RESUME_ACTION} - names
            if missing:
                raise ProfilePatchError(
                    f"actionPass filter {action_filter.get('name')} would block Clean Pause controls: {sorted(missing)}"
                )
