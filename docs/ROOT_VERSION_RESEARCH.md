# KCD2 keybind profile version research

## Why the version matters

CryEngine `CActionMapManager::LoadFromXML` requires a `version` attribute on the XML root and assigns that value to the manager's current in-memory action-map version before loading maps and filters.

It does **not** first compare the supplemental profile version with the already loaded vanilla profile version.

Therefore blindly loading a guessed `version="22"` would be unsafe even if the XML happened to parse.

## Version 22 evidence

KCD/CryEngine action-map profiles and current KCD2 mod examples use version `22`. KCD2 Keybinder also reads the retail `Libs/Config/defaultProfile.xml` and preserves its action-map structure when merging bindings.

This is enough to provide a version-22 supplemental profile, but not enough to assume every future retail build remains version 22.

## Implemented solution: runtime detection

The mod does not require the user to locate or extract the profile manually.

Current KCD2 exposes:

```lua
System.LoadTextFile(path)
```

The prototype uses it to read the effective virtual-filesystem file:

```text
Libs/Config/defaultProfile.xml
```

before calling `ActionMapManager.LoadFromXML()`.

Bootstrap policy:

```text
cannot read vanilla profile
    -> do not load supplemental input profile
    -> vanilla controls unchanged

cannot parse vanilla profile version
    -> do not load supplemental input profile
    -> vanilla controls unchanged

vanilla version != 22
    -> do not load v22 supplemental profile
    -> vanilla controls unchanged

vanilla version == 22
    -> validate/read packaged v22 profile
    -> LoadFromXML(v22 profile)
    -> verify custom filters
    -> enable gameplay-scoped interception
```

This turns an external installation detail into a fail-closed compatibility gate.

## Why the old probe remains useful

`tools/probe_profile_version.py` is retained as a diagnostic/development utility. It can inspect game PAKs directly if runtime `System.LoadTextFile` unexpectedly cannot resolve the effective profile on a particular storefront.

It is **not required** for normal installation or bootstrap.

## Remaining limitation

The project currently packages only:

```text
cleanPauseProfile_v22.xml
```

If a future KCD2 build reports another profile version, Clean Pause deliberately disables its interception rather than assuming the XML schema is compatible. Supporting a new version requires checking that version's retail profile/action schema and adding a corresponding validated supplemental profile.
