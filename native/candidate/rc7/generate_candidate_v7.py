from pathlib import Path
import subprocess
import sys
import tempfile

if len(sys.argv) != 3:
    raise SystemExit("usage: generate_candidate_v7.py <input.cpp> <output.cpp>")

source_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
v6 = Path(__file__).with_name("generate_candidate_v6.py")

with tempfile.TemporaryDirectory() as tmp:
    intermediate = Path(tmp) / "rc7f.cpp"
    subprocess.run([sys.executable, str(v6), str(source_path), str(intermediate)], check=True)
    source = intermediate.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"rc7g {label}: expected one match, got {count}")
    source = source.replace(old, new, 1)


# RC7f crashed immediately after a complete gameplay snapshot. The only ownership
# change versus RC7e at that point was Release() on every IUIElement::GetMovieClip()
# result. CryEngine's documented IUIElement usage returns the movie-clip pointer without
# a caller Release; explicit Release ownership is documented for raw IFlashPlayer-created
# variable objects instead. Treat GetMovieClip results as borrowed/cached: use only
# inside the current helper call, never store, never Release.
release_start = source.find("bool ReleaseFlashVariable(void* clip)\n{")
release_end = source.find("bool ResolveHudClipAccessor", release_start)
if release_start == -1 or release_end == -1:
    raise SystemExit("rc7g could not locate rc7f ReleaseFlashVariable helper")
source = source[:release_start] + source[release_end:]

replace_once(
    r'''        if (!clip || !ValidateObjectVtable(clip, {
                kFlashVariableReleaseSlot,
                kFlashVariableGetDisplayInfoSlot,
                kFlashVariableSetVisibleSlot })) {
            if (clip)
                ReleaseFlashVariable(clip);''',
    r'''        if (!clip || !ValidateObjectVtable(clip, {
                kFlashVariableGetDisplayInfoSlot,
                kFlashVariableSetVisibleSlot })) {''',
    "remove capture Release ownership",
)
replace_once(
    r'''        if (!ReleaseFlashVariable(clip))
            ok = false;
        if (!ok) {''',
    r'''        if (!ok) {''',
    "remove capture success Release",
)
replace_once(
    r'''        if (!clip || !ValidateObjectVtable(clip, {
                kFlashVariableReleaseSlot,
                kFlashVariableSetVisibleSlot })) {
            if (clip)
                ReleaseFlashVariable(clip);''',
    r'''        if (!clip || !ValidateObjectVtable(clip, {
                kFlashVariableSetVisibleSlot })) {''',
    "remove restore Release ownership",
)
replace_once(
    r'''        if (!ReleaseFlashVariable(clip))
            ok = false;
        if (!ok)
            return false;''',
    r'''        if (!ok)
            return false;''',
    "remove restore success Release",
)

# Add one-shot Update instrumentation. It is intentionally diagnostic-only and logs
# at most two lines for the lifetime of the process. If a future crash remains, one
# retail log distinguishes detour-entry/trampoline failure from snapshot ownership.
replace_once(
    "void* g_hudUpdateTarget{};",
    r'''void* g_hudUpdateTarget{};
std::atomic_bool g_hudUpdateFirstEntryLogged{false};
std::atomic_bool g_hudUpdateFirstReturnLogged{false};''',
    "add Update one-shot diagnostics",
)
replace_once(
    r'''void __fastcall HookHudUpdate(void* element, float deltaTime)
{
    if (g_originalHudUpdate)
        g_originalHudUpdate(element, deltaTime);

    if (element != g_hudElement || !g_cleanHidden.load(std::memory_order_acquire))''',
    r'''void __fastcall HookHudUpdate(void* element, float deltaTime)
{
    if (!g_hudUpdateFirstEntryLogged.exchange(true, std::memory_order_acq_rel))
        Log("hud@0 Update hook first entry; element=%p thread=%lu cleanHidden=%s",
            element, static_cast<unsigned long>(GetCurrentThreadId()),
            g_cleanHidden.load(std::memory_order_acquire) ? "true" : "false");

    if (g_originalHudUpdate)
        g_originalHudUpdate(element, deltaTime);

    if (!g_hudUpdateFirstReturnLogged.exchange(true, std::memory_order_acq_rel))
        Log("hud@0 Update original returned successfully");

    if (element != g_hudElement || !g_cleanHidden.load(std::memory_order_acquire))''',
    "instrument Update trampoline",
)

source = source.replace(
    "rc7f race-free child-HUD-snapshot candidate active; env=%p",
    "rc7g borrowed-movieclip child-HUD-snapshot candidate active; env=%p",
)
source = source.replace(
    "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7f race-free child-HUD-snapshot candidate",
    "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7g borrowed-movieclip child-HUD-snapshot candidate",
)

required = (
    "HudVisibilitySnapshot g_gameplayHudSnapshot",
    "HudVisibilitySnapshot g_vanillaPauseHudSnapshot",
    "CaptureHudVisibilitySnapshot",
    "RestoreHudVisibilitySnapshot",
    "getMovieClip(hud, kHudClipNames[i], nullptr)",
    "kFlashVariableGetDisplayInfoSlot",
    "kFlashVariableSetVisibleSlot",
    "HookHudUpdate",
    "hud@0 Update hook first entry",
    "hud@0 Update original returned successfully",
    'CaptureHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause")',
    'RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-visible-menu")',
    'RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-before-B")',
    "ReplayVanillaPauseToggle",
    "rc7g borrowed-movieclip child-HUD-snapshot candidate active",
)
for needle in required:
    if needle not in source:
        raise SystemExit(f"generated rc7g source missing: {needle}")

for forbidden in (
    "ReleaseFlashVariable",
    "kFlashVariableReleaseSlot",
    "FlashVariableReleaseFn",
    "HudClipSnapshot",
    "g_hudClipSnapshot",
    "snapshot.clip",
    "RestoreHudClipSnapshot()",
):
    if forbidden in source:
        raise SystemExit(f"generated rc7g source retained forbidden movieclip ownership: {forbidden}")

# Movie-clip pointers must be function-local only. Reject any snapshot or global pointer
# that could retain a borrowed clip across frames/transitions.
state_start = source.index("struct HudVisibilitySnapshot")
state_end = source.index("bool ShouldFreezeHudFunction", state_start)
state = source[state_start:state_end]
if "void* clip" in state or "void* clips" in state:
    raise SystemExit("rc7g snapshot state retains a borrowed movieclip pointer")

# Menu Render remains presentation-only.
menu_hook = source[source.index("void __fastcall HookMenuRender"):source.index("bool EnsureMenuRenderHook")]
for forbidden in ("GetMovieClip", "RestoreHudVisibilitySnapshot", "SetVisible", "Release"):
    if forbidden in menu_hook:
        raise SystemExit(f"Menu Render hook performs forbidden HUD lifecycle work: {forbidden}")

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(source, encoding="utf-8")
print(f"generated rc7g source: {out_path}")
