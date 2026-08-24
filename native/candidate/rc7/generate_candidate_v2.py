from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: generate_candidate_v2.py <input.cpp> <output.cpp>")

source_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
source = source_path.read_text(encoding="utf-8")

replacements = [
    (
        "std::atomic_bool g_renderSuppressionObserved{false};\nstd::atomic_bool g_swallowPauseRelease{false};",
        "std::atomic_bool g_renderSuppressionObserved{false};\nstd::atomic_ullong g_cleanHiddenSinceMs{0};\nstd::atomic_bool g_swallowPauseRelease{false};",
    ),
    (
        "constexpr ULONGLONG kPendingWindowMs = 750;\nconstexpr std::size_t kUIElementRenderSlot = 24;",
        "constexpr ULONGLONG kPendingWindowMs = 750;\nconstexpr ULONGLONG kRenderObservationGraceMs = 250;\nconstexpr std::size_t kUIElementRenderSlot = 24;",
    ),
    (
        "    g_cleanHidden.store(false, std::memory_order_release);\n    g_renderSuppressionObserved.store(false, std::memory_order_release);\n    g_swallowPauseRelease.store(false, std::memory_order_release);",
        "    g_cleanHidden.store(false, std::memory_order_release);\n    g_renderSuppressionObserved.store(false, std::memory_order_release);\n    g_cleanHiddenSinceMs.store(0, std::memory_order_release);\n    g_swallowPauseRelease.store(false, std::memory_order_release);",
    ),
    (
        "    g_renderSuppressionObserved.store(false, std::memory_order_release);\n    g_cleanHidden.store(true, std::memory_order_release);",
        "    g_renderSuppressionObserved.store(false, std::memory_order_release);\n    g_cleanHiddenSinceMs.store(GetTickCount64(), std::memory_order_release);\n    g_cleanHidden.store(true, std::memory_order_release);",
    ),
    (
        "    if (!g_renderSuppressionObserved.load(std::memory_order_acquire)) {\n        ClearHiddenState(\"Render suppression was not observed before next physical input; fail-open\");\n        Forward(input, event, force);\n        return;\n    }",
        "    if (!g_renderSuppressionObserved.load(std::memory_order_acquire)) {\n        const ULONGLONG enteredAt = g_cleanHiddenSinceMs.load(std::memory_order_acquire);\n        const ULONGLONG now = GetTickCount64();\n        if (enteredAt != 0 && now - enteredAt > kRenderObservationGraceMs) {\n            ClearHiddenState(\"Render suppression was not observed within 250 ms; fail-open\");\n            Forward(input, event, force);\n            return;\n        }\n    }",
    ),
]

for old, new in replacements:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one source match, got {count}: {old[:80]!r}")
    source = source.replace(old, new, 1)

required = (
    "kRenderObservationGraceMs = 250",
    "g_cleanHiddenSinceMs.store(GetTickCount64()",
    "Render suppression was not observed within 250 ms; fail-open",
)
for needle in required:
    if needle not in source:
        raise SystemExit(f"generated rc7b source missing: {needle}")

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(source, encoding="utf-8")
print(f"generated {out_path}")
