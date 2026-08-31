#include "kcd2_runtime_profile.h"
#include "kcd2_abi.h"

#include <windows.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>

namespace {

#define CHECK(condition) \
    do { \
        if (!(condition)) { \
            std::fprintf(stderr, "CHECK failed at %s:%d: %s\n", __FILE__, __LINE__, #condition); \
            return false; \
        } \
    } while (false)

class SyntheticWhGame {
public:
    SyntheticWhGame()
    {
        base_ = static_cast<std::uint8_t*>(VirtualAlloc(
            nullptr, kAllocationSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
        if (!base_)
            return;
        std::memset(base_, 0, kAllocationSize);
        BuildHeaders();
        BuildAnchorPath();
    }

    ~SyntheticWhGame()
    {
        if (base_)
            VirtualFree(base_, 0, MEM_RELEASE);
    }

    SyntheticWhGame(const SyntheticWhGame&) = delete;
    SyntheticWhGame& operator=(const SyntheticWhGame&) = delete;

    bool valid() const { return base_ != nullptr; }
    HMODULE module() const { return reinterpret_cast<HMODULE>(base_); }
    std::uint8_t* environment() const { return environment_; }
    std::uint32_t environmentRva() const
    {
        return static_cast<std::uint32_t>(environment_ - base_);
    }

    void SetStorefrontMarker(const char* marker)
    {
        auto* destination = base_ + kRdataRva + 0x300;
        std::memset(destination, 0, 128);
        if (marker)
            std::memcpy(destination, marker, std::strlen(marker) + 1);
    }

    void AddAmbiguousConsoleReference()
    {
        const auto& abi = kcd2::runtime::Release15AbiProfile();
        auto* secondEnvironment = base_ + kDataRva + 0x500;
        auto* secondConsoleStorage = secondEnvironment + abi.environment.consoleOffset;
        auto* xref = base_ + kTextRva + 0x300;
        BuildXref(xref, secondConsoleStorage);
    }

private:
    static constexpr std::size_t kAllocationSize = 0x6000;
    static constexpr std::uint32_t kTextRva = 0x1000;
    static constexpr std::uint32_t kRdataRva = 0x2000;
    static constexpr std::uint32_t kDataRva = 0x3000;
    static constexpr std::size_t kSectionSize = 0x1000;

    void BuildHeaders()
    {
        auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base_);
        dos->e_magic = IMAGE_DOS_SIGNATURE;
        dos->e_lfanew = 0x100;

        auto* nt = reinterpret_cast<IMAGE_NT_HEADERS64*>(base_ + dos->e_lfanew);
        nt->Signature = IMAGE_NT_SIGNATURE;
        nt->FileHeader.Machine = IMAGE_FILE_MACHINE_AMD64;
        nt->FileHeader.NumberOfSections = 3;
        nt->FileHeader.SizeOfOptionalHeader = sizeof(IMAGE_OPTIONAL_HEADER64);
        nt->FileHeader.TimeDateStamp = 0x6a350e20;
        nt->OptionalHeader.Magic = IMAGE_NT_OPTIONAL_HDR64_MAGIC;
        nt->OptionalHeader.SizeOfImage = 0x05b2d000;
        nt->OptionalHeader.CheckSum = 0;

        auto* sections = IMAGE_FIRST_SECTION(nt);
        SetSection(sections[0], ".text", kTextRva,
            IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_EXECUTE | IMAGE_SCN_CNT_CODE);
        SetSection(sections[1], ".rdata", kRdataRva,
            IMAGE_SCN_MEM_READ | IMAGE_SCN_CNT_INITIALIZED_DATA);
        SetSection(sections[2], ".data", kDataRva,
            IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_WRITE | IMAGE_SCN_CNT_INITIALIZED_DATA);
    }

    static void SetSection(
        IMAGE_SECTION_HEADER& section,
        const char* name,
        std::uint32_t rva,
        DWORD characteristics)
    {
        std::memcpy(section.Name, name, (std::min)(std::strlen(name), sizeof(section.Name)));
        section.VirtualAddress = rva;
        section.Misc.VirtualSize = static_cast<DWORD>(kSectionSize);
        section.SizeOfRawData = static_cast<DWORD>(kSectionSize);
        section.Characteristics = characteristics;
    }

    void BuildAnchorPath()
    {
        const auto& abi = kcd2::runtime::Release15AbiProfile();
        anchor_ = base_ + kRdataRva + 0x100;
        constexpr char kAnchor[] = "exec autoexec.cfg";
        std::memcpy(anchor_, kAnchor, sizeof(kAnchor));

        environment_ = base_ + kDataRva + 0x100;
        auto* consoleStorage = environment_ + abi.environment.consoleOffset;
        auto* xref = base_ + kTextRva + 0x200;
        BuildXref(xref, consoleStorage);
    }

    void BuildXref(std::uint8_t* xref, std::uint8_t* consoleStorage)
    {
        static constexpr std::uint8_t kContext[7] = {
            0x4c, 0x8b, 0x92, 0x18, 0x01, 0x00, 0x00};
        std::memcpy(xref - 7, kContext, sizeof(kContext));

        auto* mov = xref - 0x17;
        mov[0] = 0x48;
        mov[1] = 0x8b;
        mov[2] = 0x0d;
        WriteDisp32(mov, consoleStorage);

        xref[0] = 0x48;
        xref[1] = 0x8d;
        xref[2] = 0x15;
        WriteDisp32(xref, anchor_);
    }

    static void WriteDisp32(std::uint8_t* instruction, const std::uint8_t* target)
    {
        const auto next = reinterpret_cast<std::intptr_t>(instruction + 7);
        const auto destination = reinterpret_cast<std::intptr_t>(target);
        const auto delta = destination - next;
        if (delta < (std::numeric_limits<std::int32_t>::min)()
            || delta > (std::numeric_limits<std::int32_t>::max)())
            std::abort();
        const auto displacement = static_cast<std::int32_t>(delta);
        std::memcpy(instruction + 3, &displacement, sizeof(displacement));
    }

    std::uint8_t* base_{};
    std::uint8_t* anchor_{};
    std::uint8_t* environment_{};
};

bool TestKnownStorefrontRegistryAndAbiSeparation()
{
    std::size_t count{};
    const auto* stores = kcd2::runtime::KnownStorefronts(count);
    CHECK(stores != nullptr);
    CHECK(count == 4);

    const auto* steam = kcd2::runtime::FindStorefront(kcd2::runtime::Storefront::Steam);
    const auto* epic = kcd2::runtime::FindStorefront(kcd2::runtime::Storefront::EpicGamesStore);
    const auto* gog = kcd2::runtime::FindStorefront(kcd2::runtime::Storefront::GOG);
    const auto* xbox = kcd2::runtime::FindStorefront(kcd2::runtime::Storefront::XboxMicrosoftStore);
    CHECK(steam && epic && gog && xbox);

    const auto& release15 = kcd2::runtime::Release15AbiProfile();
    CHECK(steam->release15Abi == &release15);
    CHECK(epic->release15Abi == &release15);
    CHECK(gog->release15Abi == &release15);
    CHECK(xbox->release15Abi == &release15);
    CHECK(steam->publicRelease15AddressLibrary);
    CHECK(epic->publicRelease15AddressLibrary);
    CHECK(gog->publicRelease15AddressLibrary);
    CHECK(!xbox->publicRelease15AddressLibrary);
    CHECK(kcd2::runtime::MatureRuntimeSupports(release15));
    return true;
}

bool TestStorefrontMarkerDetection()
{
    SyntheticWhGame image;
    CHECK(image.valid());

    kcd2::runtime::Storefront storefront{};
    image.SetStorefrontMarker("steam_api64.dll");
    CHECK(kcd2::runtime::DetectStorefront(image.module(), storefront));
    CHECK(storefront == kcd2::runtime::Storefront::Steam);

    image.SetStorefrontMarker("Galaxy64.dll");
    CHECK(kcd2::runtime::DetectStorefront(image.module(), storefront));
    CHECK(storefront == kcd2::runtime::Storefront::GOG);

    image.SetStorefrontMarker("EOSSDK-Win64-Shipping.dll");
    CHECK(kcd2::runtime::DetectStorefront(image.module(), storefront));
    CHECK(storefront == kcd2::runtime::Storefront::EpicGamesStore);
    return true;
}

bool TestSteamExactFingerprintAndCanonicalEnvironment()
{
    SyntheticWhGame image;
    CHECK(image.valid());

    kcd2::runtime::DetectedBuildIdentity identity{};
    CHECK(kcd2::runtime::ReadFingerprint(image.module(), identity.fingerprint));
    const auto* steam = kcd2::runtime::MatchSupportedBuild(identity);
    CHECK(steam != nullptr);
    CHECK(steam->storefront == kcd2::runtime::Storefront::Steam);
    CHECK(steam->identityStrategy == kcd2::runtime::BuildIdentityStrategy::ExactPeFingerprint);
    CHECK(steam->environmentLocator
        == kcd2::runtime::EnvironmentLocatorStrategy::CanonicalPConsoleCodeAnchor);
    CHECK(steam->abi == &kcd2::runtime::Release15AbiProfile());

    auto syntheticProfile = *steam;
    syntheticProfile.expectedEnvironmentRva = image.environmentRva();
    std::uint8_t* environment{};
    CHECK(kcd2::runtime::ResolveCanonicalEnvironmentBase(
        image.module(), syntheticProfile, environment));
    CHECK(environment == image.environment());

    syntheticProfile.expectedEnvironmentRva += 8;
    environment = reinterpret_cast<std::uint8_t*>(1);
    CHECK(!kcd2::runtime::ResolveCanonicalEnvironmentBase(
        image.module(), syntheticProfile, environment));
    CHECK(environment == nullptr);
    return true;
}

bool TestGogAndEpicBuildIdentity()
{
    kcd2::runtime::DetectedBuildIdentity gog{};
    gog.fingerprint = {0x12345678, 0x01000000, 0};
    gog.storefront = kcd2::runtime::Storefront::GOG;
    gog.buildCode = "release_1_5-15693";
    const auto* gogProfile = kcd2::runtime::MatchSupportedBuild(gog);
    CHECK(gogProfile != nullptr);
    CHECK(gogProfile->storefront == kcd2::runtime::Storefront::GOG);
    CHECK(gogProfile->identityStrategy == kcd2::runtime::BuildIdentityStrategy::StorefrontBuildCode);
    CHECK(gogProfile->expectedEnvironmentRva == 0x049177f8);
    CHECK(gogProfile->validation == kcd2::runtime::BuildValidationLevel::ExternalRuntimeEvidence);

    auto wrongGog = gog;
    wrongGog.buildCode = "release_1_5-99999";
    CHECK(kcd2::runtime::MatchSupportedBuild(wrongGog) == nullptr);

    kcd2::runtime::DetectedBuildIdentity epic{};
    epic.fingerprint = {0x6a34f917, 0x01000000, 0};
    epic.storefront = kcd2::runtime::Storefront::EpicGamesStore;
    epic.buildCode = "release_1_5-15693";
    const auto* epicProfile = kcd2::runtime::MatchSupportedBuild(epic);
    CHECK(epicProfile != nullptr);
    CHECK(epicProfile->storefront == kcd2::runtime::Storefront::EpicGamesStore);
    CHECK(epicProfile->requiredTimestamp == 0x6a34f917);
    CHECK(epicProfile->expectedEnvironmentRva == 0x0491d8b8);

    auto wrongEpicTimestamp = epic;
    wrongEpicTimestamp.fingerprint.timestamp ^= 1;
    CHECK(kcd2::runtime::MatchSupportedBuild(wrongEpicTimestamp) == nullptr);

    auto unknownStore = epic;
    unknownStore.storefront = kcd2::runtime::Storefront::Unknown;
    CHECK(kcd2::runtime::MatchSupportedBuild(unknownStore) == nullptr);
    return true;
}

bool TestUnknownAndMismatchedBuildsFailClosed()
{
    kcd2::runtime::DetectedBuildIdentity unknown{};
    unknown.fingerprint = {0x11111111, 0x05b2d000, 0};
    CHECK(kcd2::runtime::MatchSupportedBuild(unknown) == nullptr);

    kcd2::runtime::DetectedBuildIdentity xbox{};
    xbox.fingerprint = {0x6a391f7b, 0x05bf2000, 0};
    const auto* xboxProfile = kcd2::runtime::MatchSupportedBuild(xbox);
    CHECK(xboxProfile != nullptr);
    CHECK(xboxProfile->storefront == kcd2::runtime::Storefront::XboxMicrosoftStore);
    CHECK(xboxProfile->identityStrategy == kcd2::runtime::BuildIdentityStrategy::ExactPeFingerprint);
    CHECK(xboxProfile->environmentLocator
        == kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan);
    CHECK(xboxProfile->validation == kcd2::runtime::BuildValidationLevel::RuntimeTested);
    return true;
}

bool TestAmbiguousAnchorFailsClosed()
{
    SyntheticWhGame image;
    CHECK(image.valid());

    kcd2::runtime::DetectedBuildIdentity identity{};
    CHECK(kcd2::runtime::ReadFingerprint(image.module(), identity.fingerprint));
    const auto* steam = kcd2::runtime::MatchSupportedBuild(identity);
    CHECK(steam != nullptr);

    auto syntheticProfile = *steam;
    syntheticProfile.expectedEnvironmentRva = image.environmentRva();
    image.AddAmbiguousConsoleReference();
    std::uint8_t* environment = reinterpret_cast<std::uint8_t*>(1);
    CHECK(!kcd2::runtime::ResolveCanonicalEnvironmentBase(
        image.module(), syntheticProfile, environment));
    CHECK(environment == nullptr);
    return true;
}

} // namespace

int main()
{
    if (!TestKnownStorefrontRegistryAndAbiSeparation())
        return 1;
    if (!TestStorefrontMarkerDetection())
        return 2;
    if (!TestSteamExactFingerprintAndCanonicalEnvironment())
        return 3;
    if (!TestGogAndEpicBuildIdentity())
        return 4;
    if (!TestUnknownAndMismatchedBuildsFailClosed())
        return 5;
    if (!TestAmbiguousAnchorFailsClosed())
        return 6;

    std::puts("runtime profile tests passed");
    return 0;
}
