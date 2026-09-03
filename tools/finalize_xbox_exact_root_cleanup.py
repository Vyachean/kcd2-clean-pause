#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

runtime_path = ROOT / "native/src/clean_pause_native.cpp"
runtime = runtime_path.read_text(encoding="utf-8")
start = runtime.index("bool ValidateEnvironmentCandidate")
end = runtime.index("bool ResolveMenuElement", start)
runtime = runtime[:start] + runtime[end:]
runtime_path.write_text(runtime, encoding="utf-8")

test_path = ROOT / "tests/test_runtime_profile_contract.py"
test = test_path.read_text(encoding="utf-8")
test = test.replace(
    '        self.assertIn("switch (profile.environmentLocator)", RUNTIME)\n',
    '        self.assertIn("ResolveProfileEnvironmentBase", RUNTIME)\n'
    '        self.assertNotIn("LegacyXbox156ValidatedScan", PROFILE_H)\n',
    1,
)
test = test.replace(
    '            RUNTIME.index("bool ResolveProfileFrameworkSingleton")\n',
    '            RUNTIME.index("bool ResolveProfileFramework")\n',
    1,
)
test_path.write_text(test, encoding="utf-8")

print("removed final legacy environment helper and refreshed contracts")
