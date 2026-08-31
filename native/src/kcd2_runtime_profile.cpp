#include "kcd2_runtime_profile.h"
#include "kcd2_abi.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <vector>

namespace kcd2::runtime {
namespace {

struct ImageView {
    std::uint8_t* base{};
    IMAGE_NT_HEADERS64* nt{};
    IMAGE_SECTION_HEADER* sections{};
    unsigned sectionCount{};
};

// Xbox Store / Xbox app 1.5.6 was captured from the reviewed retail runtime
// tracked in issue #36. Steam is the independently identified release_1_5-15693
// build. Storefronts stay separate even though their verified KCD2 1.5.6 ABI is
// currently the same.
constexpr std::array<BuildProfile, 2> kSupportedBuilds{{
    {StorefrontProfile::XboxStore156, "Xbox Store 1.5.6", {0x6a391f7b, 0x05bf2000, 0x00000000}},
    {StorefrontProfile::Steam15693, "Steam 1.5.6 release_1_5-15693", {0x6a350e20, 0x05b2d000, 0x00000000}},
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
            return false; // Ambiguous anchor: fail closed instead of choosing first.
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

const BuildProfile* MatchSupportedBuild(const Fingerprint& fingerprint)
{
    for (const auto& profile : kSupportedBuilds) {
        if (FingerprintsEqual(profile.fingerprint, fingerprint))
            return &profile;
    }
    return nullptr;
}

bool ResolveCanonicalEnvironmentBase(
    HMODULE whGame,
    const BuildProfile& profile,
    std::uint8_t*& environmentBase)
{
    environmentBase = nullptr;

    ImageView image{};
    if (!GetImageView(whGame, image))
        return false;

    const Fingerprint actual{
        image.nt->FileHeader.TimeDateStamp,
        image.nt->OptionalHeader.SizeOfImage,
        image.nt->OptionalHeader.CheckSum};
    if (!FingerprintsEqual(actual, profile.fingerprint))
        return false;

    std::uint8_t* consoleStorage{};
    if (!ResolveUniqueConsoleStorage(image, consoleStorage))
        return false;

    // Public KCD2 1.5.6 RE establishes the canonical SSystemGlobalEnvironment
    // base with pConsole at +0xB0. Some engine code keeps/uses a gEnv+8 pointer,
    // which makes the same field appear as +0xA8 in code-coordinate notes. Always
    // normalize back to the canonical struct base here before applying ABI offsets.
    const auto storageAddress = reinterpret_cast<std::uintptr_t>(consoleStorage);
    if (storageAddress < kEnvConsoleOffset)
        return false;
    auto* candidate = reinterpret_cast<std::uint8_t*>(storageAddress - kEnvConsoleOffset);

    if (!AddressInSection(
            image,
            candidate,
            kEnvSize,
            IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_WRITE))
        return false;
    if (!IsReadable(candidate, kEnvSize))
        return false;
    if (candidate + kEnvConsoleOffset != consoleStorage)
        return false;

    environmentBase = candidate;
    return true;
}

} // namespace kcd2::runtime
