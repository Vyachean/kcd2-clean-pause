#include "clean_pause_bubbles.h"
#include "kcd2_abi.h"

#include <MinHook.h>

#include <atomic>
#include <cstdint>
#include <cstring>
#include <windows.h>

namespace clean_pause::bubbles {
namespace {

using namespace kcd2;

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

struct CompleteObjectLocator64 {
    std::uint32_t signature;
    std::uint32_t offset;
    std::uint32_t cdOffset;
    std::int32_t typeDescriptorRva;
    std::int32_t classDescriptorRva;
    std::int32_t selfRva;
};
static_assert(sizeof(CompleteObjectLocator64) == 24);

bool IsReadable(const void* ptr, std::size_t size = 1)
{
    if (!ptr || size == 0)
        return false;

    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(ptr, &mbi, sizeof(mbi)) || mbi.State != MEM_COMMIT)
        return false;
    if ((mbi.Protect & PAGE_GUARD) || (mbi.Protect & PAGE_NOACCESS))
        return false;

    const auto begin = reinterpret_cast<std::uintptr_t>(ptr);
    const auto end = begin + size;
    const auto regionEnd = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
    return end >= begin && end <= regionEnd;
}

bool IsExecutable(const void* ptr)
{
    if (!ptr)
        return false;

    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(ptr, &mbi, sizeof(mbi)) || mbi.State != MEM_COMMIT)
        return false;

    const DWORD protection = mbi.Protect & 0xff;
    return protection == PAGE_EXECUTE
        || protection == PAGE_EXECUTE_READ
        || protection == PAGE_EXECUTE_READWRITE
        || protection == PAGE_EXECUTE_WRITECOPY;
}

bool ValidateVtable(void* object, std::size_t maxSlot)
{
    if (!IsReadable(object, sizeof(void*)))
        return false;

    void** vtable{};
    __try {
        vtable = *reinterpret_cast<void***>(object);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (!IsReadable(vtable, (maxSlot + 1) * sizeof(void*)))
        return false;

    __try {
        for (std::size_t slot = 0; slot <= maxSlot; ++slot)
            if (!IsExecutable(vtable[slot]))
                return false;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
}

bool ResolveCompleteObjectByRtti(
    void* subobject,
    const char* expectedName,
    void*& completeObject,
    std::uint32_t& subobjectOffset)
{
    completeObject = nullptr;
    subobjectOffset = 0;
    if (!subobject || !expectedName || !IsReadable(subobject, sizeof(void*)))
        return false;

    void** vtable{};
    const CompleteObjectLocator64* locator{};
    __try {
        vtable = *reinterpret_cast<void***>(subobject);
        if (!vtable || !IsReadable(vtable - 1, sizeof(void*) * 2))
            return false;
        locator = reinterpret_cast<const CompleteObjectLocator64* const*>(vtable)[-1];
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (!locator || !IsReadable(locator, sizeof(*locator)) || locator->signature != 1)
        return false;
    if (locator->selfRva <= 0 || locator->typeDescriptorRva <= 0 || locator->offset > 0x400)
        return false;

    HMODULE whGame = GetModuleHandleW(L"WHGame.dll");
    if (!whGame)
        return false;

    const auto* moduleBase = reinterpret_cast<const std::uint8_t*>(whGame);
    const auto* locatorBase = reinterpret_cast<const std::uint8_t*>(locator)
        - static_cast<std::size_t>(locator->selfRva);
    if (locatorBase != moduleBase)
        return false;

    const auto* typeDescriptor = moduleBase + static_cast<std::size_t>(locator->typeDescriptorRva);
    const std::size_t expectedLength = std::strlen(expectedName);
    if (!IsReadable(typeDescriptor, 16 + expectedLength + 1))
        return false;

    const char* typeName = reinterpret_cast<const char*>(typeDescriptor + 16);
    bool matches{};
    __try {
        matches = std::strcmp(typeName, expectedName) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        matches = false;
    }
    if (!matches)
        return false;

    auto* complete = reinterpret_cast<std::uint8_t*>(subobject) - locator->offset;
    if (!IsReadable(complete, sizeof(void*)))
        return false;

    completeObject = complete;
    subobjectOffset = locator->offset;
    return true;
}

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

bool InstallHook(void* target, void* detour, void** original, void*& installedTarget)
{
    if (!target || !detour || !original)
        return false;
    if (installedTarget)
        return installedTarget == target;

    const MH_STATUS create = MH_CreateHook(target, detour, original);
    if (create != MH_OK)
        return false;

    const MH_STATUS enable = MH_EnableHook(target);
    if (enable != MH_OK) {
        MH_RemoveHook(target);
        return false;
    }

    installedTarget = target;
    return true;
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

} // namespace

bool EnsureHooks(void* hudElement, void* flashUI)
{
    void* menu = ResolveMenu(flashUI);
    if (!menu)
        return false;

    void* bubbleInterface{};
    const bool cached = g_hudElementObject.load(std::memory_order_acquire) == hudElement
        && g_menuElement == menu;
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
    const auto menuSetVisibleTarget = reinterpret_cast<void*>(
        VFunc<SetVisibleFn>(menu, kUIElementSetVisibleSlot));
    if (!IsExecutable(bubbleUpdateTarget)
        || !IsExecutable(bubbleReleaseTarget)
        || !IsExecutable(menuSetVisibleTarget))
        return false;

    if (cached
        && g_bubbleUpdateTarget == bubbleUpdateTarget
        && g_bubbleReleaseTarget == bubbleReleaseTarget
        && g_menuSetVisibleTarget == menuSetVisibleTarget)
        return true;

    // Install suppression hooks before the menu-visibility hook. Until the final hook
    // is active, g_pauseMenuVisible remains false, so partial installation is inert.
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

    g_menuElement = menu;
    if (!InstallHook(
            menuSetVisibleTarget,
            reinterpret_cast<void*>(&HookMenuSetVisible),
            reinterpret_cast<void**>(&g_originalMenuSetVisible),
            g_menuSetVisibleTarget))
        return false;

    // Publish the exact object identity only after every required hook is installed.
    // Repeated discovery can safely retarget this to a recreated hud@0 instance while
    // the globally patched methods continue forwarding all unrelated objects.
    g_bubbleInterfaceObject.store(bubbleInterface, std::memory_order_release);
    g_hudElementObject.store(hudElement, std::memory_order_release);

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

} // namespace clean_pause::bubbles
