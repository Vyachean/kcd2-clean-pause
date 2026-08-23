# KCD2 keybind profile version research

## What is confirmed

KCD2 keybind tooling reads the retail `Libs/Config/defaultProfile.xml` directly from the game's PAK and preserves that document when merging mod actions.

The open-source KCD2 Keybinder parses action maps as direct children of the document root and, when it must create a new map, uses:

```xml
<actionmap name="..." priority="pure_include" exclusivity="0">
```

It also emits console-command actions using the same attributes used by working KCD2 keybind mods.

Source:

- https://github.com/Destuur/KCD2Keybinder/blob/main/KCD2Keybinder.Core/Services/KeybindService.cs

Working KCD2 controller mods demonstrate actions such as:

```xml
<action
  name="MagusQuickSaveController"
  onHold="1"
  holdTriggerDelay="0.3"
  holdRepeatDelay="-1"
  xboxpad="xi_start"
  pspad="pad_start"
  consoleCmd="1" />
```

and other current mods package custom controller actions under `Libs/Config/defaultProfile.xml` / custom profile files.

## Version 22 evidence

CryEngine/KCD profiles use action-map version `22`; public modding examples also show:

```xml
<actionmap name="default" version="22">
```

This is strong evidence but not yet a direct extraction of the current KCD2 retail root document.

## Why the root version matters for `LoadFromXML`

`CActionMapManager::LoadFromXML` requires a `version` attribute on the root XML node and assigns it to the manager's current version before loading action maps/filters.

Therefore an incorrect root version is not something to silently guess in a release.

## Prototype policy

For an experimental runtime-loaded profile, `22` may be used only with explicit logging and a retail safety test. It must not be called proven until one of the following is obtained:

1. a direct current KCD2 `defaultProfile.xml` extraction showing the root version; or
2. a known-working current KCD2 mod whose standalone profile is loaded by `ActionMapManager.LoadFromXML` and whose root version is inspectable.

If the profile fails to load/enable in retail, the prototype must fail back to vanilla controls rather than attempting `InitActionMaps` or replacing the complete vanilla profile.
