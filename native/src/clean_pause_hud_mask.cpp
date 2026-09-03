#include "clean_pause_hud_mask.h"
#include "kcd2_abi.h"
#include "kcd2_runtime_support.h"

#include <atomic>
#include <cstdint>

namespace clean_pause::hud_mask {
namespace {

using namespace kcd2;
using runtime_support::InstallHook;
using runtime_support::IsExecutable;
using runtime_support::IsReadable;
using runtime_support::ResolveCompleteObjectByRtti;
using runtime_support::ValidateVtable;

// KCD2 1.5.6 CFlashUIElement listener storage and C_UIHudMask class layout.
// These are layout ABI facts verified by libKCD2, not storefront-specific RVAs.
constexpr std::size_t kHudListenersOffset = 0x1D0;
constexpr std::size_t kMaskListenerOffset = 0x10;
constexpr std::size_t kMaskVisibilityInterfaceOffset = 0x58;
constexpr std::size_t kMaskSourceMonitorOffset = 0x60;
constexpr std::size_t kMaskOnModuleMessageSlot = 3;
constexpr std::size_t kMaskIsElementVisibleSlot = 1;
constexpr std::size_t kSourceEventSlot = 0;
constexpr std::size_t kModuleMessageIdOffset = 0x08;
constexpr std::uint32_t kHudRefreshModuleMessageId = 52;
constexpr std::size_t kMaxListenerStorageBytes = 64 * 1024;
constexpr char kMaskRttiName[] = ".?AVC_UIHudMask@guimodule@wh@@";

using SourceEventFn = void(__fastcall*)(void*, void*, bool);
using OnModuleMessageFn = void(__fastcall*)(void*, void*);
using IsElementVisibleFn = bool(__fastcall*)(void*, std::uint8_t);

std::atomic<MutationObserver> g_observer{nullptr};
SourceEventFn g_originalSourceEvent{};
void* g_sourceEventTarget{};
OnModuleMessageFn g_originalOnModuleMessage{};
void* g_onModuleMessageTarget{};
std::atomic<void*> g_maskObject{nullptr};
std::atomic<void*> g_sourceMonitorObject{nullptr};
std::atomic<void*> g_hudElementObject{nullptr};

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

bool LoadCachedMaskObjects(void* hudElement, void*& mask, void*& sourceMonitor)
{
    mask = nullptr;
    sourceMonitor = nullptr;
    if (!hudElement || g_hudElementObject.load(std::memory_order_acquire) != hudElement)
        return false;

    mask = g_maskObject.load(std::memory_order_acquire);
    sourceMonitor = g_sourceMonitorObject.load(std::memory_order_acquire);
    if (!mask || !sourceMonitor)
        return false;
    if (!ValidateVtable(mask, kMaskOnModuleMessageSlot)
        || !ValidateVtable(sourceMonitor, kSourceEventSlot))
        return false;
    return true;
}

bool IsHudRefreshMessage(const void* message)
{
    if (!IsReadable(message, kModuleMessageIdOffset + sizeof(std::uint32_t)))
        return false;

    std::uint32_t id{};
    __try {
        id = *reinterpret_cast<const std::uint32_t*>(
            reinterpret_cast<const std::uint8_t*>(message) + kModuleMessageIdOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return id == kHudRefreshModuleMessageId;
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

    // MinHook patches the shared method body, not one C_UIHudMask instance. Only the
    // source-monitor object discovered from the current hud@0 may drive reconciliation.
    if (sourceMonitor == g_sourceMonitorObject.load(std::memory_order_acquire))
        NotifyAfterMutation();
}

void __fastcall HookOnModuleMessage(void* mask, void* message)
{
    // MinHook patches the class method globally. Ignore other C_UIHudMask instances,
    // and for the target instance react only to verified HUD-refresh message id 52.
    // Read the id before vanilla runs so the message does not need to outlive the call.
    const bool targetMask = mask == g_maskObject.load(std::memory_order_acquire);
    const bool refresh = targetMask && IsHudRefreshMessage(message);
    if (g_originalOnModuleMessage)
        g_originalOnModuleMessage(mask, message);
    if (refresh)
        NotifyAfterMutation();
}

} // namespace

bool EnsureHooks(void* hudElement, MutationObserver observer)
{
    if (!observer)
        return false;

    void* mask{};
    void* sourceMonitor{};
    const bool cached = LoadCachedMaskObjects(hudElement, mask, sourceMonitor);
    if (!cached && !FindMaskObjects(hudElement, mask, sourceMonitor))
        return false;

    const auto sourceTarget = reinterpret_cast<void*>(
        VFunc<SourceEventFn>(sourceMonitor, kSourceEventSlot));
    const auto moduleMessageTarget = reinterpret_cast<void*>(
        VFunc<OnModuleMessageFn>(mask, kMaskOnModuleMessageSlot));
    if (!IsExecutable(sourceTarget) || !IsExecutable(moduleMessageTarget))
        return false;

    if (cached && g_sourceEventTarget == sourceTarget
        && g_onModuleMessageTarget == moduleMessageTarget) {
        g_observer.store(observer, std::memory_order_release);
        return true;
    }

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

    // Publish the concrete instance identities before the observer. The detours
    // remain inert for unrelated instances and during partial installation.
    g_maskObject.store(mask, std::memory_order_release);
    g_sourceMonitorObject.store(sourceMonitor, std::memory_order_release);
    g_hudElementObject.store(hudElement, std::memory_order_release);
    g_observer.store(observer, std::memory_order_release);
    return true;
}

bool ReadCurrentVisibility(void* hudElement, bool* visible, std::size_t count)
{
    if (!visible || count != kHudElementCount)
        return false;

    void* mask{};
    void* sourceMonitor{};
    if (!LoadCachedMaskObjects(hudElement, mask, sourceMonitor)
        && !FindMaskObjects(hudElement, mask, sourceMonitor))
        return false;

    auto* visibilityInterface = reinterpret_cast<std::uint8_t*>(mask)
        + kMaskVisibilityInterfaceOffset;
    void* interfaceOwner{};
    std::uint32_t interfaceOffset{};
    if (!ResolveCompleteObjectByRtti(
            visibilityInterface, kMaskRttiName, interfaceOwner, interfaceOffset)
        || interfaceOwner != mask || interfaceOffset != kMaskVisibilityInterfaceOffset)
        return false;
    if (!ValidateVtable(visibilityInterface, kMaskIsElementVisibleSlot))
        return false;

    const auto isVisible = VFunc<IsElementVisibleFn>(
        visibilityInterface, kMaskIsElementVisibleSlot);
    if (!isVisible || !IsExecutable(reinterpret_cast<void*>(isVisible)))
        return false;

    __try {
        for (std::size_t i = 0; i < kHudElementCount; ++i)
            visible[i] = isVisible(visibilityInterface, static_cast<std::uint8_t>(i));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
}

} // namespace clean_pause::hud_mask
