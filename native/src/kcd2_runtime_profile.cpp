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

// Build identity and engine-object discovery are independent. Full PE identity is
// retained where captured. GOG/Epic use KCSE's shipped-build identity model and are
// then gated by independently cross-validated distribution-specific gEnv RVAs.
const std::array<BuildProfile, 4> kSupportedBuilds{{
    {
        Storefront::XboxMicrosoftStore,
        "Xbox / Microsoft Store 1.5.6",
        BuildIdentityStrategy::ExactPeFingerprint,
        {0x6a391f7b, 0x05bf2000, 0x00000000},
        nullptr,
        0,
        0x049d6ef8,
        EnvironmentLocatorStrategy::ExactEnvironmentRva,
        FrameworkLocatorStrategy::ExactObjectRva,
        0x056ec680,
        0x040daf18,
        {false, false, false},
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
        EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation,
        FrameworkLocatorStrategy::ExactPointerStorageRva,
        0x0549d328,
        0x040472d0,
        {true, true, true},
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
        EnvironmentLocatorStrategy::ExactEnvironmentRva,
        FrameworkLocatorStrategy::None,
        0,
        0,
        {false, false, false},
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
        EnvironmentLocatorStrategy::ExactEnvironmentRva,
        FrameworkLocatorStrategy::None,
        0,
        0,
        {false, false, false},
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
    if (dos->e_magic != IMAGE_DOS_SIGNATURE
        || dos->e_lfanew <= 0
        || dos->e_lfanew > 0x10000)
        return false;

    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (!IsReadable(nt, sizeof(*nt))
        || nt->Signature != IMAGE_NT_SIGNATURE
        || nt->FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64
        || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC)
        return false;

    const unsigned sectionCount = nt->FileHeader.NumberOfSections;
    if (sectionCount == 0 || sectionCount > 96)
        return false;

    auto* sections = IMAGE_FIRST_SECTION(nt);
    if (!IsReadable(sections, sectionCount * sizeof(IMAGE_SECTION_HEADER)))
        return false;

    view.base = base;
    view.nt = nt;
    view.sections = sections;
    view.sectionCount = sectionCount;
    return true;
}

bool FingerprintsEqual(const Fingerprint& left, const Fingerprint& right)
{
    return left.timestamp == right.timestamp
        && left.imageSize == right.imageSize
        && left.checksum == right.checksum;
}

bool SectionNameEquals(const IMAGE_SECTION_HEADER& section, const char* expected)
{
    char name[IMAGE_SIZEOF_SHORT_NAME + 1]{};
    std::memcpy(name, section.Name, IMAGE_SIZEOF_SHORT_NAME);
    return std::strcmp(name, expected) == 0;
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

std::uint8_t* FindAsciiInSection(
    const ImageView& image,
    const char* sectionName,
    const char* text)
{
    const std::size_t textSize = std::strlen(text);
    if (textSize == 0)
        return nullptr;

    for (unsigned index = 0; index < image.sectionCount; ++index) {
        const auto& section = image.sections[index];
        if (!SectionNameEquals(section, sectionName)
            || !(section.Characteristics & IMAGE_SCN_MEM_READ))
            continue;

        auto* start = image.base + section.VirtualAddress;
        const std::size_t size = section.Misc.VirtualSize;
        if (size < textSize || !IsReadable(start, size))
            return nullptr;

        for (std::size_t offset = 0; offset + textSize <= size; ++offset) {
            if (std::memcmp(start + offset, text, textSize) == 0)
                return start + offset;
        }
        return nullptr;
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
        if (!FindAsciiInSection(image, ".rdata", marker.text))
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
    auto* anchor = FindAsciiInSection(image, ".rdata", "exec autoexec.cfg");
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

bool ParseWarhorseBuildCode(const std::string& json, std::string& out)
{
    out.clear();
    const std::string branch = JsonStringAfter(json, "\"Branch\"", "\"Name\"");
    const std::string assemblyId = JsonNumberAfter(json, "\"Assembly\"", "\"Id\"");
    if (branch.empty() || assemblyId.empty())
        return false;
    out = branch + "-" + assemblyId;
    return true;
}

bool ReadBuildCodeFromModulePath(const std::wstring& modulePath, std::string& out)
{
    out.clear();
    std::wstring directory = ParentPath(modulePath);
    for (unsigned depth = 0; depth < 6 && !directory.empty(); ++depth) {
        std::string json;
        if (ReadSmallTextFile(directory + L"\\whdlversions.json", json))
            return ParseWarhorseBuildCode(json, out);
        directory = ParentPath(directory);
    }
    return false;
}

bool ReadBuildCode(HMODULE whGame, std::string& out)
{
    out.clear();
    wchar_t modulePath[32768]{};
    const DWORD length = GetModuleFileNameW(
        whGame, modulePath, static_cast<DWORD>(std::size(modulePath)));
    if (!length || length >= std::size(modulePath))
        return false;
    return ReadBuildCodeFromModulePath(std::wstring(modulePath, length), out);
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
    case EnvironmentLocatorStrategy::ExactEnvironmentRva:
        return "exact-environment-rva";
    case EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation:
        return "exact-environment-rva+anchor-validation";
    default:
        return "unknown-locator";
    }
}

const char* FrameworkLocatorName(FrameworkLocatorStrategy strategy)
{
    switch (strategy) {
    case FrameworkLocatorStrategy::None:
        return "none";
    case FrameworkLocatorStrategy::ExactPointerStorageRva:
        return "exact-pointer-storage-rva";
    case FrameworkLocatorStrategy::ExactObjectRva:
        return "exact-object-rva";
    default:
        return "unknown-framework-locator";
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

bool ResolveProfileEnvironmentBase(
    HMODULE whGame,
    const BuildProfile& profile,
    std::uint8_t*& environmentBase)
{
    environmentBase = nullptr;
    if (!profile.abi || !profile.expectedEnvironmentRva)
        return false;
    if (profile.environmentLocator != EnvironmentLocatorStrategy::ExactEnvironmentRva
        && profile.environmentLocator
            != EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation)
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

    const auto environmentSize = profile.abi->environment.size;
    const auto imageSize = static_cast<std::size_t>(image.nt->OptionalHeader.SizeOfImage);
    const auto environmentRva = static_cast<std::size_t>(profile.expectedEnvironmentRva);
    if (environmentRva >= imageSize || environmentSize > imageSize - environmentRva)
        return false;

    auto* candidate = image.base + environmentRva;
    if (!AddressInSection(
            image,
            candidate,
            environmentSize,
            IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_WRITE)
        || !IsReadable(candidate, environmentSize))
        return false;

    const auto consoleOffset = profile.abi->environment.consoleOffset;
    if (consoleOffset > environmentSize - sizeof(void*))
        return false;
    auto* expectedConsoleStorage = candidate + consoleOffset;
    if (!AddressInSection(
            image,
            expectedConsoleStorage,
            sizeof(void*),
            IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_WRITE))
        return false;

    if (profile.environmentLocator
        == EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation) {
        std::uint8_t* anchorConsoleStorage{};
        if (!ResolveUniqueConsoleStorage(image, anchorConsoleStorage)
            || anchorConsoleStorage != expectedConsoleStorage)
            return false;
    }

    environmentBase = candidate;
    return true;
}

} // namespace kcd2::runtime
