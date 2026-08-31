#pragma once

#include "kcd2_abi_profile.h"

#include <windows.h>

#include <cstddef>
#include <cstdint>

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
};

enum class EnvironmentLocatorStrategy {
    CanonicalPConsoleCodeAnchor,
    LegacyXbox156ValidatedScan,
};

enum class BuildValidationLevel {
    RuntimeTested,
    StaticReverseEngineering,
};

struct StorefrontDescriptor {
    Storefront id{};
    const char* name{};
    const AbiProfile* release15Abi{};
    bool publicRelease15AddressLibrary{};
};

struct BuildProfile {
    Storefront storefront{};
    const char* name{};
    Fingerprint fingerprint{};
    EnvironmentLocatorStrategy environmentLocator{};
    const AbiProfile* abi{};
    BuildValidationLevel validation{};
};

bool ReadFingerprint(HMODULE whGame, Fingerprint& out);
const BuildProfile* MatchSupportedBuild(const Fingerprint& fingerprint);

const StorefrontDescriptor* KnownStorefronts(std::size_t& count);
const StorefrontDescriptor* FindStorefront(Storefront storefront);
const char* StorefrontName(Storefront storefront);
const char* EnvironmentLocatorName(EnvironmentLocatorStrategy strategy);
const char* BuildValidationName(BuildValidationLevel validation);

bool ResolveCanonicalEnvironmentBase(
    HMODULE whGame,
    const BuildProfile& profile,
    std::uint8_t*& environmentBase);

} // namespace kcd2::runtime
