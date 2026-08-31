#include "kcd2_runtime_profile.h"
#include "kcd2_abi.h"

#include <windows.h>

#include <cstdint>
#include <cstdio>
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

    void AddAmbiguousConsoleReference()
    {
        auto* secondEnvironment = base_ + kDataRva + 0x500;
        auto* secondConsoleStorage = secondEnvironment + kcd2::kEnvConsoleOffset;
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
        anchor_ = base_ + kRdataRva + 0x100;
        constexpr char kAnchor[] = "exec autoexec.cfg";
        std::memcpy(anchor_, kAnchor, sizeof(kAnchor));

        environment_ = base_ + kDataRva + 0x100;
        auto* consoleStorage = environment_ + kcd2::kEnvConsoleOffset;
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

bool TestFingerprintAndCanonicalEnvironment()
{
    SyntheticWhGame image;
    CHECK(image.valid());

    kcd2::runtime::Fingerprint fingerprint{};
    CHECK(kcd2::runtime::ReadFingerprint(image.module(), fingerprint));
    CHECK(fingerprint.timestamp == 0x6a350e20);
    CHECK(fingerprint.imageSize == 0x05b2d000);
    CHECK(fingerprint.checksum == 0);

    const auto* steam = kcd2::runtime::MatchSupportedBuild(fingerprint);
    CHECK(steam != nullptr);
    CHECK(steam->id == kcd2::runtime::StorefrontProfile::Steam15693);

    std::uint8_t* environment{};
    CHECK(kcd2::runtime::ResolveCanonicalEnvironmentBase(
        image.module(), *steam, environment));
    CHECK(environment == image.environment());
    return true;
}

bool TestUnknownAndMismatchedBuildsFailClosed()
{
    SyntheticWhGame image;
    CHECK(image.valid());

    kcd2::runtime::Fingerprint unknown{0x11111111, 0x05b2d000, 0};
    CHECK(kcd2::runtime::MatchSupportedBuild(unknown) == nullptr);

    const kcd2::runtime::Fingerprint xboxFingerprint{0x6a391f7b, 0x05bf2000, 0};
    const auto* xbox = kcd2::runtime::MatchSupportedBuild(xboxFingerprint);
    CHECK(xbox != nullptr);

    std::uint8_t* environment = reinterpret_cast<std::uint8_t*>(1);
    CHECK(!kcd2::runtime::ResolveCanonicalEnvironmentBase(
        image.module(), *xbox, environment));
    CHECK(environment == nullptr);
    return true;
}

bool TestAmbiguousAnchorFailsClosed()
{
    SyntheticWhGame image;
    CHECK(image.valid());

    kcd2::runtime::Fingerprint fingerprint{};
    CHECK(kcd2::runtime::ReadFingerprint(image.module(), fingerprint));
    const auto* steam = kcd2::runtime::MatchSupportedBuild(fingerprint);
    CHECK(steam != nullptr);

    image.AddAmbiguousConsoleReference();
    std::uint8_t* environment = reinterpret_cast<std::uint8_t*>(1);
    CHECK(!kcd2::runtime::ResolveCanonicalEnvironmentBase(
        image.module(), *steam, environment));
    CHECK(environment == nullptr);
    return true;
}

} // namespace

int main()
{
    if (!TestFingerprintAndCanonicalEnvironment())
        return 1;
    if (!TestUnknownAndMismatchedBuildsFailClosed())
        return 2;
    if (!TestAmbiguousAnchorFailsClosed())
        return 3;

    std::puts("runtime profile tests passed");
    return 0;
}
