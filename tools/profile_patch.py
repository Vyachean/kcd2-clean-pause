#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

CONTROLS_MAP = "clean_pause_controls"
RESUME_ACTION = "clean_pause_resume"
INPUT_FILTER = "clean_pause_only"


class ProfilePatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class PatchInfo:
    profile_version: str | None
    pause_map: str
    pause_action: str
    xbox_input: str | None
    ps_input: str | None


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


def detect_pause_binding(xml_text: str) -> PatchInfo:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"defaultProfile.xml is not valid XML: {exc}") from exc

    if root.tag != "profile":
        raise ProfilePatchError(f"expected <profile> root, got <{root.tag}>")

    candidates: list[tuple[int, str, str, ET.Element]] = []
    for action_map in root.findall("actionmap"):
        map_name = action_map.get("name") or ""
        for action in action_map.findall("action"):
            action_name = action.get("name") or ""
            xbox_inputs = _device_inputs(action, "xboxpad")
            if "xi_start" not in xbox_inputs:
                continue

            score = 0
            if map_name == "open_pause_menu":
                score += 100
            if action_name == "open_pause_menu":
                score += 100
            if map_name == "ui_start_pause":
                score += 90
            if action_name == "ui_start_pause":
                score += 90
            if "pause" in map_name.lower():
                score += 20
            if "pause" in action_name.lower():
                score += 20

            # xi_start is also used by non-pause actions. Require pause semantics.
            if score > 0:
                candidates.append((score, map_name, action_name, action))

    if not candidates:
        raise ProfilePatchError(
            "could not find a pause action bound to xboxpad=xi_start; refusing to guess"
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score = candidates[0][0]
    best = [item for item in candidates if item[0] == best_score]
    if len(best) != 1:
        names = ", ".join(f"{m}/{a}" for _, m, a, _ in best)
        raise ProfilePatchError(f"ambiguous pause binding candidates: {names}")

    _, map_name, action_name, action = best[0]
    xbox_inputs = _device_inputs(action, "xboxpad")
    ps_inputs = _device_inputs(action, "pspad")
    return PatchInfo(
        profile_version=root.get("version"),
        pause_map=map_name,
        pause_action=action_name,
        xbox_input=xbox_inputs[0] if xbox_inputs else None,
        ps_input=ps_inputs[0] if ps_inputs else None,
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
        raise ProfilePatchError(f"could not locate <{tag} name=\"{name}\"> in source text")
    close = re.search(rf"</{tag}\s*>", text[match.end() :], re.IGNORECASE)
    if not close:
        raise ProfilePatchError(f"missing closing </{tag}> for {name}")
    end = match.end() + close.end()
    return match.start(), end


def patch_profile(xml_text: str) -> tuple[str, PatchInfo]:
    info = detect_pause_binding(xml_text)

    if CONTROLS_MAP in xml_text or INPUT_FILTER in xml_text:
        raise ProfilePatchError("profile already contains Clean Pause additions")

    map_start, map_end = _find_named_block(xml_text, "actionmap", info.pause_map)
    map_text = xml_text[map_start:map_end]

    action_pattern = re.compile(
        rf"<action\b(?=[^>]*\bname\s*=\s*([\"']){re.escape(info.pause_action)}\1)[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    matches = list(action_pattern.finditer(map_text))
    if len(matches) != 1:
        raise ProfilePatchError(
            f"expected exactly one {info.pause_map}/{info.pause_action} action tag, found {len(matches)}"
        )

    action_match = matches[0]
    old_tag = action_match.group(0)
    new_tag = old_tag

    # A console command has no activation-mode argument. The retail pause action
    # commonly fires on both press and release, which would toggle Clean Pause
    # twice from one physical button press. Make it deliberately single-fire.
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

    # The physical bindings and keybind reference must remain untouched.
    for attr in ("xboxpad", "pspad", "keyboard", "noModifiers"):
        before = _attr_pattern(attr).search(old_tag)
        after = _attr_pattern(attr).search(new_tag)
        if (before.group(2) if before else None) != (after.group(2) if after else None):
            raise ProfilePatchError(f"patch unexpectedly changed {attr} on the pause action")

    patched_map = map_text[: action_match.start()] + new_tag + map_text[action_match.end() :]
    patched = xml_text[:map_start] + patched_map + xml_text[map_end:]

    newline = "\r\n" if "\r\n" in xml_text else "\n"
    indent = "\t" if "\t<actionmap" in xml_text else "  "
    inner = indent * 2

    controls_block = (
        newline
        + indent
        + f'<actionmap name="{CONTROLS_MAP}" priority="pure_include" exclusivity="0">'
        + newline
        + inner
        # Resume on release keeps the entire B press/release cycle behind the
        # actionPass filter, so gameplay never receives an orphaned B release.
        + f'<action name="{RESUME_ACTION}" onRelease="1" xboxpad="xi_b" pspad="pad_circle" consoleCmd="1" />'
        + newline
        + indent
        + "</actionmap>"
        + newline
    )

    # Keep the small custom map next to the source pause include map.
    _, new_map_end = _find_named_block(patched, "actionmap", info.pause_map)
    patched = patched[:new_map_end] + controls_block + patched[new_map_end:]

    filter_block = (
        indent
        + f'<actionfilter name="{INPUT_FILTER}" type="actionPass">'
        + newline
        + inner
        + f'<action name="{info.pause_action}" />'
        + newline
        + inner
        + f'<action name="{RESUME_ACTION}" />'
        + newline
        + indent
        + "</actionfilter>"
        + newline
        + newline
    )

    first_filter = re.search(r"^[ \t]*<actionfilter\b", patched, re.IGNORECASE | re.MULTILINE)
    if first_filter:
        patched = patched[: first_filter.start()] + filter_block + patched[first_filter.start() :]
    else:
        closing = re.search(r"</profile\s*>", patched, re.IGNORECASE)
        if not closing:
            raise ProfilePatchError("missing closing </profile>")
        patched = patched[: closing.start()] + filter_block + patched[closing.start() :]

    _validate_patch(patched, info)
    return patched, info


def _validate_patch(patched: str, info: PatchInfo) -> None:
    try:
        root = ET.fromstring(patched)
    except ET.ParseError as exc:
        raise ProfilePatchError(f"patched profile is invalid XML: {exc}") from exc

    if root.get("version") != info.profile_version:
        raise ProfilePatchError("patch changed the profile root version")

    pause_map = next(
        (m for m in root.findall("actionmap") if m.get("name") == info.pause_map),
        None,
    )
    if pause_map is None:
        raise ProfilePatchError("patched profile lost the retail pause map")
    pause_actions = [a for a in pause_map.findall("action") if a.get("name") == info.pause_action]
    if len(pause_actions) != 1:
        raise ProfilePatchError("patched profile has an unexpected pause action count")
    pause_action = pause_actions[0]
    if pause_action.get("consoleCmd") != "1" or pause_action.get("onPress") != "1":
        raise ProfilePatchError("pause action is not a single-fire console command")
    if any(pause_action.get(name) is not None for name in ("onRelease", "onHold", "always")):
        raise ProfilePatchError("pause action still has a second activation mode")
    if "xi_start" not in _device_inputs(pause_action, "xboxpad"):
        raise ProfilePatchError("patched pause action lost xi_start")

    controls = [m for m in root.findall("actionmap") if m.get("name") == CONTROLS_MAP]
    if len(controls) != 1:
        raise ProfilePatchError("expected exactly one Clean Pause controls map")
    resume = [a for a in controls[0].findall("action") if a.get("name") == RESUME_ACTION]
    if (
        len(resume) != 1
        or resume[0].get("onRelease") != "1"
        or resume[0].get("onPress") is not None
        or resume[0].get("xboxpad") != "xi_b"
        or resume[0].get("consoleCmd") != "1"
    ):
        raise ProfilePatchError("Clean Pause resume action contract is invalid")

    filters = [f for f in root.findall("actionfilter") if f.get("name") == INPUT_FILTER]
    if len(filters) != 1 or filters[0].get("type") != "actionPass":
        raise ProfilePatchError("Clean Pause actionPass filter contract is invalid")
    allowed = {a.get("name") for a in filters[0].findall("action")}
    if allowed != {info.pause_action, RESUME_ACTION}:
        raise ProfilePatchError(f"unexpected Clean Pause filter allow-list: {sorted(allowed)}")
