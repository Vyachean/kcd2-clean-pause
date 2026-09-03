#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "native/src/clean_pause_native.cpp"
TEST = ROOT / "tests/test_runtime_profile_contract.py"

runtime = RUNTIME.read_text(encoding="utf-8")

# The runtime-tested Xbox 1.5.6 path never called IGame/GetFramework identity
# methods from the bootstrap worker before installing the shared input runtime.
# Exact PE fingerprint + the legacy validated environment scan are the accepted
# bootstrap boundary; framework identity remains verified separately before the
# optional PauseGame observer is installed.
start = runtime.index("bool ThreadBelongsToCurrentProcess(DWORD threadId)\n{")
end = runtime.index("// Exact-profile readiness deliberately validates only capabilities required for")
runtime = runtime[:start] + runtime[end:]

old = '''    case kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan:\n        if (!LegacyFindRuntimeEnvironment_Xbox156Only(whGame, candidate)) {\n            failureReason = "xbox-runtime-not-ready";\n            return false;\n        }\n        observedCandidate = candidate;\n        if (!StronglyValidateEnvironment(candidate, result)) {\n            failureReason = "xbox-runtime-identity";\n            return false;\n        }\n        return true;\n'''
new = '''    case kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan:\n        // Preserve the runtime-tested Xbox bootstrap boundary: the exact Xbox PE\n        // fingerprint has already selected this adapter, and the legacy scanner\n        // validates the complete SSystemGlobalEnvironment interface shape. Do not\n        // call engine virtuals such as IGame::GetName()/IGame[16] from this worker\n        // thread. The optional framework identity is verified later, immediately\n        // before its PauseGame observer is installed.\n        if (!LegacyFindRuntimeEnvironment_Xbox156Only(whGame, result)) {\n            failureReason = "xbox-runtime-not-ready";\n            return false;\n        }\n        observedCandidate = result;\n        Log("Xbox legacy runtime environment discovered; env=%p mainThread=%lu",\n            result.base,\n            static_cast<unsigned long>(result.mainThreadId));\n        return true;\n'''
if old not in runtime:
    raise RuntimeError("Xbox PollRuntimeEnvironment block did not match expected source")
runtime = runtime.replace(old, new, 1)

for dead in (
    "ThreadBelongsToCurrentProcess",
    "ValidateLegacyXboxGameAndFrameworkIdentity",
    "StronglyValidateEnvironment",
):
    if dead in runtime:
        raise RuntimeError(f"pre-runtime Xbox worker-thread identity call survived: {dead}")

RUNTIME.write_text(runtime, encoding="utf-8")

test = TEST.read_text(encoding="utf-8")
old_test = '''    def test_xbox_legacy_discovery_is_locator_scoped(self):\n        self.assertIn("LegacyFindRuntimeEnvironment_Xbox156Only", RUNTIME)\n        self.assertIn("EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan", RUNTIME)\n        self.assertIn("StronglyValidateEnvironment", RUNTIME)\n        self.assertIn("ValidateLegacyXboxGameAndFrameworkIdentity", RUNTIME)\n        self.assertIn("src/clean_pause_native.cpp", CMAKE)\n        self.assertNotIn("src/clean_pause_native_profiled.cpp", CMAKE)\n        self.assertIn("for (std::size_t offset = 0; offset <= limit", RUNTIME)\n'''
new_test = '''    def test_xbox_legacy_discovery_is_locator_scoped(self):\n        self.assertIn("LegacyFindRuntimeEnvironment_Xbox156Only", RUNTIME)\n        self.assertIn("EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan", RUNTIME)\n        self.assertIn("src/clean_pause_native.cpp", CMAKE)\n        self.assertNotIn("src/clean_pause_native_profiled.cpp", CMAKE)\n        self.assertIn("for (std::size_t offset = 0; offset <= limit", RUNTIME)\n\n        legacy = RUNTIME[\n            RUNTIME.index("case kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan"):\n            RUNTIME.index("case kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRva")\n        ]\n        self.assertIn("LegacyFindRuntimeEnvironment_Xbox156Only(whGame, result)", legacy)\n        self.assertIn("observedCandidate = result;", legacy)\n        self.assertNotIn("StronglyValidateEnvironment", legacy)\n        self.assertNotIn("ValidateLegacyXboxGameAndFrameworkIdentity", RUNTIME)\n        self.assertNotIn("ThreadBelongsToCurrentProcess", RUNTIME)\n        self.assertIn("Xbox legacy runtime environment discovered", legacy)\n'''
if old_test not in test:
    raise RuntimeError("Xbox runtime profile contract block did not match expected source")
test = test.replace(old_test, new_test, 1)
TEST.write_text(test, encoding="utf-8")

print("restored runtime-tested Xbox bootstrap boundary")
