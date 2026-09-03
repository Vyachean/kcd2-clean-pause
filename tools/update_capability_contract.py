#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tools/validate_native_contract.py"
text = path.read_text(encoding="utf-8")

old = '''steam_resolver = native[
    native.index("bool ResolveProfileFrameworkSingleton"):
    native.index("bool ResolveGameFramework")
]
for needle in (
    "kSteam156FrameworkStorageRva",
    "kSteam156FrameworkVtableRva",
    "kGameFrameworkGetSystemSlot",
    "frameworkSystem != environment.system",
):
    if needle not in steam_resolver:
        raise SystemExit(f"Steam framework identity adapter contract missing: {needle}")
if "kGameGetFrameworkSlot" in steam_resolver:
    raise SystemExit("Steam framework adapter must not fall back to Xbox IGame[16]")

dispatcher = native[
    native.index("bool ResolveGameFramework"):
    native.index("bool ShouldSuppressProfileHudRootVisibility")
]
if "ResolveProfileFrameworkSingleton" not in dispatcher:
    raise SystemExit("framework dispatcher must route Steam through CCryAction singleton")
if "LegacyResolveGameFramework_Xbox156Only" not in dispatcher:
    raise SystemExit("framework dispatcher must retain the isolated Xbox adapter")
if "Storefront::XboxMicrosoftStore" not in dispatcher:
    raise SystemExit("framework dispatcher must scope legacy fallback to Xbox")
'''

new = '''profile_singleton_resolver = native[
    native.index("bool ResolveProfileFrameworkSingleton"):
    native.index("bool ResolveGameFramework")
]
for needle in (
    "FrameworkLocatorStrategy::ExactSingletonRva",
    "expectedFrameworkStorageRva",
    "expectedFrameworkVtableRva",
    "kGameFrameworkGetSystemSlot",
    "frameworkSystem != environment.system",
):
    if needle not in profile_singleton_resolver:
        raise SystemExit(f"profile singleton framework identity contract missing: {needle}")
if "Storefront::Steam" in profile_singleton_resolver:
    raise SystemExit("profile singleton framework resolver must not branch on storefront")
if "kGameGetFrameworkSlot" in profile_singleton_resolver:
    raise SystemExit("profile singleton framework resolver must not fall back to legacy IGame[16]")

dispatcher = native[
    native.index("bool ResolveGameFramework"):
    native.index("bool ShouldSuppressProfileHudRootVisibility")
]
for needle in (
    "FrameworkLocatorStrategy::ExactSingletonRva",
    "FrameworkLocatorStrategy::LegacyGameFrameworkSlot",
    "FrameworkLocatorStrategy::None",
    "ResolveProfileFrameworkSingleton",
    "LegacyResolveGameFramework_Xbox156Only",
):
    if needle not in dispatcher:
        raise SystemExit(f"framework strategy dispatcher contract missing: {needle}")
for storefront in (
    "Storefront::Steam",
    "Storefront::XboxMicrosoftStore",
    "Storefront::GOG",
    "Storefront::EpicGamesStore",
):
    if storefront in dispatcher:
        raise SystemExit(f"framework dispatcher must not branch on storefront: {storefront}")
'''

if old not in text:
    raise RuntimeError("stale framework contract block not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("updated stable native framework capability contract")
