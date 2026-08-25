#pragma once

#include <cstddef>
#include <cstdint>

namespace kcd2 {

// Minimal KCD2 1.5.6 ABI used by the stable native implementation. Clean Pause
// lets KCD2 own the real pause and changes presentation only through verified
// Input/FlashUI interfaces.

enum class DeviceId : std::int32_t {
    Keyboard = 0,
    Mouse = 1,
    XInput = 2,
    Unknown = 0xff,
};

enum InputState : std::int32_t {
    Pressed = 1 << 0,
    Released = 1 << 1,
    Down = 1 << 2,
    Changed = 1 << 3,
    UI = 1 << 4,
};

enum class KeyId : std::uint32_t {
    Escape = 0,

    // Retail Xbox Store KCD2 1.5.6 evidence. The XInput range is not treated as
    // contiguous; only directly observed IDs are named here.
    XiStart = 516,
    XiA = 526,
    XiB = 527,

    None = 0xffffffffu,
};

struct InputEvent {
    DeviceId deviceId;        // +0x00
    std::int32_t state;       // +0x04
    const char* keyName;      // +0x08
    KeyId keyId;              // +0x10
    std::int32_t modifiers;   // +0x14
    float value;              // +0x18
    std::int32_t pad1C;       // +0x1C
    void* symbol;             // +0x20
    std::uint8_t deviceIndex; // +0x28
    std::uint8_t pad29[7];
};

static_assert(offsetof(InputEvent, keyName) == 0x08);
static_assert(offsetof(InputEvent, keyId) == 0x10);
static_assert(offsetof(InputEvent, value) == 0x18);
static_assert(static_cast<std::uint32_t>(KeyId::XiStart) == 516);
static_assert(static_cast<std::uint32_t>(KeyId::XiA) == 526);
static_assert(static_cast<std::uint32_t>(KeyId::XiB) == 527);

// SSystemGlobalEnvironment offsets verified for KCD2 1.5.6.
inline constexpr std::size_t kEnvScriptSystemOffset = 0x30;
inline constexpr std::size_t kEnvInputOffset = 0x48;
inline constexpr std::size_t kEnvGameOffset = 0x98;      // IGame*, not IGameFramework*
inline constexpr std::size_t kEnvSystemOffset = 0xC8;
inline constexpr std::size_t kEnvFlashUIOffset = 0x140;
inline constexpr std::size_t kEnvMainThreadIdOffset = 0x1B0;
inline constexpr std::size_t kEnvSize = 0x1C0;

// Verified vtable slots used by the stable build.
inline constexpr std::size_t kInputPostInputEventSlot = 13;
inline constexpr std::size_t kGameGetLongNameSlot = 12;
inline constexpr std::size_t kGameGetNameSlot = 13;
inline constexpr std::size_t kScriptExecuteBufferSlot = 6;
inline constexpr std::size_t kScriptGetGlobalAnySlot = 32;
inline constexpr std::size_t kFlashUIGetElementByInstanceStrSlot = 18;
inline constexpr std::size_t kUIElementUpdateSlot = 23;
inline constexpr std::size_t kUIElementSetVisibleSlot = 28;
inline constexpr std::size_t kUIElementIsVisibleSlot = 29;
inline constexpr std::size_t kUIElementGetMovieClipByNameSlot = 71;
inline constexpr std::size_t kFlashVariableGetDisplayInfoSlot = 26;
inline constexpr std::size_t kFlashVariableSetVisibleSlot = 33;

using PostInputEventFn = void(__fastcall*)(void*, const InputEvent*, bool);
using ExecuteBufferFn = bool(__fastcall*)(void*, const char*, std::size_t, const char*, void*);
using GetUIElementByInstanceStrFn = void*(__fastcall*)(void*, const char*);
using UIElementUpdateFn = void(__fastcall*)(void*, float);
using SetVisibleFn = void(__fastcall*)(void*, bool);
using IsVisibleFn = bool(__fastcall*)(void*);
using GetMovieClipByNameFn = void*(__fastcall*)(void*, const char*, const char*);
using FlashVariableGetDisplayInfoFn = bool(__fastcall*)(void*, void*);
using FlashVariableSetVisibleFn = bool(__fastcall*)(void*, bool);

template <class Fn>
Fn VFunc(void* object, std::size_t slot)
{
    return reinterpret_cast<Fn>((*reinterpret_cast<void***>(object))[slot]);
}

} // namespace kcd2
