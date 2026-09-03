#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

path = ROOT / "native/src/kcd2_abi.h"
text = path.read_text(encoding="utf-8")
old = '''// Legacy compatibility name retained because the runtime-tested Xbox path uses
// IGame[16] this way. Public Steam 1.5.6 RE identifies slot 16 as a different
// engine-root accessor, so profiled non-Xbox builds must not use it to obtain
// IGameFramework. Their framework capability is resolved independently.
inline constexpr std::size_t kGameGetFrameworkSlot = 16;
'''
if old not in text:
    raise RuntimeError("legacy IGame framework ABI constant block not found")
text = text.replace(old, "", 1)
text = text.replace("using GetGameFrameworkFn = void*(__fastcall*)(void*);\n", "", 1)
path.write_text(text, encoding="utf-8")

path = ROOT / "native/src/kcd2_abi_profile.h"
text = path.read_text(encoding="utf-8")
needle = "    std::size_t gameGetFramework{};\n"
if needle not in text:
    raise RuntimeError("gameGetFramework ABI profile field not found")
text = text.replace(needle, "", 1)
path.write_text(text, encoding="utf-8")

path = ROOT / "native/src/kcd2_abi_profile.cpp"
text = path.read_text(encoding="utf-8")
text = text.replace("        16, // IGame::GetIGameFramework\n", "", 1)
text = text.replace("        || slots.gameGetFramework != kGameGetFrameworkSlot\n", "", 1)
path.write_text(text, encoding="utf-8")

path = ROOT / "tests/test_pause_barrier_contract.py"
text = path.read_text(encoding="utf-8")
text = text.replace('            "kGameGetFrameworkSlot = 16",\n', "", 1)
text = text.replace(
    '        self.assertNotIn("kGameGetFrameworkSlot", resolver)\n',
    '        self.assertNotIn("kGameGetFrameworkSlot", ABI)\n'
    '        self.assertNotIn("GetGameFrameworkFn", ABI)\n'
    '        self.assertNotIn("kGameGetFrameworkSlot", resolver)\n',
    1,
)
path.write_text(text, encoding="utf-8")

path = ROOT / "tools/validate_native_contract.py"
text = path.read_text(encoding="utf-8")
text = text.replace('    "kGameGetFrameworkSlot = 16",\n', "", 1)
anchor = 'for needle in required_abi:\n    if needle not in abi:\n        raise SystemExit(f"missing verified ABI contract: {needle}")\n'
replacement = anchor + '\nif "kGameGetFrameworkSlot" in abi or "GetGameFrameworkFn" in abi:\n    raise SystemExit("legacy IGame[16] framework ABI must not remain in production")\n'
if anchor not in text:
    raise RuntimeError("required ABI checker anchor not found")
text = text.replace(anchor, replacement, 1)
path.write_text(text, encoding="utf-8")

print("removed legacy IGame[16] framework ABI surface")
