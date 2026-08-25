from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: stale-test anchor mismatch")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(
    "tests/test_hud_mask_transaction_contract.py",
    "        self.assertLess(ensure.index('g_maskObject.store'), ensure.index('g_observer.store'))\n"
    "        self.assertLess(ensure.index('g_sourceMonitorObject.store'), ensure.index('g_observer.store'))\n",
    "        # Cached reuse may update the observer before the initial-publication block.\n"
    "        # The first installation must still publish both concrete identities before\n"
    "        # the final observer publication that makes new detours active.\n"
    "        self.assertLess(ensure.index('g_maskObject.store'), ensure.rindex('g_observer.store'))\n"
    "        self.assertLess(ensure.index('g_sourceMonitorObject.store'), ensure.rindex('g_observer.store'))\n",
)

replace_once(
    "tools/validate_native_contract.py",
    "if ensure_mask.index(\"g_maskObject.store\") > ensure_mask.index(\"g_observer.store\"):\n"
    "    raise SystemExit(\"target HUD-mask identity must be published before mutation observer\")\n"
    "if ensure_mask.index(\"g_sourceMonitorObject.store\") > ensure_mask.index(\"g_observer.store\"):\n"
    "    raise SystemExit(\"target source-monitor identity must be published before mutation observer\")\n",
    "if ensure_mask.index(\"g_maskObject.store\") > ensure_mask.rindex(\"g_observer.store\"):\n"
    "    raise SystemExit(\"target HUD-mask identity must be published before initial mutation observer activation\")\n"
    "if ensure_mask.index(\"g_sourceMonitorObject.store\") > ensure_mask.rindex(\"g_observer.store\"):\n"
    "    raise SystemExit(\"target source-monitor identity must be published before initial mutation observer activation\")\n",
)

Path(__file__).unlink()
print("cached-mask assertion correction applied")
