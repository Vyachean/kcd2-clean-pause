#include "clean_pause_native.h"
#include "kcd2_abi.h"

#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <string>

namespace clean_pause {
namespace {

using namespace kcd2;

std::atomic_bool g_stopping{false};
HMODULE g_selfModule{};
void* g_flashUI{};
void* g_gameContext{};
void* g_guiModule{};
SRWLOCK g_logLock = SRWLOCK_INIT;

constexpr DWORD kWaitForWhGameMs = 60'000;
constexpr DWORD kWaitForRuntimeMs = 120'000;
constexpr DWORD kPollMs = 100;

constexpr std::size_t kGameContextSize = 0x1F0;
constexpr std::size_t kGameContextGuiModuleOffset = 0xE8;
constexpr std::size_t kGuiModuleSize = 0x120;
constexpr std::size_t kGuiUiElementsOffset = 0x40;
constexpr std::size_t kUiFlashElementOffset = 0x48;
constexpr std::size_t kUiMenuInterfaceOffset = 0x58;
constexpr std::size_t kUiMenuStateOffset = 0xA0;
constexpr std::size_t kSharedPtrStride = 0x10;

constexpr std::size_t kGuiGetModuleIdSlot = 5;
constexpr std::size_t kGuiGetModuleNameSlot = 6;
constexpr std::size_t kUiMenuGetStateSlot = 9;
constexpr int kGuiModuleId = 16;
constexpr std::uint8_t kMenuStateMax = 5;

using GetModuleIdFn = int(__fastcall*)(void*);
using GetModuleNameFn = const char*(__fastcall*)(void*);
using GetMenuStateFn = std::uint8_t(__fastcall*)(void*);

const char* BoolText(bool value)
{
    return value ? "true" : "false";
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

std::wstring LogPath()
{
    wchar_t path[MAX_PATH]{};
    const DWORD length = GetModuleFileNameW(g_selfModule, path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH)
        return L"kcd2_clean_pause_native.log";

    std::wstring result(path, length);
    const auto slash = result.find_last_of(L"\\/");
    if (slash != std::wstring::npos)
        result.resize(slash + 1);
    else
        result.clear();

    result += L"kcd2_clean_pause_native.log";
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

bool ValidateObjectVtable(void* object, std::initializer_list<std::size_t> requiredSlots)
{
    if (!IsReadable(object, sizeof(void*)))
        return false;

    void** vtable{};
    __try {
        vtable = *reinterpret_cast<void***>(object);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    std::size_t maxSlot{};
    for (const auto slot : requiredSlots)
        if (slot > maxSlot)
            maxSlot = slot;

    if (!IsReadable(vtable, (maxSlot + 1) * sizeof(void*)))
        return false;

    __try {
        for (const auto slot : requiredSlots)
            if (!IsExecutable(vtable[slot]))
                return false;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
}

struct RuntimeEnvironment {
    void* flashUI{};
};

bool ValidateEnvironmentCandidate(const std::uint8_t* candidate, RuntimeEnvironment& out)
{
    if (!IsReadable(candidate, kEnvSize))
        return false;

    void* scriptSystem{};
    void* input{};
    void* game{};
    void* system{};
    void* flashUI{};
    DWORD mainThreadId{};
    __try {
        scriptSystem = *reinterpret_cast<void* const*>(candidate + kEnvScriptSystemOffset);
        input = *reinterpret_cast<void* const*>(candidate + kEnvInputOffset);
        game = *reinterpret_cast<void* const*>(candidate + kEnvGameOffset);
        system = *reinterpret_cast<void* const*>(candidate + kEnvSystemOffset);
        flashUI = *reinterpret_cast<void* const*>(candidate + kEnvFlashUIOffset);
        mainThreadId = *reinterpret_cast<const DWORD*>(candidate + kEnvMainThreadIdOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (!scriptSystem || !input || !game || !system || !flashUI || mainThreadId == 0)
        return false;
    if (!ValidateObjectVtable(scriptSystem, {kScriptExecuteBufferSlot, kScriptGetGlobalAnySlot}))
        return false;
    if (!ValidateObjectVtable(input, {kInputPostInputEventSlot}))
        return false;
    if (!ValidateObjectVtable(game, {kGameGetLongNameSlot, kGameGetNameSlot}))
        return false;
    if (!ValidateObjectVtable(system, {0}))
        return false;
    if (!ValidateObjectVtable(flashUI, {kFlashUIGetElementByInstanceStrSlot}))
        return false;

    HANDLE thread = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, mainThreadId);
    if (!thread)
        return false;
    CloseHandle(thread);

    out.flashUI = flashUI;
    return true;
}

bool ReadPeSections(HMODULE whGame, const IMAGE_NT_HEADERS64*& nt, const std::uint8_t*& base)
{
    base = reinterpret_cast<const std::uint8_t*>(whGame);
    if (!IsReadable(base, sizeof(IMAGE_DOS_HEADER)))
        return false;

    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE)
        return false;

    nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    return IsReadable(nt, sizeof(*nt)) && nt->Signature == IMAGE_NT_SIGNATURE;
}

bool FindRuntimeEnvironment(HMODULE whGame, RuntimeEnvironment& result)
{
    const IMAGE_NT_HEADERS64* nt{};
    const std::uint8_t* base{};
    if (!ReadPeSections(whGame, nt, base))
        return false;

    const auto* section = IMAGE_FIRST_SECTION(nt);
    for (unsigned index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        const DWORD flags = section->Characteristics;
        if (!(flags & IMAGE_SCN_MEM_READ) || !(flags & IMAGE_SCN_MEM_WRITE))
            continue;

        const auto* start = base + section->VirtualAddress;
        const std::size_t size = section->Misc.VirtualSize;
        if (size < kEnvSize)
            continue;

        const std::size_t limit = size - kEnvSize;
        for (std::size_t offset = 0; offset <= limit; offset += alignof(void*)) {
            RuntimeEnvironment candidate{};
            if (ValidateEnvironmentCandidate(start + offset, candidate)) {
                result = candidate;
                return true;
            }
        }
    }
    return false;
}

struct RawVector {
    std::uint8_t* begin{};
    std::uint8_t* end{};
    std::uint8_t* capacity{};
};

bool ReadUiElementsVector(void* guiModule, RawVector& value)
{
    if (!IsReadable(guiModule, kGuiModuleSize))
        return false;

    __try {
        value = *reinterpret_cast<const RawVector*>(
            reinterpret_cast<const std::uint8_t*>(guiModule) + kGuiUiElementsOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (!value.begin || !value.end || !value.capacity)
        return false;
    if (value.end < value.begin || value.capacity < value.end)
        return false;

    const auto bytes = static_cast<std::size_t>(value.end - value.begin);
    if (bytes % kSharedPtrStride != 0)
        return false;
    const auto count = bytes / kSharedPtrStride;
    if (count == 0 || count > 256)
        return false;
    return IsReadable(value.begin, bytes);
}

bool ValidateGuiModule(void* guiModule)
{
    if (!ValidateObjectVtable(guiModule, {kGuiGetModuleIdSlot, kGuiGetModuleNameSlot}))
        return false;

    const auto getId = VFunc<GetModuleIdFn>(guiModule, kGuiGetModuleIdSlot);
    const auto getName = VFunc<GetModuleNameFn>(guiModule, kGuiGetModuleNameSlot);
    if (!getId || !getName)
        return false;

    int id{};
    const char* name{};
    __try {
        id = getId(guiModule);
        name = getName(guiModule);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (id != kGuiModuleId || !name || !IsReadable(name, 10))
        return false;

    bool nameOk{};
    __try {
        nameOk = std::strcmp(name, "GUIModule") == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        nameOk = false;
    }
    if (!nameOk)
        return false;

    RawVector elements{};
    return ReadUiElementsVector(guiModule, elements);
}

bool ValidateGameContext(void* candidate, void*& guiModule)
{
    if (!IsReadable(candidate, kGameContextSize))
        return false;

    void* gui{};
    __try {
        gui = *reinterpret_cast<void* const*>(
            reinterpret_cast<const std::uint8_t*>(candidate) + kGameContextGuiModuleOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (!gui || !ValidateGuiModule(gui))
        return false;
    guiModule = gui;
    return true;
}

bool FindGameContext(HMODULE whGame, void*& context, void*& guiModule)
{
    const IMAGE_NT_HEADERS64* nt{};
    const std::uint8_t* base{};
    if (!ReadPeSections(whGame, nt, base))
        return false;

    const auto* section = IMAGE_FIRST_SECTION(nt);
    for (unsigned index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        const DWORD flags = section->Characteristics;
        if (!(flags & IMAGE_SCN_MEM_READ) || !(flags & IMAGE_SCN_MEM_WRITE))
            continue;

        const auto* start = base + section->VirtualAddress;
        const std::size_t size = section->Misc.VirtualSize;
        if (size < sizeof(void*))
            continue;

        for (std::size_t offset = 0; offset + sizeof(void*) <= size; offset += alignof(void*)) {
            void* candidate{};
            __try {
                candidate = *reinterpret_cast<void* const*>(start + offset);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                continue;
            }

            void* gui{};
            if (candidate && ValidateGameContext(candidate, gui)) {
                context = candidate;
                guiModule = gui;
                return true;
            }
        }
    }
    return false;
}

struct FlashMenuState {
    bool resolved{};
    bool visibleOk{};
    bool visible{};
    void* element{};
};

FlashMenuState ReadFlashMenuState()
{
    FlashMenuState result{};
    if (!g_flashUI)
        return result;

    const auto getElement =
        VFunc<GetUIElementByInstanceStrFn>(g_flashUI, kFlashUIGetElementByInstanceStrSlot);
    if (!getElement)
        return result;

    __try {
        result.element = getElement(g_flashUI, "Menu@0");
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return result;
    }
    result.resolved = result.element != nullptr;
    if (!result.resolved || !ValidateObjectVtable(result.element, {kUIElementIsVisibleSlot}))
        return result;

    const auto isVisible = VFunc<IsVisibleFn>(result.element, kUIElementIsVisibleSlot);
    if (!isVisible)
        return result;

    __try {
        result.visible = isVisible(result.element);
        result.visibleOk = true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        result.visibleOk = false;
    }
    return result;
}

struct ControllerState {
    bool vectorOk{};
    bool resolved{};
    bool stateOk{};
    std::uint8_t state{};
    std::uint8_t memoryState{};
    void* object{};
    void* interfacePtr{};
};

ControllerState ReadControllerState(void* menuElement)
{
    ControllerState result{};
    if (!g_guiModule || !menuElement)
        return result;

    RawVector elements{};
    if (!ReadUiElementsVector(g_guiModule, elements))
        return result;
    result.vectorOk = true;

    const auto count = static_cast<std::size_t>(elements.end - elements.begin) / kSharedPtrStride;
    for (std::size_t index = 0; index < count; ++index) {
        const auto* entry = elements.begin + index * kSharedPtrStride;
        void* object{};
        void* boundElement{};
        std::uint8_t memoryState{};
        __try {
            object = *reinterpret_cast<void* const*>(entry);
            if (!object || !IsReadable(object, kUiMenuStateOffset + 1))
                continue;
            boundElement = *reinterpret_cast<void* const*>(
                reinterpret_cast<const std::uint8_t*>(object) + kUiFlashElementOffset);
            memoryState = *reinterpret_cast<const std::uint8_t*>(
                reinterpret_cast<const std::uint8_t*>(object) + kUiMenuStateOffset);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            continue;
        }

        if (boundElement != menuElement || memoryState > kMenuStateMax)
            continue;

        void* interfacePtr = reinterpret_cast<std::uint8_t*>(object) + kUiMenuInterfaceOffset;
        if (!ValidateObjectVtable(interfacePtr, {0, 1, 2, kUiMenuGetStateSlot, 16, 17, 18}))
            continue;

        const auto getState = VFunc<GetMenuStateFn>(interfacePtr, kUiMenuGetStateSlot);
        if (!getState)
            continue;

        std::uint8_t apiState{};
        bool callOk{};
        __try {
            apiState = getState(interfacePtr);
            callOk = true;
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            callOk = false;
        }
        if (!callOk || apiState != memoryState || apiState > kMenuStateMax)
            continue;

        result.resolved = true;
        result.stateOk = true;
        result.state = apiState;
        result.memoryState = memoryState;
        result.object = object;
        result.interfacePtr = interfacePtr;
        return result;
    }
    return result;
}

void LogSnapshot(const char* reason)
{
    const FlashMenuState flash = ReadFlashMenuState();
    const ControllerState controller = ReadControllerState(flash.element);
    Log(
        "menu-mode snapshot reason=%s flash_resolved=%s flash_visible_ok=%s flash_visible=%s menu=%p game_context=%p gui_module=%p vector_ok=%s controller_resolved=%s state_ok=%s menu_state=%u memory_state=%u controller=%p i_uimenu=%p",
        reason ? reason : "poll",
        BoolText(flash.resolved),
        BoolText(flash.visibleOk),
        BoolText(flash.visible),
        flash.element,
        g_gameContext,
        g_guiModule,
        BoolText(controller.vectorOk),
        BoolText(controller.resolved),
        BoolText(controller.stateOk),
        static_cast<unsigned>(controller.state),
        static_cast<unsigned>(controller.memoryState),
        controller.object,
        controller.interfacePtr);
}

DWORD WINAPI ProbeThread(void*)
{
    Log("native bootstrap started; target=KCD2 1.5.6 Windows retail; read-only C_UIMenu state probe");

    HMODULE whGame{};
    for (DWORD elapsed = 0; elapsed < kWaitForWhGameMs && !g_stopping.load(); elapsed += kPollMs) {
        whGame = GetModuleHandleW(L"WHGame.dll");
        if (whGame)
            break;
        Sleep(kPollMs);
    }
    if (!whGame) {
        Log("WHGame.dll not found; menu-mode probe disabled");
        return 0;
    }

    RuntimeEnvironment environment{};
    for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs && !g_stopping.load(); elapsed += kPollMs) {
        if (FindRuntimeEnvironment(whGame, environment))
            break;
        Sleep(kPollMs);
    }
    if (!environment.flashUI) {
        Log("SSystemGlobalEnvironment could not be validated; menu-mode probe disabled");
        return 0;
    }
    g_flashUI = environment.flashUI;

    for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs && !g_stopping.load(); elapsed += kPollMs) {
        if (FindGameContext(whGame, g_gameContext, g_guiModule))
            break;
        Sleep(kPollMs);
    }
    if (!g_gameContext || !g_guiModule) {
        Log("S_GameContext/GUIModule could not be structurally validated; no controller reads performed");
        return 0;
    }

    Log("menu-mode probe active; vanilla input/UI untouched; flashUI=%p game_context=%p gui_module=%p",
        g_flashUI, g_gameContext, g_guiModule);

    bool havePrevious{};
    bool previousFlashResolved{};
    bool previousVisibleOk{};
    bool previousVisible{};
    bool previousControllerResolved{};
    bool previousStateOk{};
    std::uint8_t previousState{};
    ULONGLONG lastPeriodic{};

    while (!g_stopping.load(std::memory_order_relaxed)) {
        const FlashMenuState flash = ReadFlashMenuState();
        const ControllerState controller = ReadControllerState(flash.element);
        const ULONGLONG now = GetTickCount64();

        const bool changed = !havePrevious
            || flash.resolved != previousFlashResolved
            || flash.visibleOk != previousVisibleOk
            || flash.visible != previousVisible
            || controller.resolved != previousControllerResolved
            || controller.stateOk != previousStateOk
            || controller.state != previousState;

        if (changed || now - lastPeriodic >= 5000) {
            Log(
                "menu-mode snapshot reason=%s flash_resolved=%s flash_visible_ok=%s flash_visible=%s menu=%p game_context=%p gui_module=%p vector_ok=%s controller_resolved=%s state_ok=%s menu_state=%u memory_state=%u controller=%p i_uimenu=%p",
                changed ? "change" : "periodic",
                BoolText(flash.resolved),
                BoolText(flash.visibleOk),
                BoolText(flash.visible),
                flash.element,
                g_gameContext,
                g_guiModule,
                BoolText(controller.vectorOk),
                BoolText(controller.resolved),
                BoolText(controller.stateOk),
                static_cast<unsigned>(controller.state),
                static_cast<unsigned>(controller.memoryState),
                controller.object,
                controller.interfacePtr);
            lastPeriodic = now;
        }

        havePrevious = true;
        previousFlashResolved = flash.resolved;
        previousVisibleOk = flash.visibleOk;
        previousVisible = flash.visible;
        previousControllerResolved = controller.resolved;
        previousStateOk = controller.stateOk;
        previousState = controller.state;
        Sleep(kPollMs);
    }
    return 0;
}

} // namespace

bool Start(HMODULE selfModule)
{
    g_selfModule = selfModule;
    g_stopping.store(false, std::memory_order_relaxed);

    HANDLE thread = CreateThread(nullptr, 0, ProbeThread, nullptr, 0, nullptr);
    if (!thread)
        return false;
    CloseHandle(thread);
    return true;
}

void Stop()
{
    g_stopping.store(true, std::memory_order_release);
}

} // namespace clean_pause
