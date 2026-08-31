#include "kcd2_runtime_profile.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iterator>
#include <string>
#include <utility>
#include <vector>

namespace kcd2::runtime {
namespace {

struct ImageView {
    std::uint8_t* base{};
    IMAGE_NT_HEADERS64* nt{};
    IMAGE_SECTION_HEADER* sections{};
    unsigned sectionCount{};
};

const std::array<StorefrontDescriptor, 4> kKnownStorefronts{{
    {Storefront::Steam, "Steam", &Release15AbiProfile(), true},
    {Storefront::EpicGamesStore, "Epic Games Store", &Release15AbiProfile(), true},
    {Storefront::GOG, "GOG", &Release15AbiProfile(), true},
    {Storefront::XboxMicrosoftStore, "Xbox / Microsoft Store", &Release15AbiProfile(), false},
}};

// Build identity is deliberately layered. When a complete PE fingerprint is known,
// use it. For GOG/Epic, public KCSE/Address-Library evidence identifies the shipped
// binary by distribution + Warhorse Assembly.Id/Branch build code. Those profiles
// are then additionally gated by the exact cross-distribution gEnv RVA during
// environment resolution and by the strong runtime identity checks in the bootstrap.
const std::array<BuildProfile, 4> kSupportedBuilds{{
    {
        Storefront::XboxMicrosoftStore,
        "Xbox / Microsoft Store 1.5.6",
        BuildIdentityStrategy::ExactPeFingerprint,
        {0x6a391f7b, 0x05bf2000, 0x00000000},
        nullptr,
        0,
        0,
        EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan,
        &Release15AbiProfile(),
        BuildValidationLevel::RuntimeTested,
    },
    {
        Storefront::Steam,
        "Steam 1.5.6 release_1_5-15693",
        BuildIdentityStrategy::ExactPeFingerprint,
        {0x6a350e20, 0x05b2d000, 0x00000000},
        "release_1_5-15693",
        0,
        0x0492d7f8,
        EnvironmentLocatorStrategy::CanonicalPConsoleCodeAnchor,
        &Release15AbiProfile(),
        BuildValidationLevel::StaticReverseEngineering,
    },
    {
        Storefront::GOG,
        "GOG 1.5.6 release_1_5-15693",
        BuildIdentityStrategy::StorefrontBuildCode,
        {},
        "release_1_5-15693",
        0,
        0x049177f8,
        EnvironmentLocatorStrategy::CanonicalPConsoleCodeAnchor,
        &Release15AbiProfile(),
        BuildValidationLevel::ExternalRuntimeEvidence,
    },
    {
        Storefront::EpicGamesStore,
        "Epic Games Store 1.5.6 release_1_5-15693",
        BuildIdentityStrategy::StorefrontBuildCode,
        {},
        "release_1_5-15693",
        0x6a34f917,
        0x0491d8b8,
        EnvironmentLocatorStrategy::CanonicalPConsoleCodeAnchor,
        &Release15AbiProfile(),
        BuildValidationLevel::ExternalRuntimeEvidence,
    },
}};

bool IsReadable(const void* ptr, std::size_t size = 1)
{
    if (!ptr || size == 0)
        return false;

    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(ptr, &mbi, sizeof(mbi)) || mbi.State != MEM_COMMIT)
        return false;
    if ((mbi.Protect & PAGE_GUARD) || (mbi.Protect & PAGE_NOACCESS))
        return false;

    const auto begin = reinterpret_cast<std::uintptr_t>(ptr);
    const auto end = begin + size;
    const auto regionEnd = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
    return end >= begin && end <= regionEnd;
}

bool GetImageView(HMODULE module, ImageView& view)
{
    view = {};
    auto* base = reinterpret_cast<std::uint8_t*>(module);
    if (!IsReadable(base, sizeof(IMAGE_DOS_HEADER)))
        return false;

    auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0)
        return false;

    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (!IsReadable(nt, sizeof(*nt)) || nt->Signature != IMAGE_NT_SIGNATURE)
        return false;

    view.base = base;
    view.nt = nt;
    view.sections = IMAGE_FIRST_SECTION(nt);
    view.sectionCount = nt->FileHeader.NumberOfSections;
    return true;
}

bool FingerprintsEqual(const Fingerprint& left, const Fingerprint& right)
{
    return left.timestamp == right.timestamp
        && left.imageSize == right.imageSize
        && left.checksum == right.checksum;
}

bool AddressInSection(
    const ImageView& image,
    const void* address,
    std::size_t size,
    DWORD requiredCharacteristics)
{
    if (!address || size == 0)
        return false;

    const auto value = reinterpret_cast<std::uintptr_t>(address);
    const auto imageBegin = reinterpret_cast<std::uintptr_t>(image.base);
    for (unsigned index = 0; index < image.sectionCount; ++index) {
        const auto& section = image.sections[index];
        if ((section.Characteristics & requiredCharacteristics) != requiredCharacteristics)
            continue;

        const auto begin = imageBegin + section.VirtualAddress;
        const auto virtualSize = static_cast<std::size_t>(section.Misc.VirtualSize);
        const auto rawSize = static_cast<std::size_t>(section.SizeOfRawData);
        const auto sectionSize = (std::max)(virtualSize, rawSize);
        const auto end = begin + sectionSize;
        if (end < begin || value < begin || value > end)
            continue;
        if (size <= end - value)
            return true;
    }
    return false;
}

std::uint8_t* FindAscii(const ImageView& image, const char* text)
{
    const std::size_t textSize = std::strlen(text);
    for (unsigned index = 0; index < image.sectionCount; ++index) {
        const auto& section = image.sections[index];
        if (!(section.Characteristics & IMAGE_SCN_MEM_READ))
            continue;

        auto* start = image.base + section.VirtualAddress;
        const std::size_t size = section.Misc.VirtualSize;
        if (size < textSize || !IsReadable(start, size))
            continue;

        for (std::size_t offset = 0; offset + textSize <= size; ++offset) {
            if (std::memcmp(start + offset, text, textSize) == 0)
                return start + offset;
        }
    }
    return nullptr;
}

bool ResolveStorefront(const ImageView& image, Storefront& out)
{
    out = Storefront::Unknown;
    struct Marker {
        const char* text;
        Storefront storefront;
    };
    static constexpr std::array<Marker, 3> kMarkers{{
        {"steam_api64.dll", Storefront::Steam},
        {"Galaxy64.dll", Storefront::GOG},
        {"EOSSDK-Win64-Shipping.dll", Storefront::EpicGamesStore},
    }};

    unsigned matches{};
    for (const auto& marker : kMarkers) {
        if (!FindAscii(image, marker.text))
            continue;
        out = marker.storefront;
        ++matches;
    }
    if (matches != 1) {
        out = Storefront::Unknown;
        return false;
    }
    return true;
}

std::wstring ParentPath(std::wstring path)
{
    while (!path.empty() && (path.back() == L'\\' || path.back() == L'/'))
        path.pop_back();
    const auto separator = path.find_last_of(L"\\/");
    if (separator == std::wstring::npos)
        return {};
    path.resize(separator);
    return path;
}

bool ReadSmallTextFile(const std::wstring& path, std::string& out)
{
    out.clear();
    HANDLE file = CreateFileW(
        path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE)
        return false;

    LARGE_INTEGER size{};
    const bool sizeOk = GetFileSizeEx(file, &size) != FALSE
        && size.QuadPart > 0 && size.QuadPart <= 4 * 1024 * 1024;
    if (!sizeOk) {
        CloseHandle(file);
        return false;
    }

    out.resize(static_cast<std::size_t>(size.QuadPart));
    DWORD bytesRead{};
    const bool readOk = ReadFile(
        file, out.data(), static_cast<DWORD>(out.size()), &bytesRead, nullptr) != FALSE;
    CloseHandle(file);
    if (!readOk || bytesRead != out.size()) {
        out.clear();
        return false;
    }
    return true;
}

std::string JsonStringAfter(const std::string& json, const char* anchor, const char* key)
{
    const auto anchorPos = json.find(anchor);
    if (anchorPos == std::string::npos)
        return {};
    const auto keyPos = json.find(key, anchorPos);
    if (keyPos == std::string::npos)
        return {};
    const auto colon = json.find(':', keyPos + std::strlen(key));
    if (colon == std::string::npos)
        return {};
    const auto firstQuote = json.find('"', colon);
    if (firstQuote == std::string::npos)
        return {};
    const auto secondQuote = json.find('"', firstQuote + 1);
    if (secondQuote == std::string::npos)
        return {};
    return json.substr(firstQuote + 1, secondQuote - firstQuote - 1);
}

std::string JsonNumberAfter(const std::string& json, const char* anchor, const char* key)
{
    const auto anchorPos = json.find(anchor);
    if (anchorPos == std::string::npos)
        return {};
    const auto keyPos = json.find(key, anchorPos);
    if (keyPos == std::string::npos)
        return {};
    const auto colon = json.find(':', keyPos + std::strlen(key));
    if (colon == std::string::npos)
        return {};

    auto pos = colon + 1;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t'))
        ++pos;
    const auto begin = pos;
    while (pos < json.size() && json[pos] >= '0' && json[pos] <= '9')
        ++pos;
    return json.substr(begin, pos - begin);
}

bool BuildCodeMatches(const BuildProfile& profile, const DetectedBuildIdentity& identity)
{
    if (identity.storefront != profile.storefront || !profile.buildCode)
        return false;
    if (identity.buildCode != profile.buildCode)
        return false;
    return profile.requiredTimestamp == 0
        || identity.fingerprint.timestamp == profile.requiredTimestamp;
}

std::vector<std::uint8_t*> FindLeaXrefs(const ImageView& image, const std::uint8_t* target)
{
    std::vector<std::uint8_t*> matches;
    for (unsigned index = 0; index < image.sectionCount; ++index) {
        const auto& section = image.sections[index];
        if (!(section.Characteristics & IMAGE_SCN_MEM_EXECUTE))
            continue;

        auto* start = image.base + section.VirtualAddress;
        const std::size_t size = section.Misc.VirtualSize;
        if (size < 7 || !IsReadable(start, size))
            continue;

        for (std::size_t offset = 0; offset + 7 <= size; ++offset) {
            auto* instruction = start + offset;
            if (instruction[0] != 0x48 || instruction[1] != 0x8d || instruction[2] != 0x15)
                continue;

            std::int32_t displacement{};
            std::memcpy(&displacement, instruction + 3, sizeof(displacement));
            if (instruction + 7 + displacement == target)
                matches.push_back(instruction);
        }
    }
    return matches;
}

bool MatchBytes(const std::uint8_t* at, const std::uint8_t* expected, std::size_t size)
{
    return IsReadable(at, size) && std::memcmp(at, expected, size) == 0;
}

bool TryResolveConsoleStorage(
    const ImageView& image,
    std::uint8_t* xref,
    std::uint8_t*& storage)
{
    storage = nullptr;
    static constexpr std::uint8_t kKcd2Context[7] = {
        0x4c, 0x8b, 0x92, 0x18, 0x01, 0x00, 0x00};
    static constexpr std::uint8_t kMovRip[3] = {0x48, 0x8b, 0x0d};

    std::uint8_t* mov{};
    if (xref >= image.base + 0x17 && MatchBytes(xref - 7, kKcd2Context, sizeof(kKcd2Context)))
        mov = xref - 0x17;
    else if (xref >= image.base + 7 && MatchBytes(xref - 7, kMovRip, sizeof(kMovRip)))
        mov = xref - 7;
    else
        return false;

    if (!MatchBytes(mov, kMovRip, sizeof(kMovRip)) || !IsReadable(mov, 7))
        return false;

    std::int32_t displacement{};
    std::memcpy(&displacement, mov + 3, sizeof(displacement));
    auto* candidate = mov + 7 + displacement;
    if (!AddressInSection(
            image,
            candidate,
            sizeof(void*),
            IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_WRITE))
        return false;

    storage = candidate;
    return true;
}

bool ResolveUniqueConsoleStorage(const ImageView& image, std::uint8_t*& storage)
{
    storage = nullptr;
    auto* anchor = FindAscii(image, "exec autoexec.cfg");
    if (!anchor)
        return false;

    const auto xrefs = FindLeaXrefs(image, anchor);
    for (auto* xref : xrefs) {
        std::uint8_t* candidate{};
        if (!TryResolveConsoleStorage(image, xref, candidate))
            continue;
        if (!storage) {
            storage = candidate;
            continue;
        }
        if (candidate != storage)
            return false;
    }
    return storage != nullptr;
}

} // namespace

bool ReadFingerprint(HMODULE whGame, Fingerprint& out)
{
    out = {};
    ImageView image{};
    if (!GetImageView(whGame, image))
        return false;

    out.timestamp = image.nt->FileHeader.TimeDateStamp;
    out.imageSize = image.nt->OptionalHeader.SizeOfImage;
    out.checksum = image.nt->OptionalHeader.CheckSum;
    return true;
}

bool DetectStorefront(HMODULE whGame, Storefront& out)
{
    ImageView image{};
    if (!GetImageView(whGame, image)) {
        out = Storefront::Unknown;
        return false;
    }
    return ResolveStorefront(image, out);
}

bool ReadBuildCode(HMODULE whGame, std::string& out)
{
    out.clear();
    wchar_t modulePath[32768]{};
    const DWORD length = GetModuleFileNameW(whGame, modulePath, static_cast<DWORD>(std::size(modulePath)));
    if (!length || length >= std::size(modulePath))
        return false;

    std::wstring directory = ParentPath(std::wstring(modulePath, length));
    for (unsigned depth = 0; depth < 5 && !directory.empty(); ++depth) {
        std::string json;
        if (ReadSmallTextFile(directory + L"\\whdlversions.json", json)) {
            const std::string branch = JsonStringAfter(json, "\"Branch\"", "\"Name\"");
            const std::string assemblyId = JsonNumberAfter(json, "\"Assembly\"", "\"Id\"");
            if (!branch.empty() && !assemblyId.empty()) {
                out = branch + "-" + assemblyId;
                return true;
            }
        }
        directory = ParentPath(directory);
    }
    return false;
}

bool ReadBuildIdentity(HMODULE whGame, DetectedBuildIdentity& out)
{
    out = {};
    if (!ReadFingerprint(whGame, out.fingerprint))
        return false;

    Storefront storefront{};
    if (DetectStorefront(whGame, storefront))
        out.storefront = storefront;

    std::string buildCode;
    if (ReadBuildCode(whGame, buildCode))
        out.buildCode = std::move(buildCode);
    return true;
}

const BuildProfile* MatchSupportedBuild(const DetectedBuildIdentity& identity)
{
    for (const auto& profile : kSupportedBuilds) {
        switch (profile.identityStrategy) {
        case BuildIdentityStrategy::ExactPeFingerprint:
            if (FingerprintsEqual(profile.exactFingerprint, identity.fingerprint))
                return &profile;
            break;
        case BuildIdentityStrategy::StorefrontBuildCode:
            if (BuildCodeMatches(profile, identity))
                return &profile;
            break;
        default:
            break;
        }
    }
    return nullptr;
}

const StorefrontDescriptor* KnownStorefronts(std::size_t& count)
{
    count = kKnownStorefronts.size();
    return kKnownStorefronts.data();
}

const StorefrontDescriptor* FindStorefront(Storefront storefront)
{
    for (const auto& descriptor : kKnownStorefronts) {
        if (descriptor.id == storefront)
            return &descriptor;
    }
    return nullptr;
}

const char* StorefrontName(Storefront storefront)
{
    const auto* descriptor = FindStorefront(storefront);
    return descriptor ? descriptor->name : "Unknown storefront";
}

const char* BuildIdentityStrategyName(BuildIdentityStrategy strategy)
{
    switch (strategy) {
    case BuildIdentityStrategy::ExactPeFingerprint:
        return "exact-pe-fingerprint";
    case BuildIdentityStrategy::StorefrontBuildCode:
        return "storefront-build-code";
    default:
        return "unknown-build-identity";
    }
}

const char* EnvironmentLocatorName(EnvironmentLocatorStrategy strategy)
{
    switch (strategy) {
    case EnvironmentLocatorStrategy::CanonicalPConsoleCodeAnchor:
        return "canonical-pConsole-code-anchor";
    case EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan:
        return "legacy-xbox-1.5.6-validated-scan";
    default:
        return "unknown-locator";
    }
}

const char* BuildValidationName(BuildValidationLevel validation)
{
    switch (validation) {
    case BuildValidationLevel::RuntimeTested:
        return "runtime-tested";
    case BuildValidationLevel::StaticReverseEngineering:
        return "static-reverse-engineering";
    case BuildValidationLevel::ExternalRuntimeEvidence:
        return "external-runtime-evidence";
    default:
        return "unknown-validation";
    }
}

bool ResolveCanonicalEnvironmentBase(
    HMODULE whGame,
    const BuildProfile& profile,
    std::uint8_t*& environmentBase)
{
    environmentBase = nullptr;
    if (!profile.abi
        || profile.environmentLocator != EnvironmentLocatorStrategy::CanonicalPConsoleCodeAnchor)
        return false;

    ImageView image{};
    if (!GetImageView(whGame, image))
        return false;

    const Fingerprint actual{
        image.nt->FileHeader.TimeDateStamp,
        image.nt->OptionalHeader.SizeOfImage,
        image.nt->OptionalHeader.CheckSum};
    if (profile.identityStrategy == BuildIdentityStrategy::ExactPeFingerprint
        && !FingerprintsEqual(actual, profile.exactFingerprint))
        return false;
    if (profile.requiredTimestamp && actual.timestamp != profile.requiredTimestamp)
        return false;

    std::uint8_t* consoleStorage{};
    if (!ResolveUniqueConsoleStorage(image, consoleStorage))
        return false;

    const auto consoleOffset = profile.abi->environment.consoleOffset;
    const auto environmentSize = profile.abi->environment.size;
    const auto storageAddress = reinterpret_cast<std::uintptr_t>(consoleStorage);
    if (storageAddress < consoleOffset)
        return false;
    auto* candidate = reinterpret_cast<std::uint8_t*>(storageAddress - consoleOffset);

    if (!AddressInSection(
            image,
            candidate,
            environmentSize,
            IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_WRITE))
        return false;
    if (!IsReadable(candidate, environmentSize))
        return false;
    if (candidate + consoleOffset != consoleStorage)
        return false;

    if (profile.expectedEnvironmentRva) {
        const auto candidateRva = static_cast<std::uint64_t>(candidate - image.base);
        if (candidateRva != profile.expectedEnvironmentRva)
            return false;
    }

    environmentBase = candidate;
    return true;
}

} // namespace kcd2::runtime
