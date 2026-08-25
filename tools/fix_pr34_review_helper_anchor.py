from pathlib import Path

path = Path(__file__).with_name("apply_pr34_review_corrections.py")
text = path.read_text(encoding="utf-8")
old = "'#include <windows.h>\\n\\nnamespace clean_pause {'"
new = "'#include <string>\\n\\nnamespace clean_pause {'"
old_replacement = "'#include <windows.h>\\n\\n#ifndef CLEAN_PAUSE_VERSION\\n#define CLEAN_PAUSE_VERSION \"unknown\"\\n#endif\\n#ifndef CLEAN_PAUSE_BUILD_ID\\n#define CLEAN_PAUSE_BUILD_ID \"unknown\"\\n#endif\\n\\nnamespace clean_pause {'"
new_replacement = "'#include <string>\\n\\n#ifndef CLEAN_PAUSE_VERSION\\n#define CLEAN_PAUSE_VERSION \"unknown\"\\n#endif\\n#ifndef CLEAN_PAUSE_BUILD_ID\\n#define CLEAN_PAUSE_BUILD_ID \"unknown\"\\n#endif\\n\\nnamespace clean_pause {'"
if text.count(old) != 1 or text.count(old_replacement) != 1:
    raise SystemExit("review helper guard shape changed")
text = text.replace(old, new, 1).replace(old_replacement, new_replacement, 1)
path.write_text(text, encoding="utf-8")
