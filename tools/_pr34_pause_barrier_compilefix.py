from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "native/src/clean_pause_native.cpp"
text = p.read_text(encoding="utf-8")
old = "    Menu visibility path remains the fail-open compatibility behavior.\n"
new = "    // Menu visibility path remains the fail-open compatibility behavior.\n"
if text.count(old) != 1:
    raise SystemExit("compile-fix anchor mismatch")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
Path(__file__).unlink()
print("pause barrier compile correction applied")
