#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tests/test_pause_barrier_contract.py"
CHECKER = ROOT / "tools/validate_native_contract.py"

test = TEST.read_text(encoding="utf-8")
old = '        self.assertIn("frameworkSystem == environment.system", xbox)\n'
new = '''        self.assertIn("frameworkSystem != environment.system", xbox)
        self.assertIn("return false;", xbox[xbox.index("frameworkSystem != environment.system"):])
        self.assertIn("LogLegacyXboxFrameworkRootEvidence", xbox)
        self.assertLess(
            xbox.index("frameworkSystem != environment.system"),
            xbox.index("LogLegacyXboxFrameworkRootEvidence"),
        )
'''
if old not in test:
    raise RuntimeError("Xbox test identity assertion not found")
test = test.replace(old, new, 1)
TEST.write_text(test, encoding="utf-8")

checker = CHECKER.read_text(encoding="utf-8")
old_checker = '''for needle in (
    "kGameGetFrameworkSlot",
    "kGameFrameworkGetSystemSlot",
    "frameworkSystem == environment.system",
):
    if needle not in xbox_resolver:
        raise SystemExit(f"Xbox framework identity adapter contract missing: {needle}")
'''
new_checker = '''for needle in (
    "kGameGetFrameworkSlot",
    "kGameFrameworkGetSystemSlot",
    "frameworkSystem != environment.system",
):
    if needle not in xbox_resolver:
        raise SystemExit(f"Xbox framework identity adapter contract missing: {needle}")
identity_gate = xbox_resolver.index("frameworkSystem != environment.system")
if "return false;" not in xbox_resolver[identity_gate:]:
    raise SystemExit("Xbox framework identity mismatch must fail closed")
if "LogLegacyXboxFrameworkRootEvidence" in xbox_resolver:
    if identity_gate > xbox_resolver.index("LogLegacyXboxFrameworkRootEvidence"):
        raise SystemExit("Xbox diagnostic root logging must happen only after framework identity proof")
'''
if old_checker not in checker:
    raise RuntimeError("Xbox stable checker identity block not found")
checker = checker.replace(old_checker, new_checker, 1)
CHECKER.write_text(checker, encoding="utf-8")

print("Xbox diagnostic contracts updated")
