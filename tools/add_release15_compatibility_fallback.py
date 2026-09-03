#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "native/src/kcd2_runtime_profile.cpp"
NATIVE = ROOT / "native/src/clean_pause_native.cpp"
TESTS = ROOT / "native/tests/runtime_profile_tests.cpp"
PYTEST = ROOT / "tests/test_runtime_profile_contract.py"
CHECKER = ROOT / "tools/validate_native_contract.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing transform marker: {label}")
    return text.replace(old, new, 1)


# --- runtime profile implementation -------------------------------------------------
text = PROFILE.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''bool BuildCodeMatches(const BuildProfile& profile, const DetectedBuildIdentity& identity)\n{\n    if (identity.storefront != profile.storefront || !profile.buildCode)\n        return false;\n    if (identity.buildCode != profile.buildCode)\n        return false;\n    return profile.requiredTimestamp == 0\n        || identity.fingerprint.timestamp == profile.requiredTimestamp;\n}\n''',
    '''bool BuildCodeMatches(const BuildProfile& profile, const DetectedBuildIdentity& identity)\n{\n    if (identity.storefront != profile.storefront || !profile.buildCode)\n        return false;\n    if (identity.buildCode != profile.buildCode)\n        return false;\n    return profile.requiredTimestamp == 0\n        || identity.fingerprint.timestamp == profile.requiredTimestamp;\n}\n\nbool IsCompatibleRelease15BuildCode(const std::string& buildCode)\n{\n    static constexpr char kPrefix[] = "release_1_5-";\n    constexpr std::size_t kPrefixLength = sizeof(kPrefix) - 1;\n    if (buildCode.size() <= kPrefixLength\n        || buildCode.compare(0, kPrefixLength, kPrefix) != 0)\n        return false;\n    return std::all_of(\n        buildCode.begin() + static_cast<std::ptrdiff_t>(kPrefixLength),\n        buildCode.end(),\n        [](char value) { return value >= '0' && value <= '9'; });\n}\n''',
    "release15 build-code helper")

text = replace_once(
    text,
    '''const BuildProfile* MatchSupportedBuild(const DetectedBuildIdentity& identity)\n{\n    for (const auto& profile : kSupportedBuilds) {\n        switch (profile.identityStrategy) {\n        case BuildIdentityStrategy::ExactPeFingerprint:\n            if (FingerprintsEqual(profile.exactFingerprint, identity.fingerprint))\n                return &profile;\n            break;\n        case BuildIdentityStrategy::StorefrontBuildCode:\n            if (BuildCodeMatches(profile, identity))\n                return &profile;\n            break;\n        default:\n            break;\n        }\n    }\n    return nullptr;\n}\n''',
    '''const BuildProfile* MatchSupportedBuild(const DetectedBuildIdentity& identity)\n{\n    for (const auto& profile : kSupportedBuilds) {\n        switch (profile.identityStrategy) {\n        case BuildIdentityStrategy::ExactPeFingerprint:\n            if (FingerprintsEqual(profile.exactFingerprint, identity.fingerprint))\n                return &profile;\n            break;\n        case BuildIdentityStrategy::StorefrontBuildCode:\n            if (BuildCodeMatches(profile, identity))\n                return &profile;\n            break;\n        case BuildIdentityStrategy::CompatibleReleaseBranch:\n        default:\n            break;\n        }\n    }\n    return nullptr;\n}\n\nbool BuildCompatibleRelease15Fallback(\n    const DetectedBuildIdentity& identity,\n    BuildProfile& out)\n{\n    out = {};\n    if (!IsCompatibleRelease15BuildCode(identity.buildCode))\n        return false;\n\n    const AbiProfile* abi = &Release15AbiProfile();\n    if (const auto* storefront = FindStorefront(identity.storefront)) {\n        if (!storefront->release15Abi)\n            return false;\n        abi = storefront->release15Abi;\n    }\n    if (!abi || !MatureRuntimeSupports(*abi))\n        return false;\n\n    out.storefront = identity.storefront;\n    out.name = "release_1_5 compatibility fallback";\n    out.identityStrategy = BuildIdentityStrategy::CompatibleReleaseBranch;\n    out.buildCode = "release_1_5-*";\n    out.environmentLocator = EnvironmentLocatorStrategy::AnchorDerivedEnvironment;\n    out.frameworkLocator = FrameworkLocatorStrategy::None;\n    out.capabilities = {};\n    out.abi = abi;\n    out.validation = BuildValidationLevel::CompatibilityFallback;\n    return true;\n}\n''',
    "fallback profile builder")

text = replace_once(
    text,
    '''    case BuildIdentityStrategy::StorefrontBuildCode:\n        return "storefront-build-code";\n    default:\n''',
    '''    case BuildIdentityStrategy::StorefrontBuildCode:\n        return "storefront-build-code";\n    case BuildIdentityStrategy::CompatibleReleaseBranch:\n        return "compatible-release-branch";\n    default:\n''',
    "identity strategy name")

text = replace_once(
    text,
    '''    case EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation:\n        return "exact-environment-rva+anchor-validation";\n    default:\n''',
    '''    case EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation:\n        return "exact-environment-rva+anchor-validation";\n    case EnvironmentLocatorStrategy::AnchorDerivedEnvironment:\n        return "anchor-derived-environment";\n    default:\n''',
    "environment locator name")

text = replace_once(
    text,
    '''    case BuildValidationLevel::ExternalRuntimeEvidence:\n        return "external-runtime-evidence";\n    default:\n''',
    '''    case BuildValidationLevel::ExternalRuntimeEvidence:\n        return "external-runtime-evidence";\n    case BuildValidationLevel::CompatibilityFallback:\n        return "compatibility-fallback";\n    default:\n''',
    "validation name")

start = text.index("bool ResolveProfileEnvironmentBase(\n")
end = text.index("\n} // namespace kcd2::runtime", start)
new_resolver = r'''bool ResolveProfileEnvironmentBase(
    HMODULE whGame,
    const BuildProfile& profile,
    std::uint8_t*& environmentBase)
{
    environmentBase = nullptr;
    if (!profile.abi)
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
    const auto consoleOffset = profile.abi->environment.consoleOffset;
    if (environmentSize == 0 || consoleOffset > environmentSize - sizeof(void*))
        return false;

    std::uint8_t* candidate{};
    std::uint8_t* anchorConsoleStorage{};
    if (profile.environmentLocator == EnvironmentLocatorStrategy::AnchorDerivedEnvironment) {
        if (!ResolveUniqueConsoleStorage(image, anchorConsoleStorage))
            return false;
        const auto anchorAddress = reinterpret_cast<std::uintptr_t>(anchorConsoleStorage);
        const auto imageBegin = reinterpret_cast<std::uintptr_t>(image.base);
        if (anchorAddress < imageBegin + consoleOffset)
            return false;
        candidate = anchorConsoleStorage - consoleOffset;
    } else {
        if (profile.environmentLocator != EnvironmentLocatorStrategy::ExactEnvironmentRva
            && profile.environmentLocator
                != EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation)
            return false;
        if (!profile.expectedEnvironmentRva)
            return false;

        const auto imageSize = static_cast<std::size_t>(image.nt->OptionalHeader.SizeOfImage);
        const auto environmentRva = static_cast<std::size_t>(profile.expectedEnvironmentRva);
        if (environmentRva >= imageSize || environmentSize > imageSize - environmentRva)
            return false;
        candidate = image.base + environmentRva;
    }

    if (!AddressInSection(
            image,
            candidate,
            environmentSize,
            IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_WRITE)
        || !IsReadable(candidate, environmentSize))
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
        if (!ResolveUniqueConsoleStorage(image, anchorConsoleStorage)
            || anchorConsoleStorage != expectedConsoleStorage)
            return false;
    } else if (profile.environmentLocator
        == EnvironmentLocatorStrategy::AnchorDerivedEnvironment) {
        if (anchorConsoleStorage != expectedConsoleStorage)
            return false;
    }

    environmentBase = candidate;
    return true;
}
'''
text = text[:start] + new_resolver + text[end:]
PROFILE.write_text(text, encoding="utf-8")

# --- bootstrap ----------------------------------------------------------------------
text = NATIVE.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''HMODULE g_profileWhGame{};\nconst kcd2::runtime::BuildProfile* g_activeBuildProfile{};\n''',
    '''HMODULE g_profileWhGame{};\nkcd2::runtime::BuildProfile g_compatibilityFallbackProfile{};\nconst kcd2::runtime::BuildProfile* g_activeBuildProfile{};\n''',
    "fallback profile storage")
text = replace_once(
    text,
    '''    const auto* profile = kcd2::runtime::MatchSupportedBuild(identity);\n    if (!profile) {\n        Log("unsupported WHGame build; Clean Pause disabled; no hooks installed");\n        return 0;\n    }\n''',
    '''    const auto* profile = kcd2::runtime::MatchSupportedBuild(identity);\n    bool compatibilityFallback{};\n    if (!profile) {\n        if (!kcd2::runtime::BuildCompatibleRelease15Fallback(\n                identity, g_compatibilityFallbackProfile)) {\n            Log("unsupported WHGame build/release branch; Clean Pause disabled; no hooks installed");\n            return 0;\n        }\n        profile = &g_compatibilityFallbackProfile;\n        compatibilityFallback = true;\n        Log(\n            "no exact registered build profile; attempting conservative release_1_5 compatibility fallback; framework observer and profile presentation quirks disabled");\n    }\n''',
    "bootstrap fallback selection")
text = replace_once(
    text,
    '''    Log("runtime profile validated for %s; env=%p mainThread=%lu",\n        profile->name,\n        environment.base,\n        static_cast<unsigned long>(environment.mainThreadId));\n''',
    '''    Log("runtime profile validated for %s; env=%p mainThread=%lu%s",\n        profile->name,\n        environment.base,\n        static_cast<unsigned long>(environment.mainThreadId),\n        compatibilityFallback ? " compatibilityFallback=yes" : "");\n''',
    "fallback validation log")
NATIVE.write_text(text, encoding="utf-8")

# --- executable tests ---------------------------------------------------------------
text = TESTS.read_text(encoding="utf-8")
insert_before = "bool TestAmbiguousAnchorFailsClosedForSteam()\n"
idx = text.index(insert_before)
fallback_test = r'''bool TestRelease15CompatibilityFallback()
{
    kcd2::runtime::DetectedBuildIdentity identity{};
    identity.fingerprint = {0x77777777, 0x6000, 0};
    identity.storefront = kcd2::runtime::Storefront::Steam;
    identity.buildCode = "release_1_5-99999";

    CHECK(kcd2::runtime::MatchSupportedBuild(identity) == nullptr);

    kcd2::runtime::BuildProfile fallback{};
    CHECK(kcd2::runtime::BuildCompatibleRelease15Fallback(identity, fallback));
    CHECK(fallback.identityStrategy
        == kcd2::runtime::BuildIdentityStrategy::CompatibleReleaseBranch);
    CHECK(fallback.environmentLocator
        == kcd2::runtime::EnvironmentLocatorStrategy::AnchorDerivedEnvironment);
    CHECK(fallback.expectedEnvironmentRva == 0);
    CHECK(fallback.frameworkLocator == kcd2::runtime::FrameworkLocatorStrategy::None);
    CHECK(fallback.expectedFrameworkRva == 0);
    CHECK(fallback.expectedFrameworkVtableRva == 0);
    CHECK(!fallback.capabilities.deferPauseBarrierUntilPauseInput);
    CHECK(!fallback.capabilities.pinHudRootDuringPause);
    CHECK(!fallback.capabilities.prehideMenuDuringPauseTransition);
    CHECK(fallback.abi == &kcd2::runtime::Release15AbiProfile());
    CHECK(fallback.validation == kcd2::runtime::BuildValidationLevel::CompatibilityFallback);

    SyntheticWhGame image;
    CHECK(image.valid());
    std::uint8_t* environment{};
    CHECK(kcd2::runtime::ResolveProfileEnvironmentBase(
        image.module(), fallback, environment));
    CHECK(environment == image.environment());

    image.AddAmbiguousConsoleReference();
    environment = reinterpret_cast<std::uint8_t*>(1);
    CHECK(!kcd2::runtime::ResolveProfileEnvironmentBase(
        image.module(), fallback, environment));
    CHECK(environment == nullptr);

    identity.buildCode = "release_1_6-10000";
    CHECK(!kcd2::runtime::BuildCompatibleRelease15Fallback(identity, fallback));
    identity.buildCode = "release_1_5-";
    CHECK(!kcd2::runtime::BuildCompatibleRelease15Fallback(identity, fallback));
    identity.buildCode.clear();
    CHECK(!kcd2::runtime::BuildCompatibleRelease15Fallback(identity, fallback));
    return true;
}

'''
text = text[:idx] + fallback_test + text[idx:]
text = replace_once(
    text,
    '''    if (!TestAmbiguousAnchorFailsClosedForSteam())\n        return 8;\n\n    std::puts("runtime profile tests passed");\n''',
    '''    if (!TestRelease15CompatibilityFallback())\n        return 8;\n    if (!TestAmbiguousAnchorFailsClosedForSteam())\n        return 9;\n\n    std::puts("runtime profile tests passed");\n''',
    "runtime fallback test registration")
TESTS.write_text(text, encoding="utf-8")

# --- source contracts ---------------------------------------------------------------
text = PYTEST.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        self.assertIn("EnvironmentLocatorStrategy::ExactEnvironmentRva", PROFILE)\n        self.assertIn("EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation", PROFILE)\n''',
    '''        self.assertIn("EnvironmentLocatorStrategy::ExactEnvironmentRva", PROFILE)\n        self.assertIn("EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation", PROFILE)\n        self.assertIn("EnvironmentLocatorStrategy::AnchorDerivedEnvironment", PROFILE)\n''',
    "profile locator contract")
marker = "    def test_unknown_build_is_rejected_before_abi_or_runtime_discovery(self):\n"
if marker in text:
    start = text.index(marker)
    end = text.index("\n    def ", start + len(marker))
    replacement = '''    def test_unknown_build_uses_only_conservative_release15_fallback(self):\n        marker = "DWORD WINAPI BootstrapThread(void*)"\n        bootstrap = RUNTIME[RUNTIME.index(marker):]\n        exact = bootstrap.index("MatchSupportedBuild")\n        fallback = bootstrap.index("BuildCompatibleRelease15Fallback")\n        abi_gate = bootstrap.index("MatureRuntimeSupports")\n        resolve = bootstrap.index("ResolveProfileEnvironmentBase")\n        install = bootstrap.index("InstallInputHook")\n        self.assertLess(exact, fallback)\n        self.assertLess(fallback, abi_gate)\n        self.assertLess(abi_gate, resolve)\n        self.assertLess(resolve, install)\n        self.assertIn("unsupported WHGame build/release branch", bootstrap)\n        self.assertIn("conservative release_1_5 compatibility fallback", bootstrap)\n        self.assertIn("FrameworkLocatorStrategy::None", PROFILE)\n        self.assertIn("BuildValidationLevel::CompatibilityFallback", PROFILE_H)\n        self.assertIn("AnchorDerivedEnvironment", PROFILE_H)\n\n'''
    text = text[:start] + replacement + text[end + 1:]
else:
    raise RuntimeError("unknown build source-contract test marker not found")
PYTEST.write_text(text, encoding="utf-8")

text = CHECKER.read_text(encoding="utf-8")
# Exact unknown-build rejection was intentionally replaced by a narrow release_1_5 fallback.
if "unsupported WHGame build; Clean Pause disabled; no hooks installed" in text:
    text = text.replace(
        "unsupported WHGame build; Clean Pause disabled; no hooks installed",
        "unsupported WHGame build/release branch; Clean Pause disabled; no hooks installed")
CHECKER.write_text(text, encoding="utf-8")

print("release_1_5 compatibility fallback added")
