# RC7f retail evidence — immediate crash on first pause

Source: Xbox Store KCD2 1.5.6 retail session on 2026-08-24 using `v0.1.0-rc.7f`.

## User-visible result

The game launched normally, but crashed immediately when the user attempted the first pause.

No repeat run is required.

## Last runtime markers

The native log proves the following sequence completed before the crash:

```text
rc7f race-free child-HUD-snapshot candidate active
Menu@0 render hook active
hud@0 subtitle-preservation hook active
hud@0 main-thread Update hook active
HUD visibility snapshot captured for all 28 clips (gameplay-pre-pause)
Clean Pause subtitle freeze: suppressed hud.ClearSubtitles
```

There is no later marker for:

- vanilla-pause HUD snapshot capture;
- gameplay HUD restore;
- Clean Pause entry;
- Menu render suppression observation.

Therefore the crash occurs after the complete pre-pause child snapshot and during the vanilla pause transition, before Clean Pause ownership is established.

## Root-cause correction

RC7f changed `IUIElement::GetMovieClip()` handling relative to RC7e: every returned `IFlashVariableObject*` was immediately passed to `Release()` after read/write.

That ownership assumption is not supported by the IUIElement API contract.

CryEngine's official FlashUI C++ documentation shows `IUIElement::GetMovieClip()` returning an `IFlashVariableObject*` for direct use without instructing the caller to release it. The same documentation separately warns that `IFlashVariableObject`s **created through the raw IFlashPlayer interface** must be released by the caller.

libKCD2 confirms `IFlashVariableObject::Release()` is destructive (`delete this` / scalar deleting destructor).

The RC7f sequence is therefore consistent with deleting movieclip wrappers owned/cached by the UI element during the pre-pause snapshot, then crashing when the following pause UI transition touches that state.

## RC7g ownership rule

For `IUIElement::GetMovieClip()` only:

- treat the returned pointer as borrowed/cached;
- use it only inside the current helper call;
- never store it in a snapshot/global;
- never call `Release()` on it;
- snapshots contain only visibility booleans.

This preserves the successful RC7e child-HUD mechanism without RC7e's cross-frame raw-pointer retention and without RC7f's destructive release.

## Additional instrumentation

RC7g adds two one-shot markers around the first `hud@0::Update` trampoline:

```text
hud@0 Update hook first entry ...
hud@0 Update original returned successfully
```

If a future crash remains, one retail log can distinguish an Update-detour/trampoline problem from child-snapshot ownership without a separate diagnostic launch.
