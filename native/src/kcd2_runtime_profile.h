#pragma once

#include <windows.h>

#include <cstdint>

namespace kcd2::runtime {

struct Fingerprint {
    std::uint32_t timestamp{};
    std::uint32_t imageSize{};
    std::uint32_t checksum{};
};

enum class StorefrontProfile {
    XboxStore156,
    Steam15693,
};

struct BuildProfile {
    StorefrontProfile id;
    const char* name;
    Fingerprint fingerprint;
};

bool ReadFingerprint(HMODULE whGame, Fingerprint& out);
const BuildProfile* MatchSupportedBuild(const Fingerprint& fingerprint);
bool ResolveCanonicalEnvironmentBase(
    HMODULE whGame,
    const BuildProfile& profile,
    std::uint8_t*& environmentBase);

} // namespace kcd2::runtime
