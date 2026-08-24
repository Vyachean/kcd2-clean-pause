from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: generate_candidate_v6.py <input.cpp> <output.cpp>")

v5 = Path(__file__).with_name("generate_candidate_v5.py")
source = v5.read_text(encoding="utf-8")

# v5 already has a complete final forbidden-symbol check after every transformation.
# Its earlier check runs before TryEnterCleanPause is transformed and therefore sees
# the expected rc7e g_hudSnapshotCaptured symbol. Remove only that premature check;
# the stricter final check remains untouched and is also repeated by CI over the
# generated C++ that MSVC compiles.
premature = '''if "ReleaseHudClipSnapshot" in source or "g_hudClipSnapshot" in source or "g_hudSnapshotCaptured" in source:\n    raise SystemExit("rc7f retained an rc7e long-lived wrapper symbol")\n'''
if source.count(premature) != 1:
    raise SystemExit("rc7f wrapper expected exactly one premature legacy-symbol check")
source = source.replace(premature, "", 1)

namespace = {
    "__file__": str(v5),
    "__name__": "__main__",
    "__builtins__": __builtins__,
}
exec(compile(source, str(v5), "exec"), namespace, namespace)
