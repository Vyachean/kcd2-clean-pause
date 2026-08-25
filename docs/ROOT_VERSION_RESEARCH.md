# KCD2 keybind profile version research

> **Status: historical research.** This file documents why the discarded runtime action-map/profile prototype treated XML versioning as a safety boundary. The current native implementation does not load a custom action profile. See [DESIGN.md](DESIGN.md).

## Evidence collected

KCD2 keybind tooling reads the retail `Libs/Config/defaultProfile.xml` from the game's PAK and preserves that document when merging mod actions.

The open-source KCD2 Keybinder parses action maps as direct children of the document root and, when it must create a new map, uses structures such as:

```xml
<actionmap name="..." priority="pure_include" exclusivity="0">
```

It also emits console-command actions using attributes seen in working KCD2 controller mods.

Reference:

- https://github.com/Destuur/KCD2Keybinder/blob/main/KCD2Keybinder.Core/Services/KeybindService.cs

Working controller mods also demonstrated custom actions bound to inputs such as `xi_start`, confirming that custom profile actions were technically possible in some contexts.

## Historical version-22 hypothesis

CryEngine/KCD profile examples use action-map version `22`, and public modding examples showed structures such as:

```xml
<actionmap name="default" version="22">
```

That was useful evidence for a prototype, but it was never accepted as a production contract merely by analogy.

## Why the root version mattered

The historical `CActionMapManager::LoadFromXML` investigation indicated that the root XML `version` participates in manager/profile loading. An incorrect value therefore could not safely be guessed in a release candidate that depended on runtime-loaded action maps.

The prototype policy was consequently fail-open: if the custom profile could not be proven to load safely, vanilla controls had to remain untouched.

## Current relevance

The current Clean Pause implementation no longer uses this path:

- it does not load a custom action profile;
- it does not replace `defaultProfile.xml`;
- it does not call `InitActionMaps`;
- it forwards the real Escape/Start input and reuses KCD2's own pause lifecycle.

This file is retained only as evidence behind the decision to reject profile/action-map ownership.
