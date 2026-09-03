#include "kcd2_runtime_profile.h"
#include "kcd2_abi.h"

#include <windows.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <string>
#include <system_error>
#include <vector>

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
        nt->OptionalHeader.SizeOfImage = static_cast<DWORD>(kAllocationSize);
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

class TemporaryBuildMetadata {
public:
    TemporaryBuildMetadata()
    {
        const auto unique = std::to_wstring(GetCurrentProcessId())
            + L"-" + std::to_wstring(GetTickCount64());
        root_ = std::filesystem::temp_directory_path()
            / (L"kcd2-clean-pause-runtime-profile-" + unique);
        gameRoot_ = root_ / L"Kingdom Come Deliverance II";
        std::filesystem::create_directories(gameRoot_);

        std::ofstream metadata(gameRoot_ / L"whdlversions.json", std::ios::binary);
        metadata
            << R"({"Assembly":{"Id":15693,"DateTestedData":0},)"
            << R"("Preset":{"Branch":{"Id":9,"Name":"release_1_5"}}})";
    }

    ~TemporaryBuildMetadata()
    {
        std::error_code error;
        std::filesystem::remove_all(root_, error);
    }

    std::filesystem::path modulePath(const std::filesystem::path& relativeDirectory) const
    {
        const auto directory = gameRoot_ / relativeDirectory;
        std::filesystem::create_directories(directory);
        return directory / L"WHGame.dll";
    }

private:
    std::filesystem::path root_{};
    std::filesystem::path gameRoot_{};
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

    image.SetStorefrontMarker(nullptr);
    CHECK(!kcd2::runtime::DetectStorefront(image.module(), storefront));
    CHECK(storefront == kcd2::runtime::Storefront::Unknown);
    return true;
}

bool TestBuildCodeParsingAndPathDiscovery()
{
    std::string buildCode;
    CHECK(kcd2::runtime::ParseWarhorseBuildCode(
        R"({"Assembly":{"Id":15693},"Preset":{"Branch":{"Name":"release_1_5"}}})",
        buildCode));
    CHECK(buildCode == "release_1_5-15693");

    CHECK(!kcd2::runtime::ParseWarhorseBuildCode(
        R"({"Assembly":{"Id":15693},"Preset":{}})", buildCode));
    CHECK(buildCode.empty());

    TemporaryBuildMetadata fixture;
    const std::vector<std::filesystem::path> layouts{
        std::filesystem::path(L"Bin") / L"Win64MasterMasterSteamPGO",
        std::filesystem::path{},
        std::filesystem::path(L"Bin") / L"Win64MasterMasterEpicPGO",
    };
    for (const auto& layout : layouts) {
        buildCode.clear();
        CHECK(kcd2::runtime::ReadBuildCodeFromModulePath(
            fixture.modulePath(layout).wstring(), buildCode));
        CHECK(buildCode == "release_1_5-15693");
    }
    return true;
}

bool TestSteamExactFingerprintAndEnvironmentValidation()
{
    SyntheticWhGame image;
    CHECK(image.valid());

    kcd2::runtime::DetectedBuildIdentity identity{};
    identity.fingerprint = {0x6a350e20, 0x05b2d000, 0};
    const auto* steam = kcd2::runtime::MatchSupportedBuild(identity);
    CHECK(steam != nullptr);
    CHECK(steam->storefront == kcd2::runtime::Storefront::Steam);
    CHECK(steam->identityStrategy == kcd2::runtime::BuildIdentityStrategy::ExactPeFingerprint);
    CHECK(steam->environmentLocator
        == kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation);
    CHECK(steam->frameworkLocator
        == kcd2::runtime::FrameworkLocatorStrategy::ExactSingletonRva);
    CHECK(steam->expectedFrameworkStorageRva == 0x0549d328);
    CHECK(steam->expectedFrameworkVtableRva == 0x040472d0);
    CHECK(steam->capabilities.deferPauseBarrierUntilPauseInput);
    CHECK(steam->capabilities.pinHudRootDuringPause);
    CHECK(steam->capabilities.prehideMenuDuringPauseTransition);
    CHECK(steam->abi == &kcd2::runtime::Release15AbiProfile());

    auto syntheticProfile = *steam;
    syntheticProfile.exactFingerprint = {0x6a350e20, 0x6000, 0};
    syntheticProfile.expectedEnvironmentRva = image.environmentRva();
    std::uint8_t* environment{};
    CHECK(kcd2::runtime::ResolveProfileEnvironmentBase(
        image.module(), syntheticProfile, environment));
    CHECK(environment == image.environment());

    syntheticProfile.expectedEnvironmentRva += 8;
    environment = reinterpret_cast<std::uint8_t*>(1);
    CHECK(!kcd2::runtime::ResolveProfileEnvironmentBase(
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
    CHECK(gogProfile->environmentLocator
        == kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRva);
    CHECK(gogProfile->expectedEnvironmentRva == 0x049177f8);
    CHECK(gogProfile->frameworkLocator == kcd2::runtime::FrameworkLocatorStrategy::None);
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
    CHECK(epicProfile->environmentLocator
        == kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRva);
    CHECK(epicProfile->requiredTimestamp == 0x6a34f917);
    CHECK(epicProfile->expectedEnvironmentRva == 0x0491d8b8);
    CHECK(epicProfile->frameworkLocator == kcd2::runtime::FrameworkLocatorStrategy::None);

    auto wrongEpicTimestamp = epic;
    wrongEpicTimestamp.fingerprint.timestamp ^= 1;
    CHECK(kcd2::runtime::MatchSupportedBuild(wrongEpicTimestamp) == nullptr);

    auto unknownStore = epic;
    unknownStore.storefront = kcd2::runtime::Storefront::Unknown;
    CHECK(kcd2::runtime::MatchSupportedBuild(unknownStore) == nullptr);
    return true;
}

bool TestExactRvaLocatorDoesNotDependOnUnverifiedAnchorShape()
{
    SyntheticWhGame image;
    CHECK(image.valid());
    image.AddAmbiguousConsoleReference();

    kcd2::runtime::DetectedBuildIdentity gogIdentity{};
    gogIdentity.storefront = kcd2::runtime::Storefront::GOG;
    gogIdentity.buildCode = "release_1_5-15693";
    const auto* gog = kcd2::runtime::MatchSupportedBuild(gogIdentity);
    CHECK(gog != nullptr);

    auto syntheticProfile = *gog;
    syntheticProfile.expectedEnvironmentRva = image.environmentRva();
    std::uint8_t* environment{};
    CHECK(kcd2::runtime::ResolveProfileEnvironmentBase(
        image.module(), syntheticProfile, environment));
    CHECK(environment == image.environment());
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
    CHECK(xboxProfile->frameworkLocator
        == kcd2::runtime::FrameworkLocatorStrategy::LegacyGameFrameworkSlot);
    CHECK(!xboxProfile->capabilities.deferPauseBarrierUntilPauseInput);
    CHECK(!xboxProfile->capabilities.pinHudRootDuringPause);
    CHECK(!xboxProfile->capabilities.prehideMenuDuringPauseTransition);
    CHECK(xboxProfile->validation == kcd2::runtime::BuildValidationLevel::RuntimeTested);
    return true;
}

bool TestAmbiguousAnchorFailsClosedForSteam()
{
    SyntheticWhGame image;
    CHECK(image.valid());

    kcd2::runtime::DetectedBuildIdentity identity{};
    identity.fingerprint = {0x6a350e20, 0x05b2d000, 0};
    const auto* steam = kcd2::runtime::MatchSupportedBuild(identity);
    CHECK(steam != nullptr);

    auto syntheticProfile = *steam;
    syntheticProfile.exactFingerprint = {0x6a350e20, 0x6000, 0};
    syntheticProfile.expectedEnvironmentRva = image.environmentRva();
    image.AddAmbiguousConsoleReference();
    std::uint8_t* environment = reinterpret_cast<std::uint8_t*>(1);
    CHECK(!kcd2::runtime::ResolveProfileEnvironmentBase(
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
    if (!TestBuildCodeParsingAndPathDiscovery())
        return 3;
    if (!TestSteamExactFingerprintAndEnvironmentValidation())
        return 4;
    if (!TestGogAndEpicBuildIdentity())
        return 5;
    if (!TestExactRvaLocatorDoesNotDependOnUnverifiedAnchorShape())
        return 6;
    if (!TestUnknownAndMismatchedBuildsFailClosed())
        return 7;
    if (!TestAmbiguousAnchorFailsClosedForSteam())
        return 8;

    std::puts("runtime profile tests passed");
    return 0;
}
