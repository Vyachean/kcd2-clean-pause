#pragma once

#include "kcd2_abi_profile.h"

#include <windows.h>

#include <cstddef>
#include <cstdint>
#include <string>

namespace kcd2::runtime {

struct Fingerprint {
    std::uint32_t timestamp{};
    std::uint32_t imageSize{};
    std::uint32_t checksum{};
};

enum class Storefront {
    Steam,
    EpicGamesStore,
    GOG,
    XboxMicrosoftStore,
    Unknown,
};

enum class BuildIdentityStrategy {
    ExactPeFingerprint,
    StorefrontBuildCode,
    CompatibleReleaseBranch,
};

enum class EnvironmentLocatorStrategy {
    ExactEnvironmentRva,
    ExactEnvironmentRvaWithAnchorValidation,
    AnchorDerivedEnvironment,
};

enum class FrameworkLocatorStrategy {
    None,
    ExactPointerStorageRva,
    ExactObjectRva,
};

enum class BuildValidationLevel {
    RuntimeTested,
    StaticReverseEngineering,
    ExternalRuntimeEvidence,
    CompatibilityFallback,
};

struct RuntimeCapabilities {
    // Some builds expose the optional PauseGame observer safely only after a real
    // Pause input, when the engine lifecycle is fully mature.
    bool deferPauseBarrierUntilPauseInput{};

    // Presentation quirks are evidence-driven build capabilities, not storefront
    // identity checks inside the shared Clean Pause state machine.
    bool pinHudRootDuringPause{};
    bool prehideMenuDuringPauseTransition{};
};

struct StorefrontDescriptor {
    Storefront id{};
    const char* name{};
    const AbiProfile* release15Abi{};
    bool publicRelease15AddressLibrary{};
};

struct DetectedBuildIdentity {
    Fingerprint fingerprint{};
    Storefront storefront{Storefront::Unknown};
    std::string buildCode{};
};

struct BuildProfile {
    Storefront storefront{};
    const char* name{};
    BuildIdentityStrategy identityStrategy{};
    Fingerprint exactFingerprint{};
    const char* buildCode{};
    std::uint32_t requiredTimestamp{};

    std::uint32_t expectedEnvironmentRva{};
    EnvironmentLocatorStrategy environmentLocator{};

    FrameworkLocatorStrategy frameworkLocator{};
    std::uint32_t expectedFrameworkRva{};
    std::uint32_t expectedFrameworkVtableRva{};

    RuntimeCapabilities capabilities{};
    const AbiProfile* abi{};
    BuildValidationLevel validation{};
};

bool ReadFingerprint(HMODULE whGame, Fingerprint& out);
bool DetectStorefront(HMODULE whGame, Storefront& out);
bool ParseWarhorseBuildCode(const std::string& json, std::string& out);
bool ReadBuildCodeFromModulePath(const std::wstring& modulePath, std::string& out);
bool ReadBuildCode(HMODULE whGame, std::string& out);
bool ReadBuildIdentity(HMODULE whGame, DetectedBuildIdentity& out);
const BuildProfile* MatchSupportedBuild(const DetectedBuildIdentity& identity);

// Build a best-effort profile only for an otherwise-unmatched release_1_5 build.
// The fallback deliberately has no version-specific framework root or presentation
// quirks. It derives gEnv from a unique code anchor and is still subject to the
// mature runtime's full live interface/main-thread/game-name validation before any
// hook is installed. Unknown release branches remain unsupported.
bool BuildCompatibleRelease15Fallback(
    const DetectedBuildIdentity& identity,
    BuildProfile& out);

const StorefrontDescriptor* KnownStorefronts(std::size_t& count);
const StorefrontDescriptor* FindStorefront(Storefront storefront);
const char* StorefrontName(Storefront storefront);
const char* BuildIdentityStrategyName(BuildIdentityStrategy strategy);
const char* EnvironmentLocatorName(EnvironmentLocatorStrategy strategy);
const char* FrameworkLocatorName(FrameworkLocatorStrategy strategy);
const char* BuildValidationName(BuildValidationLevel validation);

// Resolves immutable build-level environment identity once. Exact profiles use
// their registered RVA; the conservative release_1_5 fallback derives gEnv from a
// unique executable reference to the canonical pConsole storage instead of broad
// writable-memory scanning. The caller may then poll object readiness at the
// returned address without rescanning WHGame.dll.
bool ResolveProfileEnvironmentBase(
    HMODULE whGame,
    const BuildProfile& profile,
    std::uint8_t*& environmentBase);

} // namespace kcd2::runtime
