#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tools/validate_native_contract.py"
text = path.read_text(encoding="utf-8")

old = '''dispatcher = native[
    native.index("bool ResolveGameFramework"):
    native.index("bool ShouldSuppressProfileHudRootVisibility")
]
for needle in (
    "FrameworkLocatorStrategy::ExactPointerStorageRva",
    "FrameworkLocatorStrategy::ExactObjectRva",
    "FrameworkLocatorStrategy::None",
    "ResolveProfileFramework",
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

new = '''for needle in (
    "FrameworkLocatorStrategy::ExactPointerStorageRva",
    "FrameworkLocatorStrategy::ExactObjectRva",
    "FrameworkLocatorStrategy::None",
):
    if needle not in profile_framework_resolver:
        raise SystemExit(f"framework locator strategy contract missing: {needle}")

dispatcher = native[
    native.index("bool ResolveGameFramework"):
    native.index("bool ShouldSuppressProfileHudRootVisibility")
]
if "return ResolveProfileFramework(environment, framework);" not in dispatcher:
    raise SystemExit("framework dispatcher must delegate to the unified profile resolver")
for storefront in (
    "Storefront::Steam",
    "Storefront::XboxMicrosoftStore",
    "Storefront::GOG",
    "Storefront::EpicGamesStore",
):
    if storefront in profile_framework_resolver or storefront in dispatcher:
        raise SystemExit(f"framework resolution must not branch on storefront: {storefront}")
'''

if old not in text:
    raise RuntimeError("stale framework dispatcher checker block not found")
text = text.replace(old, new, 1)
text = text.replace(
    'raise SystemExit(f"profile singleton framework identity contract missing: {needle}")',
    'raise SystemExit(f"profile framework identity contract missing: {needle}")',
)
text = text.replace(
    'raise SystemExit("profile singleton framework resolver must not branch on storefront")',
    'raise SystemExit("profile framework resolver must not branch on storefront")',
)
path.write_text(text, encoding="utf-8")
print("unified framework checker fixed")
