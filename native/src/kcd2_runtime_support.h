#pragma once

#include <MinHook.h>

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <windows.h>

namespace clean_pause::runtime_support {

// Shared low-level helpers for runtime-discovered KCD2 objects. These helpers do
// not encode storefront/build policy; callers remain responsible for selecting a
// validated BuildProfile/ABI before using version-specific object layouts.

struct CompleteObjectLocator64 {
    std::uint32_t signature;
    std::uint32_t offset;
    std::uint32_t cdOffset;
    std::int32_t typeDescriptorRva;
    std::int32_t classDescriptorRva;
    std::int32_t selfRva;
};
static_assert(sizeof(CompleteObjectLocator64) == 24);

inline bool IsReadable(const void* ptr, std::size_t size = 1)
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

inline bool IsExecutable(const void* ptr)
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

inline bool ValidateVtable(void* object, std::size_t maxSlot)
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
        for (std::size_t slot = 0; slot <= maxSlot; ++slot) {
            if (!IsExecutable(vtable[slot]))
                return false;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
}

inline bool ResolveCompleteObjectByRtti(
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

inline bool InstallHook(
    void* target,
    void* detour,
    void** original,
    void*& installedTarget)
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
        *original = nullptr;
        return false;
    }

    installedTarget = target;
    return true;
}

} // namespace clean_pause::runtime_support
