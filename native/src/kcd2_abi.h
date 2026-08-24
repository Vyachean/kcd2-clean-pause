#pragma once

#include <cstddef>
#include <cstdint>

namespace kcd2 {

// Minimal KCD2 1.5.6 ABI used by the native proxy. The runtime deliberately
// avoids inferred IGameFramework::PauseGame signatures: Clean Pause lets KCD2
// open its own vanilla pause, then hides only the Menu Flash element.

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

    XiDPadUp = 512,
    XiDPadDown,
    XiDPadLeft,
    XiDPadRight,
    XiStart,
    XiBack,
    XiThumbL,
    XiThumbR,
    XiShoulderL,
    XiShoulderR,
    XiA,
    XiB,
    XiX,
    XiY,

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

// KCD2 1.5.6 ScriptAnyValue layout. Only booleans are read.
enum class ScriptAnyType : std::int32_t {
    Any = 0,
    Nil,
    Boolean,
    Handle,
    Number,
    String,
    Table,
    Function,
    UserData,
    Vector,
};

struct ScriptAnyValue {
    ScriptAnyType type{ScriptAnyType::Any};
    std::uint32_t pad04{};
    union {
        bool boolean;
        std::int64_t handle;
        float number;
        const char* string;
        void* pointer;
        struct {
            float x;
            float y;
            float z;
        } vec3;
    } value{};
};

static_assert(sizeof(ScriptAnyValue) == 0x18);

// SSystemGlobalEnvironment offsets verified for KCD2 1.5.6.
// +0x98 is IGame*, not IGameFramework*.
// +0x140 is IFlashUI*.
inline constexpr std::size_t kEnvScriptSystemOffset = 0x30;
inline constexpr std::size_t kEnvInputOffset = 0x48;
inline constexpr std::size_t kEnvGameOffset = 0x98;
inline constexpr std::size_t kEnvSystemOffset = 0xC8;
inline constexpr std::size_t kEnvFlashUIOffset = 0x140;
inline constexpr std::size_t kEnvMainThreadIdOffset = 0x1B0;
inline constexpr std::size_t kEnvSize = 0x1C0;

// Verified KCD2 1.5.6 vtable slots used by this build.
inline constexpr std::size_t kInputPostInputEventSlot = 13;
inline constexpr std::size_t kGameGetLongNameSlot = 12;
inline constexpr std::size_t kGameGetNameSlot = 13;

inline constexpr std::size_t kScriptExecuteBufferSlot = 6;
inline constexpr std::size_t kScriptReleaseAnySlot = 29;
inline constexpr std::size_t kScriptGetGlobalAnySlot = 32;
inline constexpr std::size_t kScriptSetGlobalToNullSlot = 33;

inline constexpr std::size_t kFlashUIGetElementByInstanceStrSlot = 18;
inline constexpr std::size_t kUIElementSetVisibleSlot = 28;
inline constexpr std::size_t kUIElementIsVisibleSlot = 29;

using PostInputEventFn = void(__fastcall*)(void*, const InputEvent*, bool);
using ExecuteBufferFn = bool(__fastcall*)(void*, const char*, std::size_t, const char*, void*);
using ReleaseAnyFn = void(__fastcall*)(void*, const ScriptAnyValue*);
using GetGlobalAnyFn = bool(__fastcall*)(void*, const char*, ScriptAnyValue*);
using SetGlobalToNullFn = void(__fastcall*)(void*, const char*);

using GetUIElementByInstanceStrFn = void*(__fastcall*)(void*, const char*);
using SetVisibleFn = void(__fastcall*)(void*, bool);
using IsVisibleFn = bool(__fastcall*)(void*);

template <class Fn>
Fn VFunc(void* object, std::size_t slot)
{
    return reinterpret_cast<Fn>((*reinterpret_cast<void***>(object))[slot]);
}

} // namespace kcd2
