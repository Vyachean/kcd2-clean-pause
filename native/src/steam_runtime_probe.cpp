#include "steam_runtime_probe.h"

#include <TlHelp32.h>
#include <windows.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#ifndef CLEAN_PAUSE_VERSION
#define CLEAN_PAUSE_VERSION "unknown"
#endif
#ifndef CLEAN_PAUSE_BUILD_ID
#define CLEAN_PAUSE_BUILD_ID "unknown"
#endif

namespace clean_pause::steam_probe {
namespace {

HMODULE g_selfModule{};
SRWLOCK g_logLock = SRWLOCK_INIT;

constexpr DWORD kWaitForWhGameMs = 60'000;
constexpr DWORD kWaitForGameMs = 30'000;
constexpr DWORD kPollMs = 100;

constexpr std::uint32_t kReportedSteamTimestamp = 0x6a350e20;
constexpr std::uint32_t kReportedSteamImageSize = 0x05b2d000;
constexpr std::uint32_t kReportedSteamChecksum = 0x00000000;

constexpr std::size_t kSteamScriptSystemOffset = 0x28;
constexpr std::size_t kSteamInputOffset = 0x40;
constexpr std::size_t kSteamGameOffset = 0x90;
constexpr std::size_t kSteamConsoleOffset = 0xA8;
constexpr std::size_t kSteamSystemOffset = 0xB8;
constexpr std::size_t kSteamFlashUiHypothesisOffset = 0x120;

constexpr std::size_t kXboxScriptSystemOffset = 0x30;
constexpr std::size_t kXboxInputOffset = 0x48;
constexpr std::size_t kXboxGameOffset = 0x98;
constexpr std::size_t kXboxSystemOffset = 0xC8;
constexpr std::size_t kXboxFlashUiOffset = 0x140;
constexpr std::size_t kXboxMainThreadIdOffset = 0x1B0;

constexpr std::size_t kInputPostInputEventSlot = 13;
constexpr std::size_t kGameGetLongNameSlot = 12;
constexpr std::size_t kGameGetNameSlot = 13;
constexpr std::size_t kGameGetFrameworkSlot = 16;
constexpr std::size_t kGameFrameworkPauseGameSlot = 13;
constexpr std::size_t kGameFrameworkGetSystemSlot = 19;
constexpr std::size_t kFlashUiGetElementSlot = 18;

struct ImageView {
    std::uint8_t* base{};
    IMAGE_NT_HEADERS64* nt{};
    IMAGE_SECTION_HEADER* sections{};
    unsigned sectionCount{};
};

std::wstring LogPath()
{
    wchar_t path[MAX_PATH]{};
    const DWORD length = GetModuleFileNameW(g_selfModule, path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH)
        return L"kcd2_clean_pause_steam_probe.log";

    std::wstring result(path, length);
    const auto slash = result.find_last_of(L"\\/");
    if (slash != std::wstring::npos)
        result.resize(slash + 1);
    else
        result.clear();
    result += L"kcd2_clean_pause_steam_probe.log";
    return result;
}

void Log(const char* format, ...)
{
    char message[2048]{};
    va_list args;
    va_start(args, format);
    const int count = vsnprintf(message, sizeof(message) - 1, format, args);
    va_end(args);
    if (count <= 0)
        return;

    SYSTEMTIME now{};
    GetLocalTime(&now);
    char line[2304]{};
    const int lineCount = snprintf(
        line,
        sizeof(line) - 1,
        "[%02u:%02u:%02u.%03u] %s\r\n",
        now.wHour,
        now.wMinute,
        now.wSecond,
        now.wMilliseconds,
        message);
    if (lineCount <= 0)
        return;

    AcquireSRWLockExclusive(&g_logLock);
    const std::wstring path = LogPath();
    HANDLE file = CreateFileW(
        path.c_str(),
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file != INVALID_HANDLE_VALUE) {
        DWORD written{};
        WriteFile(file, line, static_cast<DWORD>(lineCount), &written, nullptr);
        CloseHandle(file);
    }
    ReleaseSRWLockExclusive(&g_logLock);
}

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

bool ReadPointer(const std::uint8_t* base, std::size_t offset, void*& value)
{
    value = nullptr;
    if (!IsReadable(base + offset, sizeof(void*)))
        return false;
    __try {
        value = *reinterpret_cast<void* const*>(base + offset);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        value = nullptr;
        return false;
    }
}

bool ReadDword(const std::uint8_t* base, std::size_t offset, DWORD& value)
{
    value = 0;
    if (!IsReadable(base + offset, sizeof(DWORD)))
        return false;
    __try {
        value = *reinterpret_cast<const DWORD*>(base + offset);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        value = 0;
        return false;
    }
}

void* ExecutableSlot(void* object, std::size_t slot)
{
    if (!IsReadable(object, sizeof(void*)))
        return nullptr;

    void** vtable{};
    __try {
        vtable = *reinterpret_cast<void***>(object);
        if (!IsReadable(vtable, (slot + 1) * sizeof(void*)))
            return nullptr;
        void* target = vtable[slot];
        return IsExecutable(target) ? target : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }
}

bool SafeCallPointer(void* target, void* object, void*& result)
{
    result = nullptr;
    if (!IsExecutable(target) || !object)
        return false;
    using Fn = void*(__fastcall*)(void*);
    __try {
        result = reinterpret_cast<Fn>(target)(object);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        result = nullptr;
        return false;
    }
}

bool SafeCallString(void* target, void* object, const char*& result)
{
    result = nullptr;
    if (!IsExecutable(target) || !object)
        return false;
    using Fn = const char*(__fastcall*)(void*);
    __try {
        result = reinterpret_cast<Fn>(target)(object);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        result = nullptr;
        return false;
    }
}

bool CopyAscii(const char* source, char* destination, std::size_t capacity)
{
    if (!source || !destination || capacity == 0)
        return false;
    __try {
        std::size_t index = 0;
        for (; index + 1 < capacity; ++index) {
            const char c = source[index];
            destination[index] = c;
            if (c == '\0')
                return true;
            const unsigned char byte = static_cast<unsigned char>(c);
            if (byte < 0x20 || byte > 0x7e) {
                destination[index] = '\0';
                return false;
            }
        }
        destination[capacity - 1] = '\0';
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        destination[0] = '\0';
        return false;
    }
}

bool GetImageView(HMODULE module, ImageView& view)
{
    view = {};
    auto* base = reinterpret_cast<std::uint8_t*>(module);
    if (!IsReadable(base, sizeof(IMAGE_DOS_HEADER)))
        return false;
    auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE)
        return false;

    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (!IsReadable(nt, sizeof(*nt)) || nt->Signature != IMAGE_NT_SIGNATURE)
        return false;

    view.base = base;
    view.nt = nt;
    view.sections = IMAGE_FIRST_SECTION(nt);
    view.sectionCount = nt->FileHeader.NumberOfSections;
    return true;
}

std::uint8_t* FindAscii(const ImageView& image, const char* text)
{
    const std::size_t textSize = std::strlen(text);
    for (unsigned index = 0; index < image.sectionCount; ++index) {
        const auto& section = image.sections[index];
        if (!(section.Characteristics & IMAGE_SCN_MEM_READ))
            continue;
        auto* start = image.base + section.VirtualAddress;
        const std::size_t size = section.Misc.VirtualSize;
        if (size < textSize || !IsReadable(start, size))
            continue;
        for (std::size_t offset = 0; offset + textSize <= size; ++offset) {
            if (std::memcmp(start + offset, text, textSize) == 0)
                return start + offset;
        }
    }
    return nullptr;
}

std::vector<std::uint8_t*> FindLeaXrefs(const ImageView& image, const std::uint8_t* target)
{
    std::vector<std::uint8_t*> matches;
    for (unsigned index = 0; index < image.sectionCount; ++index) {
        const auto& section = image.sections[index];
        if (!(section.Characteristics & IMAGE_SCN_MEM_EXECUTE))
            continue;
        auto* start = image.base + section.VirtualAddress;
        const std::size_t size = section.Misc.VirtualSize;
        if (size < 7 || !IsReadable(start, size))
            continue;
        for (std::size_t offset = 0; offset + 7 <= size; ++offset) {
            auto* instruction = start + offset;
            if (instruction[0] != 0x48 || instruction[1] != 0x8d || instruction[2] != 0x15)
                continue;
            std::int32_t displacement{};
            std::memcpy(&displacement, instruction + 3, sizeof(displacement));
            if (instruction + 7 + displacement == target)
                matches.push_back(instruction);
        }
    }
    return matches;
}

bool MatchBytes(const std::uint8_t* at, const std::uint8_t* expected, std::size_t size)
{
    return IsReadable(at, size) && std::memcmp(at, expected, size) == 0;
}

bool ResolveConsoleFieldStorage(
    const ImageView& image,
    const std::vector<std::uint8_t*>& xrefs,
    std::uint8_t*& storage)
{
    storage = nullptr;
    static constexpr std::uint8_t kNewContext[7] = {0x4c, 0x8b, 0x92, 0x18, 0x01, 0x00, 0x00};
    static constexpr std::uint8_t kMovRip[3] = {0x48, 0x8b, 0x0d};

    for (auto* xref : xrefs) {
        std::uint8_t* mov{};
        const auto xrefRva = static_cast<unsigned long long>(xref - image.base);
        if (xref >= image.base + 0x17 && MatchBytes(xref - 7, kNewContext, sizeof(kNewContext))) {
            mov = xref - 0x17;
            Log("anchor xref rva=0x%llx matches KCD2 1.4+ context", xrefRva);
        } else if (xref >= image.base + 7 && MatchBytes(xref - 7, kMovRip, sizeof(kMovRip))) {
            mov = xref - 7;
            Log("anchor xref rva=0x%llx matches legacy context", xrefRva);
        } else {
            Log("anchor xref rva=0x%llx has unknown context", xrefRva);
            continue;
        }

        if (!MatchBytes(mov, kMovRip, sizeof(kMovRip)) || !IsReadable(mov, 7)) {
            Log("candidate pConsole MOV at rva=0x%llx failed opcode validation",
                static_cast<unsigned long long>(mov - image.base));
            continue;
        }

        std::int32_t displacement{};
        std::memcpy(&displacement, mov + 3, sizeof(displacement));
        auto* candidate = mov + 7 + displacement;
        const auto begin = reinterpret_cast<std::uintptr_t>(image.base);
        const auto end = begin + image.nt->OptionalHeader.SizeOfImage;
        const auto address = reinterpret_cast<std::uintptr_t>(candidate);
        if (address < begin || address + sizeof(void*) > end) {
            Log("candidate pConsole field storage is outside WHGame image");
            continue;
        }
        storage = candidate;
        Log("resolved pConsole field storage rva=0x%llx",
            static_cast<unsigned long long>(storage - image.base));
        return true;
    }
    return false;
}

std::string ModuleNameForAddress(void* address, std::uintptr_t& rva)
{
    rva = 0;
    if (!address)
        return "<null>";

    HMODULE module{};
    if (!GetModuleHandleExA(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCSTR>(address),
            &module))
        return "<unknown>";

    char path[MAX_PATH]{};
    if (!GetModuleFileNameA(module, path, MAX_PATH))
        return "<unknown>";
    const char* name = std::strrchr(path, '\\');
    if (!name)
        name = std::strrchr(path, '/');
    name = name ? name + 1 : path;
    rva = reinterpret_cast<std::uintptr_t>(address) - reinterpret_cast<std::uintptr_t>(module);
    return name;
}

void LogSlot(const char* label, void* object, std::size_t slot)
{
    void* target = ExecutableSlot(object, slot);
    if (!target) {
        Log("%s slot=%zu unavailable", label, slot);
        return;
    }
    std::uintptr_t rva{};
    const std::string module = ModuleNameForAddress(target, rva);
    Log("%s slot=%zu target=%p owner=%s+0x%llx",
        label,
        slot,
        target,
        module.c_str(),
        static_cast<unsigned long long>(rva));
}

void LogField(const std::uint8_t* env, const char* label, std::size_t offset, std::size_t slot)
{
    void* value{};
    if (!ReadPointer(env, offset, value)) {
        Log("field %s +0x%zx unreadable", label, offset);
        return;
    }
    Log("field %s +0x%zx = %p", label, offset, value);
    if (value && slot != static_cast<std::size_t>(-1))
        LogSlot(label, value, slot);
}

std::vector<DWORD> CurrentProcessThreadIds()
{
    std::vector<DWORD> result;
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snapshot == INVALID_HANDLE_VALUE)
        return result;

    THREADENTRY32 entry{};
    entry.dwSize = sizeof(entry);
    const DWORD pid = GetCurrentProcessId();
    if (Thread32First(snapshot, &entry)) {
        do {
            if (entry.th32OwnerProcessID == pid)
                result.push_back(entry.th32ThreadID);
            entry.dwSize = sizeof(entry);
        } while (Thread32Next(snapshot, &entry));
    }
    CloseHandle(snapshot);
    std::sort(result.begin(), result.end());
    return result;
}

void LogThreadIdCandidates(const std::uint8_t* env)
{
    const auto threads = CurrentProcessThreadIds();
    Log("current process has %zu threads during probe", threads.size());
    unsigned matches{};
    for (std::size_t offset = 0x140; offset <= 0x1d0; offset += 4) {
        DWORD value{};
        if (!ReadDword(env, offset, value) || value == 0)
            continue;
        if (std::binary_search(threads.begin(), threads.end(), value)) {
            Log("gEnv thread-id candidate: +0x%zx = %lu", offset, static_cast<unsigned long>(value));
            ++matches;
        }
    }
    if (matches == 0)
        Log("no current-process thread id found in gEnv range +0x140..+0x1d0");

    DWORD xboxValue{};
    if (ReadDword(env, kXboxMainThreadIdOffset, xboxValue))
        Log("Xbox-profile mainThread field hypothesis +0x%zx = %lu",
            kXboxMainThreadIdOffset,
            static_cast<unsigned long>(xboxValue));
}

void ProbeStandardProfile(std::uint8_t* env)
{
    Log("probing standard KCD2/CryEngine layout at gEnv=%p", env);
    LogField(env, "pScriptSystem[standard]", kSteamScriptSystemOffset, 6);
    LogField(env, "pInput[standard]", kSteamInputOffset, kInputPostInputEventSlot);
    LogField(env, "pGame[standard]", kSteamGameOffset, kGameGetFrameworkSlot);
    LogField(env, "pConsole[standard]", kSteamConsoleOffset, 0);
    LogField(env, "pSystem[standard]", kSteamSystemOffset, 0);
    LogField(env, "pFlashUI[standard-hypothesis]", kSteamFlashUiHypothesisOffset, kFlashUiGetElementSlot);

    LogField(env, "pScriptSystem[xbox-offset]", kXboxScriptSystemOffset, 6);
    LogField(env, "pInput[xbox-offset]", kXboxInputOffset, kInputPostInputEventSlot);
    LogField(env, "pGame[xbox-offset]", kXboxGameOffset, kGameGetFrameworkSlot);
    LogField(env, "pSystem[xbox-offset]", kXboxSystemOffset, 0);
    LogField(env, "pFlashUI[xbox-offset]", kXboxFlashUiOffset, kFlashUiGetElementSlot);

    LogThreadIdCandidates(env);

    void* game{};
    void* system{};
    if (!ReadPointer(env, kSteamGameOffset, game) || !game) {
        Log("standard pGame is unavailable; identity calls skipped");
        return;
    }
    ReadPointer(env, kSteamSystemOffset, system);

    const char* longName{};
    const char* shortName{};
    char longNameCopy[128]{};
    char shortNameCopy[128]{};
    void* getLongName = ExecutableSlot(game, kGameGetLongNameSlot);
    void* getName = ExecutableSlot(game, kGameGetNameSlot);
    const bool longCall = SafeCallString(getLongName, game, longName);
    const bool shortCall = SafeCallString(getName, game, shortName);
    const bool longCopy = longCall && CopyAscii(longName, longNameCopy, sizeof(longNameCopy));
    const bool shortCopy = shortCall && CopyAscii(shortName, shortNameCopy, sizeof(shortNameCopy));
    Log("IGame identity: GetLongName call=%s value=%s; GetName call=%s value=%s",
        longCall ? "ok" : "failed",
        longCopy ? longNameCopy : "<unreadable>",
        shortCall ? "ok" : "failed",
        shortCopy ? shortNameCopy : "<unreadable>");

    void* framework{};
    void* getFramework = ExecutableSlot(game, kGameGetFrameworkSlot);
    if (!SafeCallPointer(getFramework, game, framework) || !framework) {
        Log("IGame::GetIGameFramework slot %zu call failed", kGameGetFrameworkSlot);
        return;
    }
    Log("IGame::GetIGameFramework -> %p", framework);
    LogSlot("IGameFramework::PauseGame candidate", framework, kGameFrameworkPauseGameSlot);
    LogSlot("IGameFramework::GetISystem candidate", framework, kGameFrameworkGetSystemSlot);

    void* frameworkSystem{};
    void* getSystem = ExecutableSlot(framework, kGameFrameworkGetSystemSlot);
    const bool systemCall = SafeCallPointer(getSystem, framework, frameworkSystem);
    Log("IGameFramework identity: GetISystem call=%s returned=%p env.pSystem=%p match=%s",
        systemCall ? "ok" : "failed",
        frameworkSystem,
        system,
        systemCall && frameworkSystem == system ? "true" : "false");
}

DWORD WINAPI ProbeThread(void*)
{
    Log("Steam runtime probe started; KCD2 Clean Pause v%s build=%s; no hooks will be installed",
        CLEAN_PAUSE_VERSION,
        CLEAN_PAUSE_BUILD_ID);

    HMODULE whGame{};
    const ULONGLONG deadline = GetTickCount64() + kWaitForWhGameMs;
    while (!whGame && GetTickCount64() < deadline) {
        whGame = GetModuleHandleW(L"WHGame.dll");
        if (!whGame)
            Sleep(kPollMs);
    }
    if (!whGame) {
        Log("WHGame.dll was not loaded within %lu ms; probe stopped",
            static_cast<unsigned long>(kWaitForWhGameMs));
        return 0;
    }

    ImageView image{};
    if (!GetImageView(whGame, image)) {
        Log("WHGame PE image could not be validated; probe stopped");
        return 0;
    }

    const auto timestamp = image.nt->FileHeader.TimeDateStamp;
    const auto imageSize = image.nt->OptionalHeader.SizeOfImage;
    const auto checksum = image.nt->OptionalHeader.CheckSum;
    Log("WHGame fingerprint: TimeDateStamp=0x%08lx SizeOfImage=0x%08lx CheckSum=0x%08lx",
        static_cast<unsigned long>(timestamp),
        static_cast<unsigned long>(imageSize),
        static_cast<unsigned long>(checksum));
    Log("fingerprint matches reported Steam 1.5.6 sample: %s",
        timestamp == kReportedSteamTimestamp
            && imageSize == kReportedSteamImageSize
            && checksum == kReportedSteamChecksum
            ? "true" : "false");

    auto* anchor = FindAscii(image, "exec autoexec.cfg");
    if (!anchor) {
        Log("anchor string 'exec autoexec.cfg' not found; probe stopped without hooks");
        return 0;
    }
    Log("anchor string rva=0x%llx", static_cast<unsigned long long>(anchor - image.base));

    const auto xrefs = FindLeaXrefs(image, anchor);
    Log("anchor LEA xref count=%zu", xrefs.size());
    if (xrefs.empty()) {
        Log("no RIP-relative LEA xref to anchor found; probe stopped without hooks");
        return 0;
    }

    std::uint8_t* consoleFieldStorage{};
    if (!ResolveConsoleFieldStorage(image, xrefs, consoleFieldStorage)) {
        Log("could not derive pConsole field storage from known KCD2 contexts; probe stopped without hooks");
        return 0;
    }

    auto* env = consoleFieldStorage - kSteamConsoleOffset;
    Log("standard-layout gEnv candidate = %p (WHGame+0x%llx)",
        env,
        static_cast<unsigned long long>(env - image.base));

    const ULONGLONG gameDeadline = GetTickCount64() + kWaitForGameMs;
    void* game{};
    while (GetTickCount64() < gameDeadline) {
        if (ReadPointer(env, kSteamGameOffset, game) && game)
            break;
        Sleep(kPollMs);
    }
    Log("standard-layout pGame became available: %s", game ? "true" : "false");

    ProbeStandardProfile(env);
    Log("Steam runtime probe complete; no hooks were installed. Send kcd2_clean_pause_steam_probe.log.");
    return 0;
}

} // namespace

void Start(HMODULE selfModule)
{
    g_selfModule = selfModule;
    HANDLE thread = CreateThread(nullptr, 0, &ProbeThread, nullptr, 0, nullptr);
    if (thread)
        CloseHandle(thread);
}

} // namespace clean_pause::steam_probe
