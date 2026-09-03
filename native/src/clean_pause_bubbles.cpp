#include "clean_pause_bubbles.h"
#include "kcd2_abi.h"
#include "kcd2_runtime_support.h"

#include <atomic>
#include <cstdint>

namespace clean_pause::bubbles {
namespace {

using namespace kcd2;
using runtime_support::InstallHook;
using runtime_support::IsExecutable;
using runtime_support::IsReadable;
using runtime_support::ResolveCompleteObjectByRtti;
using runtime_support::ValidateVtable;

// KCD2 1.5.6 CFlashUIElement stores its IUIElementEventListener vector at +0x1D0.
// C_UIHudBubbles binds to hud@0 as an IUIElementEventListener subobject at +0x10 and
// exposes its framework I_UIHudBubbles interface at +0x58. These are class-layout ABI
// facts, not WHGame.dll RVAs; the concrete object is discovered at runtime by MSVC RTTI.
constexpr std::size_t kHudListenersOffset = 0x1D0;
constexpr std::size_t kBubbleListenerOffset = 0x10;
constexpr std::size_t kBubbleInterfaceOffset = 0x58;
constexpr std::size_t kBubbleUpdateSlot = 1;
constexpr std::size_t kBubbleReleaseSlot = 3;
constexpr std::size_t kBubbleSetTextSlot = 4;
constexpr std::size_t kBubbleSetAnchorSlot = 5;
constexpr std::size_t kMaxListenerStorageBytes = 64 * 1024;
constexpr char kBubbleRttiName[] = ".?AVC_UIHudBubbles@guimodule@wh@@";

using BubbleUpdateFn = void(__fastcall*)(void*);
using BubbleReleaseFn = void(__fastcall*)(void*, std::uint32_t);

std::atomic_bool g_pauseMenuVisible{false};
void* g_menuElement{};
SetVisibleFn g_originalMenuSetVisible{};
void* g_menuSetVisibleTarget{};
BubbleUpdateFn g_originalBubbleUpdate{};
void* g_bubbleUpdateTarget{};
BubbleReleaseFn g_originalBubbleRelease{};
void* g_bubbleReleaseTarget{};
std::atomic<void*> g_bubbleInterfaceObject{nullptr};
std::atomic<void*> g_hudElementObject{nullptr};
std::atomic<HudRootVisibilityFilterFn> g_hudRootVisibilityFilter{nullptr};

void* FindBubbleInterface(void* hudElement)
{
    if (!hudElement || !IsReadable(hudElement, kHudListenersOffset + 3 * sizeof(void*)))
        return nullptr;

    void** begin{};
    void** end{};
    __try {
        auto** vectorHeader = reinterpret_cast<void***>(
            reinterpret_cast<std::uint8_t*>(hudElement) + kHudListenersOffset);
        begin = vectorHeader[0];
        end = vectorHeader[1];
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }

    const auto beginAddress = reinterpret_cast<std::uintptr_t>(begin);
    const auto endAddress = reinterpret_cast<std::uintptr_t>(end);
    if (!begin || !end || endAddress < beginAddress)
        return nullptr;
    const std::size_t storageBytes = static_cast<std::size_t>(endAddress - beginAddress);
    if (storageBytes == 0 || storageBytes > kMaxListenerStorageBytes
        || (storageBytes % sizeof(void*)) != 0)
        return nullptr;

    // The KCD2 listener storage is a vector, but scanning pointer-sized cells keeps
    // discovery tolerant of any listener metadata stored beside the actual pointer.
    for (auto address = beginAddress; address < endAddress; address += sizeof(void*)) {
        if (!IsReadable(reinterpret_cast<const void*>(address), sizeof(void*)))
            return nullptr;

        void* candidate{};
        __try {
            candidate = *reinterpret_cast<void* const*>(address);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            continue;
        }
        if (!candidate)
            continue;

        void* owner{};
        std::uint32_t listenerOffset{};
        if (!ResolveCompleteObjectByRtti(candidate, kBubbleRttiName, owner, listenerOffset)
            || listenerOffset != kBubbleListenerOffset)
            continue;

        auto* bubbleInterface = reinterpret_cast<std::uint8_t*>(owner) + kBubbleInterfaceOffset;
        void* interfaceOwner{};
        std::uint32_t interfaceOffset{};
        if (!ResolveCompleteObjectByRtti(
                bubbleInterface, kBubbleRttiName, interfaceOwner, interfaceOffset)
            || interfaceOwner != owner || interfaceOffset != kBubbleInterfaceOffset)
            continue;

        if (!ValidateVtable(bubbleInterface, kBubbleSetAnchorSlot))
            continue;
        return bubbleInterface;
    }
    return nullptr;
}

void* ResolveMenu(void* flashUI)
{
    if (!flashUI || !ValidateVtable(flashUI, kFlashUIGetElementByInstanceStrSlot))
        return nullptr;

    const auto getElement = VFunc<GetUIElementByInstanceStrFn>(
        flashUI, kFlashUIGetElementByInstanceStrSlot);
    if (!getElement)
        return nullptr;

    void* menu{};
    __try {
        menu = getElement(flashUI, "Menu@0");
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }
    if (!menu || !ValidateVtable(menu, kUIElementIsVisibleSlot))
        return nullptr;
    return menu;
}

void __fastcall HookBubbleUpdate(void* bubbles)
{
    // MinHook patches the shared class method body. Suppress only the concrete
    // I_UIHudBubbles object discovered from this hud@0 instance.
    const bool target = bubbles == g_bubbleInterfaceObject.load(std::memory_order_acquire);
    if (target && g_pauseMenuVisible.load(std::memory_order_acquire))
        return;
    if (g_originalBubbleUpdate)
        g_originalBubbleUpdate(bubbles);
}

void __fastcall HookBubbleRelease(void* bubbles, std::uint32_t bubbleId)
{
    const bool target = bubbles == g_bubbleInterfaceObject.load(std::memory_order_acquire);
    if (target && g_pauseMenuVisible.load(std::memory_order_acquire))
        return;
    if (g_originalBubbleRelease)
        g_originalBubbleRelease(bubbles, bubbleId);
}

void __fastcall HookMenuSetVisible(void* element, bool visible)
{
    const bool isHudRoot = element == g_hudElementObject.load(std::memory_order_acquire);
    const auto hudFilter = g_hudRootVisibilityFilter.load(std::memory_order_acquire);
    if (isHudRoot && hudFilter && hudFilter(visible))
        return;

    const bool isPauseMenu = element == g_menuElement;
    if (isPauseMenu && visible)
        g_pauseMenuVisible.store(true, std::memory_order_release);

    if (g_originalMenuSetVisible)
        g_originalMenuSetVisible(element, visible);

    // Keep the freeze active through vanilla's SetVisible(false) callbacks. The first
    // bubble update after SetVisible returns can then reconcile any genuinely stale line.
    if (isPauseMenu && !visible)
        g_pauseMenuVisible.store(false, std::memory_order_release);
}

bool EnsureSharedVisibilityHook(void* hudElement, void* menu)
{
    if (!hudElement || !menu)
        return false;

    const auto menuSetVisibleTarget = reinterpret_cast<void*>(
        VFunc<SetVisibleFn>(menu, kUIElementSetVisibleSlot));
    if (!IsExecutable(menuSetVisibleTarget))
        return false;

    // Publish identities before enabling the shared method hook. Any immediate call
    // after MH_EnableHook can then be classified as Menu@0, hud@0, or unrelated.
    g_menuElement = menu;
    g_hudElementObject.store(hudElement, std::memory_order_release);
    if (!InstallHook(
            menuSetVisibleTarget,
            reinterpret_cast<void*>(&HookMenuSetVisible),
            reinterpret_cast<void**>(&g_originalMenuSetVisible),
            g_menuSetVisibleTarget))
        return false;

    bool visible{};
    const auto isVisible = VFunc<IsVisibleFn>(menu, kUIElementIsVisibleSlot);
    __try {
        visible = isVisible && isVisible(menu);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        visible = false;
    }
    g_pauseMenuVisible.store(visible, std::memory_order_release);
    return true;
}

} // namespace

void SetHudRootVisibilityFilter(HudRootVisibilityFilterFn filter)
{
    g_hudRootVisibilityFilter.store(filter, std::memory_order_release);
}

bool EnsureHooks(void* hudElement, void* flashUI)
{
    void* menu = ResolveMenu(flashUI);
    if (!menu)
        return false;

    // Capture cache identity before the shared visibility hook republishes the current
    // hud/menu objects. Otherwise a recreated HUD would incorrectly appear cached.
    const bool cached = g_hudElementObject.load(std::memory_order_acquire) == hudElement
        && g_menuElement == menu;
    if (!EnsureSharedVisibilityHook(hudElement, menu))
        return false;

    void* bubbleInterface{};
    if (cached)
        bubbleInterface = g_bubbleInterfaceObject.load(std::memory_order_acquire);
    if (!bubbleInterface)
        bubbleInterface = FindBubbleInterface(hudElement);
    if (!bubbleInterface)
        return false;

    const auto bubbleUpdateTarget = reinterpret_cast<void*>(
        VFunc<BubbleUpdateFn>(bubbleInterface, kBubbleUpdateSlot));
    const auto bubbleReleaseTarget = reinterpret_cast<void*>(
        VFunc<BubbleReleaseFn>(bubbleInterface, kBubbleReleaseSlot));
    if (!IsExecutable(bubbleUpdateTarget) || !IsExecutable(bubbleReleaseTarget))
        return false;

    if (cached
        && g_bubbleUpdateTarget == bubbleUpdateTarget
        && g_bubbleReleaseTarget == bubbleReleaseTarget)
        return true;

    if (!InstallHook(
            bubbleUpdateTarget,
            reinterpret_cast<void*>(&HookBubbleUpdate),
            reinterpret_cast<void**>(&g_originalBubbleUpdate),
            g_bubbleUpdateTarget))
        return false;
    if (!InstallHook(
            bubbleReleaseTarget,
            reinterpret_cast<void*>(&HookBubbleRelease),
            reinterpret_cast<void**>(&g_originalBubbleRelease),
            g_bubbleReleaseTarget))
        return false;

    // Repeated discovery can safely retarget this to a recreated hud@0 instance while
    // the globally patched methods continue forwarding all unrelated objects.
    g_bubbleInterfaceObject.store(bubbleInterface, std::memory_order_release);
    return true;
}

} // namespace clean_pause::bubbles
