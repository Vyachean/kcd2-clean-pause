#include "kcd2_abi_profile.h"
#include "kcd2_abi.h"

#include <cstddef>
#include <cstdint>

namespace kcd2::runtime {
namespace {

constexpr AbiProfile kRelease15Abi{
    AbiProfileId::Release15,
    "KCD2 release_1_5 / 1.5.6 ABI",
    {
        0x30,  // pScriptSystem
        0x48,  // pInput
        0x98,  // pGame
        0xB0,  // pConsole
        0xC8,  // pSystem
        0x140, // pFlashUI
        0x1B0, // mMainThreadId
        0x1C0, // sizeof(SSystemGlobalEnvironment)
    },
    {
        13, // IInput::PostInputEvent
        12, // IGame::GetLongName
        13, // IGame::GetName
        13, // IGameFramework::PauseGame
        19, // IGameFramework::GetISystem
        6,  // IScriptSystem::ExecuteBuffer
        32, // IScriptSystem::GetGlobalAny
        18, // IFlashUI::GetUIElementByInstanceStr
        23, // IUIElement::Update
        24, // IUIElement::Render
        28, // IUIElement::SetVisible
        29, // IUIElement::IsVisible
        69, // IUIElement::CallFunction(name)
        71, // IUIElement::GetMovieClip(name)
        26, // IFlashVariableObject::GetDisplayInfo
        33, // IFlashVariableObject::SetVisible
    },
    {
        InputEventLayoutId::Release15,
        0x30,
        0x04,
        0x08,
        0x10,
        0x18,
        0,
        516,
        526,
        527,
    },
    {
        PresentationLayoutId::Release15,
        0x38, // SFlashDisplayInfo binary size used by Clean Pause
        0x28, // SFlashDisplayInfo::visible byte
        28,   // C_UIHudMask child count
        0x1D0,// CFlashUIElement listener vector

        0x10, // C_UIHudBubbles IUIElementEventListener subobject
        0x58, // C_UIHudBubbles I_UIHudBubbles subobject
        1,    // bubble Update
        3,    // bubble Release
        4,    // bubble SetText
        5,    // bubble SetAnchor

        0x10, // C_UIHudMask listener subobject
        0x58, // C_UIHudMask visibility interface
        0x60, // C_UIHudMask source-monitor subobject
        3,    // C_UIHudMask OnModuleMessage
        1,    // I_UIHudMask IsElementVisible
        0,    // source monitor event
        0x08, // C_ModuleMessage id
        52,   // HUD refresh module message
    },
};

} // namespace

const AbiProfile& Release15AbiProfile()
{
    return kRelease15Abi;
}

bool MatureRuntimeSupports(const AbiProfile& profile)
{
    if (profile.id != AbiProfileId::Release15)
        return false;
    if (profile.input.id != InputEventLayoutId::Release15
        || profile.presentation.id != PresentationLayoutId::Release15)
        return false;

    const auto& env = profile.environment;
    if (env.scriptSystemOffset != kEnvScriptSystemOffset
        || env.inputOffset != kEnvInputOffset
        || env.gameOffset != kEnvGameOffset
        || env.consoleOffset != kEnvConsoleOffset
        || env.systemOffset != kEnvSystemOffset
        || env.flashUIOffset != kEnvFlashUIOffset
        || env.mainThreadIdOffset != kEnvMainThreadIdOffset
        || env.size != kEnvSize)
        return false;

    const auto& slots = profile.vtables;
    if (slots.inputPostInputEvent != kInputPostInputEventSlot
        || slots.gameGetLongName != kGameGetLongNameSlot
        || slots.gameGetName != kGameGetNameSlot
        || slots.gameFrameworkPauseGame != kGameFrameworkPauseGameSlot
        || slots.gameFrameworkGetSystem != kGameFrameworkGetSystemSlot
        || slots.scriptExecuteBuffer != kScriptExecuteBufferSlot
        || slots.scriptGetGlobalAny != kScriptGetGlobalAnySlot
        || slots.flashUIGetElementByInstanceStr != kFlashUIGetElementByInstanceStrSlot
        || slots.uiElementUpdate != kUIElementUpdateSlot
        || slots.uiElementRender != 24
        || slots.uiElementSetVisible != kUIElementSetVisibleSlot
        || slots.uiElementIsVisible != kUIElementIsVisibleSlot
        || slots.uiElementCallFunctionByName != 69
        || slots.uiElementGetMovieClipByName != kUIElementGetMovieClipByNameSlot
        || slots.flashVariableGetDisplayInfo != kFlashVariableGetDisplayInfoSlot
        || slots.flashVariableSetVisible != kFlashVariableSetVisibleSlot)
        return false;

    const auto& input = profile.input;
    if (input.size != sizeof(InputEvent)
        || input.stateOffset != offsetof(InputEvent, state)
        || input.keyNameOffset != offsetof(InputEvent, keyName)
        || input.keyIdOffset != offsetof(InputEvent, keyId)
        || input.valueOffset != offsetof(InputEvent, value)
        || input.escapeKey != static_cast<std::uint32_t>(KeyId::Escape)
        || input.xiStartKey != static_cast<std::uint32_t>(KeyId::XiStart)
        || input.xiAKey != static_cast<std::uint32_t>(KeyId::XiA)
        || input.xiBKey != static_cast<std::uint32_t>(KeyId::XiB))
        return false;

    // These values are consumed by the mature HUD/bubble implementation as class
    // layout facts. Keeping them in the ABI profile means a future build with a
    // different presentation ABI will fail here until a matching adapter is added,
    // rather than silently reusing release_1_5 offsets.
    const auto& presentation = profile.presentation;
    return presentation.flashDisplayInfoSize == 0x38
        && presentation.flashDisplayInfoVisibleOffset == 0x28
        && presentation.hudElementCount == 28
        && presentation.hudListenersOffset == 0x1D0
        && presentation.bubbleListenerOffset == 0x10
        && presentation.bubbleInterfaceOffset == 0x58
        && presentation.bubbleUpdateSlot == 1
        && presentation.bubbleReleaseSlot == 3
        && presentation.bubbleSetTextSlot == 4
        && presentation.bubbleSetAnchorSlot == 5
        && presentation.maskListenerOffset == 0x10
        && presentation.maskVisibilityInterfaceOffset == 0x58
        && presentation.maskSourceMonitorOffset == 0x60
        && presentation.maskOnModuleMessageSlot == 3
        && presentation.maskIsElementVisibleSlot == 1
        && presentation.sourceEventSlot == 0
        && presentation.moduleMessageIdOffset == 0x08
        && presentation.hudRefreshModuleMessageId == 52;
}

} // namespace kcd2::runtime
