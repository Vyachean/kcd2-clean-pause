#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

CONTROLS_MAP = "clean_pause_controls"
CONTROLS_PRIORITY = "overlays"
GAMEPLAY_MAP = "open_menu"
GAMEPLAY_ACTION = "open_menu"
PAUSE_MAP = "open_pause_menu"
PAUSE_ACTION = "open_pause_menu"

GAMEPLAY_ENTRY_ACTION = "clean_pause_enter_gameplay"
PAUSE_ENTRY_ACTION = "clean_pause_enter_pause_context"
MENU_ACTION = "clean_pause_open_menu"
START_RELEASE_BLOCK_ACTION = "clean_pause_block_start_release"
B_PRESS_ACTION = "clean_pause_block_b_press"
RESUME_ACTION = "clean_pause_resume"

CONSOLE_COMMAND_ATTR = "consoleCMD"
DEFAULT_KEYBOARD_PAUSE_INPUT = "escape"


class ProfilePatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class RoutedAction:
    map_name: str
    action_name: str
    entry_action_name: str
    xbox_input: str
    ps_input: str | None
    keyboard_input: str | None
    no_modifiers: str | None


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


def _find_exact_action(
    root: ET.Element,
    map_name: str,
    action_name: str,
    entry_action_name: str,
) -> RoutedAction:
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

    action = actions[0]
    xbox_inputs = _device_inputs(action, "xboxpad")
    if "xi_start" not in xbox_inputs:
        raise ProfilePatchError(
            f"{map_name}/{action_name} is not bound to xboxpad=xi_start; refusing to guess"
        )

    keyboard = action.get("keyboard")
    if keyboard != "_keybinds_ref_":
        raise ProfilePatchError(
            f"{map_name}/{action_name} keyboard route is {keyboard!r}, expected _keybinds_ref_; "
            "refusing to hard-code a different keyboard fallback"
        )

    ps_inputs = _device_inputs(action, "pspad")
    return RoutedAction(
        map_name=map_name,
        action_name=action_name,
        entry_action_name=entry_action_name,
        xbox_input="xi_start",
        ps_input=ps_inputs[0] if ps_inputs else None,
        keyboard_input=keyboard,
        no_modifiers=action.get("noModifiers"),
    )


def detect_pause_bindings(xml_text: str) -> PatchInfo:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"defaultProfile.xml is not valid XML: {exc}") from exc

    if root.tag != "profile":
        raise ProfilePatchError(f"expected <profile> root, got <{root.tag}>")

    priority_names = {
        p.get("name")
        for priorities in root.findall("priorities")
        for p in priorities.findall("priority")
    }
    if CONTROLS_PRIORITY not in priority_names:
        raise ProfilePatchError(
            f'profile does not define required priority "{CONTROLS_PRIORITY}"; '
            "refusing to invent ordering"
        )

    return PatchInfo(
        profile_version=root.get("version"),
        gameplay=_find_exact_action(
            root, GAMEPLAY_MAP, GAMEPLAY_ACTION, GAMEPLAY_ENTRY_ACTION
        ),
        pause=_find_exact_action(
            root, PAUSE_MAP, PAUSE_ACTION, PAUSE_ENTRY_ACTION
        ),
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


def _entry_action_tag(routed: RoutedAction) -> str:
    attrs = [
        f'name="{routed.entry_action_name}"',
        'onPress="1"',
        f'keyboard="{DEFAULT_KEYBOARD_PAUSE_INPUT}"',
        'noModifiers="1"',
        f'xboxpad="{routed.xbox_input}"',
    ]
    if routed.ps_input:
        attrs.append(f'pspad="{routed.ps_input}"')
    attrs.append(f'{CONSOLE_COMMAND_ATTR}="1"')
    return "<action " + " ".join(attrs) + " />"


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
            f"expected exactly one {routed.map_name}/{routed.action_name} action tag, "
            f"found {len(matches)}"
        )

    action_match = matches[0]
    old_tag = action_match.group(0)
    fallback_tag = old_tag

    # Keep the retail semantic action as the fail-safe path, but make it
    # release-only. If the custom press command cannot execute, releasing
    # Esc/Start still reaches the normal vanilla pause action.
    for attr in (
        "onPress",
        "onHold",
        "always",
        "retriggerable",
        "holdTriggerDelay",
        "holdRepeatDelay",
        "pressTriggerDelay",
        "pressTriggerDelayRepeatOverride",
        CONSOLE_COMMAND_ATTR,
    ):
        fallback_tag = _remove_attr(fallback_tag, attr)
    fallback_tag = _set_attr(fallback_tag, "onRelease", "1")

    for attr in ("name", "xboxpad", "pspad", "keyboard", "noModifiers"):
        before = _attr_pattern(attr).search(old_tag)
        after = _attr_pattern(attr).search(fallback_tag)
        if (before.group(2) if before else None) != (after.group(2) if after else None):
            raise ProfilePatchError(
                f"patch unexpectedly changed {attr} on "
                f"{routed.map_name}/{routed.action_name}"
            )

    newline = "\r\n" if "\r\n" in text else "\n"
    line_start = map_text.rfind("\n", 0, action_match.start()) + 1
    indent = map_text[line_start : action_match.start()]
    replacement = fallback_tag + newline + indent + _entry_action_tag(routed)

    patched_map = (
        map_text[: action_match.start()]
        + replacement
        + map_text[action_match.end() :]
    )
    return text[:map_start] + patched_map + text[map_end:]


def _filter_additions_for_originals(
    originals: set[str], include_controls: bool
) -> tuple[str, ...]:
    additions: list[str] = []
    if GAMEPLAY_ACTION in originals:
        additions.append(GAMEPLAY_ENTRY_ACTION)
    if PAUSE_ACTION in originals:
        additions.append(PAUSE_ENTRY_ACTION)
    if include_controls and originals & {GAMEPLAY_ACTION, PAUSE_ACTION}:
        additions.extend(
            (
                MENU_ACTION,
                START_RELEASE_BLOCK_ACTION,
                B_PRESS_ACTION,
                RESUME_ACTION,
            )
        )
    return tuple(dict.fromkeys(additions))


def _extend_filters(text: str) -> str:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ProfilePatchError(
            f"profile became invalid before filter extension: {exc}"
        ) from exc

    targets: list[tuple[str, tuple[str, ...]]] = []
    for action_filter in root.findall("actionfilter"):
        filter_name = action_filter.get("name")
        if not filter_name:
            continue
        names = {a.get("name") for a in action_filter.findall("action")}
        filter_type = (action_filter.get("type") or "actionFail").lower()
        if not names & {GAMEPLAY_ACTION, PAUSE_ACTION}:
            continue
        if filter_type == "actionpass":
            additions = _filter_additions_for_originals(names, include_controls=True)
        else:
            additions = _filter_additions_for_originals(names, include_controls=False)
        if additions:
            targets.append((filter_name, additions))

    if not targets:
        return text

    newline = "\r\n" if "\r\n" in text else "\n"
    indent = "\t" if "\t<actionmap" in text else "  "
    inner = indent * 2

    patched = text
    for filter_name, additions in targets:
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
    markers = (
        GAMEPLAY_ENTRY_ACTION,
        PAUSE_ENTRY_ACTION,
        CONTROLS_MAP,
        MENU_ACTION,
        START_RELEASE_BLOCK_ACTION,
        B_PRESS_ACTION,
        RESUME_ACTION,
    )
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
        + f'<action name="{MENU_ACTION}" onPress="1" keyboard="{DEFAULT_KEYBOARD_PAUSE_INPUT}" '
        + f'noModifiers="1" xboxpad="xi_start" pspad="pad_start" {CONSOLE_COMMAND_ATTR}="1" />'
        + newline
        + inner
        + f'<action name="{START_RELEASE_BLOCK_ACTION}" onRelease="1" '
        + f'keyboard="{DEFAULT_KEYBOARD_PAUSE_INPUT}" noModifiers="1" '
        + 'xboxpad="xi_start" pspad="pad_start" />'
        + newline
        + inner
        + f'<action name="{B_PRESS_ACTION}" onPress="1" xboxpad="xi_b" pspad="pad_circle" />'
        + newline
        + inner
        + f'<action name="{RESUME_ACTION}" onRelease="1" xboxpad="xi_b" '
        + f'pspad="pad_circle" {CONSOLE_COMMAND_ATTR}="1" />'
        + newline
        + indent
        + "</actionmap>"
        + newline
    )

    _, pause_map_end = _find_named_block(patched, "actionmap", info.pause.map_name)
    patched = patched[:pause_map_end] + controls_block + patched[pause_map_end:]
    patched = _extend_filters(patched)

    _validate_patch(patched, info)
    return patched, info


def _find_action(root: ET.Element, map_name: str, action_name: str) -> ET.Element:
    maps = [m for m in root.findall("actionmap") if m.get("name") == map_name]
    if len(maps) != 1:
        raise ProfilePatchError(
            f"patched profile has unexpected action map count: {map_name}"
        )
    actions = [a for a in maps[0].findall("action") if a.get("name") == action_name]
    if len(actions) != 1:
        raise ProfilePatchError(
            f"patched profile has unexpected {map_name}/{action_name} count"
        )
    return actions[0]


def _validate_routed_action(root: ET.Element, routed: RoutedAction) -> None:
    fallback = _find_action(root, routed.map_name, routed.action_name)
    if fallback.get("onRelease") != "1":
        raise ProfilePatchError(
            f"{routed.map_name}/{routed.action_name} must remain as release-only vanilla fallback"
        )
    if any(
        fallback.get(name) is not None
        for name in ("onPress", "onHold", "always", CONSOLE_COMMAND_ATTR, "consoleCmd")
    ):
        raise ProfilePatchError(
            f"{routed.map_name}/{routed.action_name} fallback still has a custom activation mode"
        )
    if "xi_start" not in _device_inputs(fallback, "xboxpad"):
        raise ProfilePatchError(f"{routed.map_name}/{routed.action_name} lost xi_start")
    if fallback.get("keyboard") != routed.keyboard_input:
        raise ProfilePatchError(
            f"{routed.map_name}/{routed.action_name} lost keyboard binding"
        )

    entry = _find_action(root, routed.map_name, routed.entry_action_name)
    if entry.get("onPress") != "1" or entry.get("onRelease") is not None:
        raise ProfilePatchError(
            f"{routed.map_name}/{routed.entry_action_name} must be press-only"
        )
    if entry.get(CONSOLE_COMMAND_ATTR) != "1" or entry.get("consoleCmd") is not None:
        raise ProfilePatchError(
            f"{routed.map_name}/{routed.entry_action_name} is not an exact KCD2 console command"
        )
    if entry.get("keyboard") != DEFAULT_KEYBOARD_PAUSE_INPUT:
        raise ProfilePatchError(
            f"{routed.map_name}/{routed.entry_action_name} must explicitly bind Escape"
        )
    if entry.get("xboxpad") != "xi_start":
        raise ProfilePatchError(
            f"{routed.map_name}/{routed.entry_action_name} lost xi_start"
        )


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
    if (
        controls_map.get("priority") != CONTROLS_PRIORITY
        or controls_map.get("exclusivity") != "1"
    ):
        raise ProfilePatchError(
            "Clean Pause controls map must be exclusive at overlay priority"
        )

    actions = {a.get("name"): a for a in controls_map.findall("action")}
    expected = {
        MENU_ACTION,
        START_RELEASE_BLOCK_ACTION,
        B_PRESS_ACTION,
        RESUME_ACTION,
    }
    if set(actions) != expected:
        raise ProfilePatchError(
            f"Clean Pause controls map has unexpected actions: {sorted(actions)}"
        )

    menu = actions[MENU_ACTION]
    if (
        menu.get("onPress") != "1"
        or menu.get("keyboard") != DEFAULT_KEYBOARD_PAUSE_INPUT
        or menu.get("xboxpad") != "xi_start"
        or menu.get(CONSOLE_COMMAND_ATTR) != "1"
        or menu.get("consoleCmd") is not None
    ):
        raise ProfilePatchError("Clean Pause menu-handoff action contract is invalid")

    start_release = actions[START_RELEASE_BLOCK_ACTION]
    if (
        start_release.get("onRelease") != "1"
        or start_release.get("onPress") is not None
        or start_release.get("keyboard") != DEFAULT_KEYBOARD_PAUSE_INPUT
        or start_release.get("xboxpad") != "xi_start"
        or start_release.get(CONSOLE_COMMAND_ATTR) is not None
    ):
        raise ProfilePatchError(
            "Clean Pause Start/Escape release sink contract is invalid"
        )

    b_press = actions[B_PRESS_ACTION]
    if (
        b_press.get("onPress") != "1"
        or b_press.get("xboxpad") != "xi_b"
        or b_press.get(CONSOLE_COMMAND_ATTR) is not None
    ):
        raise ProfilePatchError("Clean Pause B press sink contract is invalid")

    resume = actions[RESUME_ACTION]
    if (
        resume.get("onRelease") != "1"
        or resume.get("onPress") is not None
        or resume.get("xboxpad") != "xi_b"
        or resume.get(CONSOLE_COMMAND_ATTR) != "1"
        or resume.get("consoleCmd") is not None
    ):
        raise ProfilePatchError("Clean Pause resume action contract is invalid")

    original_to_entry = {
        GAMEPLAY_ACTION: GAMEPLAY_ENTRY_ACTION,
        PAUSE_ACTION: PAUSE_ENTRY_ACTION,
    }
    controls_required = {
        MENU_ACTION,
        START_RELEASE_BLOCK_ACTION,
        B_PRESS_ACTION,
        RESUME_ACTION,
    }
    for action_filter in root.findall("actionfilter"):
        names = {a.get("name") for a in action_filter.findall("action")}
        filter_type = (action_filter.get("type") or "actionFail").lower()
        originals = names & set(original_to_entry)
        for original in originals:
            if original_to_entry[original] not in names:
                raise ProfilePatchError(
                    f"filter {action_filter.get('name')} does not mirror {original} "
                    f"to {original_to_entry[original]}"
                )
        if filter_type == "actionpass" and originals:
            missing = controls_required - names
            if missing:
                raise ProfilePatchError(
                    f"actionPass filter {action_filter.get('name')} would block "
                    f"Clean Pause controls: {sorted(missing)}"
                )
