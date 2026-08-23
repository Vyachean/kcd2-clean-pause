#pragma once

#include <cstddef>
#include <cstdint>

namespace kcd2 {

// Minimal ABI copied from verified KCD2 1.5.6 reverse-engineering facts.
// Keep this deliberately small: the native prototype only needs raw input and
// the existing Lua runtime. No ActionMapManager ABI is used here.

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

// KCD2 1.5.6 ScriptAnyValue layout. We only read booleans from Lua.
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
inline constexpr std::size_t kEnvScriptSystemOffset = 0x30;
inline constexpr std::size_t kEnvInputOffset = 0x48;
inline constexpr std::size_t kEnvGameOffset = 0x98;
inline constexpr std::size_t kEnvSystemOffset = 0xC8;
inline constexpr std::size_t kEnvMainThreadIdOffset = 0x1B0;
inline constexpr std::size_t kEnvSize = 0x1C0;

// KCD2 1.5.6 vtable slots used by the prototype.
inline constexpr std::size_t kInputPostInputEventSlot = 13;
inline constexpr std::size_t kScriptExecuteBufferSlot = 6;
inline constexpr std::size_t kScriptReleaseAnySlot = 29;
inline constexpr std::size_t kScriptGetGlobalAnySlot = 32;
inline constexpr std::size_t kScriptSetGlobalToNullSlot = 33;

using PostInputEventFn = void(__fastcall*)(void*, const InputEvent*, bool);
using ExecuteBufferFn = bool(__fastcall*)(void*, const char*, std::size_t, const char*, void*);
using ReleaseAnyFn = void(__fastcall*)(void*, const ScriptAnyValue*);
using GetGlobalAnyFn = bool(__fastcall*)(void*, const char*, ScriptAnyValue*);
using SetGlobalToNullFn = void(__fastcall*)(void*, const char*);

template <class Fn>
Fn VFunc(void* object, std::size_t slot)
{
    return reinterpret_cast<Fn>((*reinterpret_cast<void***>(object))[slot]);
}

} // namespace kcd2
