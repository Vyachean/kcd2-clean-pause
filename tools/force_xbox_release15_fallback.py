#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "native/src/clean_pause_native.cpp"
text = path.read_text(encoding="utf-8")
old = '''    const auto* profile = kcd2::runtime::MatchSupportedBuild(identity);\n    bool compatibilityFallback{};\n'''
new = '''    const auto* profile = kcd2::runtime::MatchSupportedBuild(identity);\n    // Diagnostic-only proof for the currently captured Xbox / Microsoft Store\n    // 1.5.6 binary. Force the production compatibility fallback instead of the\n    // exact profile so the anchor-derived gEnv resolver is exercised on retail.\n    const bool forceXboxCompatibilityFallback =\n        identity.fingerprint.timestamp == 0x6a391f7b\n        && identity.fingerprint.imageSize == 0x05bf2000\n        && identity.fingerprint.checksum == 0;\n    if (forceXboxCompatibilityFallback) {\n        Log("DIAGNOSTIC: forcing release_1_5 compatibility fallback for exact Xbox 1.5.6 fingerprint");\n        profile = nullptr;\n    }\n    bool compatibilityFallback{};\n'''
if old not in text:
    raise RuntimeError("bootstrap profile selection marker not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("forced Xbox compatibility fallback diagnostic added")
