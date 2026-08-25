#include "clean_pause_hud_mask.h"
#include "kcd2_abi.h"

#include <MinHook.h>

#include <atomic>
#include <cstdint>
#include <cstring>
#include <windows.h>

namespace clean_pause::hud_mask {
namespace {

using namespace kcd2;

// KCD2 1.5.6 CFlashUIElement listener storage and C_UIHudMask class layout.
// These are layout ABI facts verified by libKCD2, not storefront-specific RVAs.
constexpr std::size_t kHudListenersOffset = 0x1D0;
constexpr std::size_t kMaskListenerOffset = 0x10;
constexpr std::size_t kMaskSourceMonitorOffset = 0x60;
constexpr std::size_t kMaskOnModuleMessageSlot = 3;
constexpr std::size_t kSourceEventSlot = 0;
constexpr std::size_t kMaxListenerStorageBytes = 64 * 1024;
constexpr char kMaskRttiName[] = ".?AVC_UIHudMask@guimodule@wh@@";

using SourceEventFn = void(__fastcall*)(void*, void*, bool);
using OnModuleMessageFn = void(__fastcall*)(void*, void*);

std::atomic<MutationObserver> g_observer{nullptr};
SourceEventFn g_originalSourceEvent{};
void* g_sourceEventTarget{};
OnModuleMessageFn g_originalOnModuleMessage{};
void* g_onModuleMessageTarget{};

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

bool FindMaskObjects(void* hudElement, void*& owner, void*& sourceMonitor)
{
    owner = nullptr;
    sourceMonitor = nullptr;
    if (!hudElement || !IsReadable(hudElement, kHudListenersOffset + 3 * sizeof(void*)))
        return false;

    void** begin{};
    void** end{};
    __try {
        auto** vectorHeader = reinterpret_cast<void***>(
            reinterpret_cast<std::uint8_t*>(hudElement) + kHudListenersOffset);
        begin = vectorHeader[0];
        end = vectorHeader[1];
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    const auto beginAddress = reinterpret_cast<std::uintptr_t>(begin);
    const auto endAddress = reinterpret_cast<std::uintptr_t>(end);
    if (!begin || !end || endAddress < beginAddress)
        return false;
    const std::size_t storageBytes = static_cast<std::size_t>(endAddress - beginAddress);
    if (storageBytes == 0 || storageBytes > kMaxListenerStorageBytes
        || (storageBytes % sizeof(void*)) != 0)
        return false;

    for (auto address = beginAddress; address < endAddress; address += sizeof(void*)) {
        if (!IsReadable(reinterpret_cast<const void*>(address), sizeof(void*)))
            return false;

        void* candidate{};
        __try {
            candidate = *reinterpret_cast<void* const*>(address);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            continue;
        }
        if (!candidate)
            continue;

        void* candidateOwner{};
        std::uint32_t listenerOffset{};
        if (!ResolveCompleteObjectByRtti(candidate, kMaskRttiName, candidateOwner, listenerOffset)
            || listenerOffset != kMaskListenerOffset)
            continue;

        auto* source = reinterpret_cast<std::uint8_t*>(candidateOwner) + kMaskSourceMonitorOffset;
        void* sourceOwner{};
        std::uint32_t sourceOffset{};
        if (!ResolveCompleteObjectByRtti(source, kMaskRttiName, sourceOwner, sourceOffset)
            || sourceOwner != candidateOwner || sourceOffset != kMaskSourceMonitorOffset)
            continue;

        if (!ValidateVtable(candidateOwner, kMaskOnModuleMessageSlot)
            || !ValidateVtable(source, kSourceEventSlot))
            continue;

        owner = candidateOwner;
        sourceMonitor = source;
        return true;
    }
    return false;
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

void NotifyAfterMutation()
{
    const auto observer = g_observer.load(std::memory_order_acquire);
    if (observer)
        observer();
}

void __fastcall HookSourceEvent(void* sourceMonitor, void* source, bool active)
{
    if (g_originalSourceEvent)
        g_originalSourceEvent(sourceMonitor, source, active);
    NotifyAfterMutation();
}

void __fastcall HookOnModuleMessage(void* mask, void* message)
{
    if (g_originalOnModuleMessage)
        g_originalOnModuleMessage(mask, message);
    NotifyAfterMutation();
}

} // namespace

bool EnsureHooks(void* hudElement, MutationObserver observer)
{
    if (!observer)
        return false;

    void* mask{};
    void* sourceMonitor{};
    if (!FindMaskObjects(hudElement, mask, sourceMonitor))
        return false;

    const auto sourceTarget = reinterpret_cast<void*>(
        VFunc<SourceEventFn>(sourceMonitor, kSourceEventSlot));
    const auto moduleMessageTarget = reinterpret_cast<void*>(
        VFunc<OnModuleMessageFn>(mask, kMaskOnModuleMessageSlot));
    if (!IsExecutable(sourceTarget) || !IsExecutable(moduleMessageTarget))
        return false;

    // Partial installation is inert because the observer is published only after
    // both mutation paths are hooked successfully.
    if (!InstallHook(
            sourceTarget,
            reinterpret_cast<void*>(&HookSourceEvent),
            reinterpret_cast<void**>(&g_originalSourceEvent),
            g_sourceEventTarget))
        return false;
    if (!InstallHook(
            moduleMessageTarget,
            reinterpret_cast<void*>(&HookOnModuleMessage),
            reinterpret_cast<void**>(&g_originalOnModuleMessage),
            g_onModuleMessageTarget))
        return false;

    g_observer.store(observer, std::memory_order_release);
    return true;
}

} // namespace clean_pause::hud_mask
