#pragma once

#include <cstddef>
#include <cstdint>

namespace kcd2::runtime {

enum class AbiProfileId {
    Release15,
};

enum class InputEventLayoutId {
    Release15,
};

enum class PresentationLayoutId {
    Release15,
};

struct EnvironmentLayout {
    std::size_t scriptSystemOffset{};
    std::size_t inputOffset{};
    std::size_t gameOffset{};
    std::size_t consoleOffset{};
    std::size_t systemOffset{};
    std::size_t flashUIOffset{};
    std::size_t mainThreadIdOffset{};
    std::size_t size{};
};

struct VtableLayout {
    std::size_t inputPostInputEvent{};
    std::size_t gameGetLongName{};
    std::size_t gameGetName{};
    std::size_t gameGetFramework{};
    std::size_t gameFrameworkPauseGame{};
    std::size_t gameFrameworkGetSystem{};
    std::size_t scriptExecuteBuffer{};
    std::size_t scriptGetGlobalAny{};
    std::size_t flashUIGetElementByInstanceStr{};
    std::size_t uiElementUpdate{};
    std::size_t uiElementRender{};
    std::size_t uiElementSetVisible{};
    std::size_t uiElementIsVisible{};
    std::size_t uiElementCallFunctionByName{};
    std::size_t uiElementGetMovieClipByName{};
    std::size_t flashVariableGetDisplayInfo{};
    std::size_t flashVariableSetVisible{};
};

struct InputLayout {
    InputEventLayoutId id{};
    std::size_t size{};
    std::size_t stateOffset{};
    std::size_t keyNameOffset{};
    std::size_t keyIdOffset{};
    std::size_t valueOffset{};
    std::uint32_t escapeKey{};
    std::uint32_t xiStartKey{};
    std::uint32_t xiAKey{};
    std::uint32_t xiBKey{};
};

struct PresentationLayout {
    PresentationLayoutId id{};
    std::size_t flashDisplayInfoSize{};
    std::size_t flashDisplayInfoVisibleOffset{};
    std::size_t hudElementCount{};
    std::size_t hudListenersOffset{};

    std::size_t bubbleListenerOffset{};
    std::size_t bubbleInterfaceOffset{};
    std::size_t bubbleUpdateSlot{};
    std::size_t bubbleReleaseSlot{};
    std::size_t bubbleSetTextSlot{};
    std::size_t bubbleSetAnchorSlot{};

    std::size_t maskListenerOffset{};
    std::size_t maskVisibilityInterfaceOffset{};
    std::size_t maskSourceMonitorOffset{};
    std::size_t maskOnModuleMessageSlot{};
    std::size_t maskIsElementVisibleSlot{};
    std::size_t sourceEventSlot{};
    std::size_t moduleMessageIdOffset{};
    std::uint32_t hudRefreshModuleMessageId{};
};

struct AbiProfile {
    AbiProfileId id{};
    const char* name{};
    EnvironmentLayout environment{};
    VtableLayout vtables{};
    InputLayout input{};
    PresentationLayout presentation{};
};

const AbiProfile& Release15AbiProfile();

// The existing mature Clean Pause implementation has one concrete adapter today.
// Build/storefront registration is data-driven, but a build may install hooks only
// when its selected ABI is fully representable by that adapter. A future ABI can be
// described immediately without being treated as compatible by accident.
bool MatureRuntimeSupports(const AbiProfile& profile);

} // namespace kcd2::runtime
