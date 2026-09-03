#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "native/src/clean_pause_native.cpp"
text = path.read_text(encoding="utf-8")

resolver_marker = '''bool LegacyResolveGameFramework_Xbox156Only(const RuntimeEnvironment& environment, void*& framework)\n{'''
if resolver_marker not in text:
    raise RuntimeError("legacy Xbox framework resolver marker not found")

diagnostic = r'''void LogLegacyXboxFrameworkRootEvidence(void* framework, void* getFrameworkTarget)
{
    static std::atomic_bool logged{false};
    if (!framework || logged.exchange(true, std::memory_order_acq_rel))
        return;

    HMODULE whGame = GetModuleHandleW(L"WHGame.dll");
    const auto* base = reinterpret_cast<const std::uint8_t*>(whGame);
    if (!base || !IsReadable(base, sizeof(IMAGE_DOS_HEADER))) {
        Log("Xbox framework root evidence unavailable: WHGame base unreadable");
        return;
    }

    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        Log("Xbox framework root evidence unavailable: invalid WHGame DOS header");
        return;
    }

    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (!IsReadable(nt, sizeof(*nt)) || nt->Signature != IMAGE_NT_SIGNATURE) {
        Log("Xbox framework root evidence unavailable: invalid WHGame PE header");
        return;
    }

    const auto imageBegin = reinterpret_cast<std::uintptr_t>(base);
    const auto imageEnd = imageBegin + nt->OptionalHeader.SizeOfImage;
    const auto imageRva = [&](const void* address) -> std::uint64_t {
        const auto value = reinterpret_cast<std::uintptr_t>(address);
        return value >= imageBegin && value < imageEnd
            ? static_cast<std::uint64_t>(value - imageBegin)
            : 0;
    };
    const auto inImage = [&](const void* address) {
        const auto value = reinterpret_cast<std::uintptr_t>(address);
        return value >= imageBegin && value < imageEnd;
    };

    void* vtable{};
    __try {
        vtable = *reinterpret_cast<void**>(framework);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        vtable = nullptr;
    }

    Log(
        "Xbox framework root evidence: WHGame=%p imageSize=0x%08lx framework=%p frameworkRva=0x%llx frameworkInImage=%s vtable=%p vtableRva=0x%llx vtableInImage=%s IGame[16]=%p accessorRva=0x%llx accessorInImage=%s",
        whGame,
        static_cast<unsigned long>(nt->OptionalHeader.SizeOfImage),
        framework,
        static_cast<unsigned long long>(imageRva(framework)),
        inImage(framework) ? "yes" : "no",
        vtable,
        static_cast<unsigned long long>(imageRva(vtable)),
        inImage(vtable) ? "yes" : "no",
        getFrameworkTarget,
        static_cast<unsigned long long>(imageRva(getFrameworkTarget)),
        inImage(getFrameworkTarget) ? "yes" : "no");

    unsigned totalCandidates{};
    unsigned loggedCandidates{};
    const auto* section = IMAGE_FIRST_SECTION(nt);
    for (unsigned index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        const DWORD flags = section->Characteristics;
        if (!(flags & IMAGE_SCN_MEM_READ) || !(flags & IMAGE_SCN_MEM_WRITE))
            continue;

        const auto* start = base + section->VirtualAddress;
        const std::size_t size = section->Misc.VirtualSize;
        for (std::size_t offset = 0; offset + sizeof(void*) <= size; offset += sizeof(void*)) {
            void* value{};
            __try {
                value = *reinterpret_cast<void* const*>(start + offset);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                continue;
            }
            if (value != framework)
                continue;

            ++totalCandidates;
            if (loggedCandidates >= 16)
                continue;

            char sectionName[9]{};
            std::memcpy(sectionName, section->Name, 8);
            const auto* slot = start + offset;
            Log(
                "Xbox framework storage candidate: section=%s slot=%p slotRva=0x%llx -> framework=%p",
                sectionName,
                slot,
                static_cast<unsigned long long>(imageRva(slot)),
                framework);
            ++loggedCandidates;
        }
    }

    Log(
        "Xbox framework storage scan complete: writablePointerMatches=%u logged=%u",
        totalCandidates,
        loggedCandidates);
}

'''
text = text.replace(resolver_marker, diagnostic + resolver_marker, 1)

old_return = '''    __try {
        frameworkSystem = getSystem ? getSystem(framework) : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        frameworkSystem = nullptr;
    }
    return frameworkSystem == environment.system;
}
'''
new_return = '''    __try {
        frameworkSystem = getSystem ? getSystem(framework) : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        frameworkSystem = nullptr;
    }
    if (frameworkSystem != environment.system)
        return false;

    LogLegacyXboxFrameworkRootEvidence(
        framework,
        reinterpret_cast<void*>(getFramework));
    return true;
}
'''
if old_return not in text:
    raise RuntimeError("legacy Xbox framework identity return block not found")
text = text.replace(old_return, new_return, 1)

old_env_log = '''        observedCandidate = result;
        Log("Xbox legacy runtime environment discovered; env=%p mainThread=%lu",
            result.base,
            static_cast<unsigned long>(result.mainThreadId));
        return true;
'''
new_env_log = '''        observedCandidate = result;
        const auto* moduleBase = reinterpret_cast<const std::uint8_t*>(whGame);
        const auto envRva = static_cast<unsigned long long>(result.base - moduleBase);
        Log("Xbox legacy runtime environment discovered; WHGame=%p env=%p envRva=0x%llx mainThread=%lu",
            whGame,
            result.base,
            envRva,
            static_cast<unsigned long>(result.mainThreadId));
        return true;
'''
if old_env_log not in text:
    raise RuntimeError("Xbox environment discovery log block not found")
text = text.replace(old_env_log, new_env_log, 1)

path.write_text(text, encoding="utf-8")
print("Xbox runtime root diagnostics added")
