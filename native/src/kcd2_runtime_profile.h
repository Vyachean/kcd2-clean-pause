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
};

enum class EnvironmentLocatorStrategy {
    CanonicalPConsoleCodeAnchor,
    LegacyXbox156ValidatedScan,
};

enum class BuildValidationLevel {
    RuntimeTested,
    StaticReverseEngineering,
    ExternalRuntimeEvidence,
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
    const AbiProfile* abi{};
    BuildValidationLevel validation{};
};

bool ReadFingerprint(HMODULE whGame, Fingerprint& out);
bool DetectStorefront(HMODULE whGame, Storefront& out);
bool ReadBuildCode(HMODULE whGame, std::string& out);
bool ReadBuildIdentity(HMODULE whGame, DetectedBuildIdentity& out);
const BuildProfile* MatchSupportedBuild(const DetectedBuildIdentity& identity);

const StorefrontDescriptor* KnownStorefronts(std::size_t& count);
const StorefrontDescriptor* FindStorefront(Storefront storefront);
const char* StorefrontName(Storefront storefront);
const char* BuildIdentityStrategyName(BuildIdentityStrategy strategy);
const char* EnvironmentLocatorName(EnvironmentLocatorStrategy strategy);
const char* BuildValidationName(BuildValidationLevel validation);

bool ResolveCanonicalEnvironmentBase(
    HMODULE whGame,
    const BuildProfile& profile,
    std::uint8_t*& environmentBase);

} // namespace kcd2::runtime
