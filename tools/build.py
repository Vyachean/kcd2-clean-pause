#!/usr/bin/env python3

"""Compatibility entry point for the exact-profile builder.

A standalone source-only PAK is intentionally no longer supported: Clean Pause
must patch the target installation's own defaultProfile.xml so it cannot ship an
outdated whole-file keybind override.
"""

from build_from_game import main


if __name__ == "__main__":
    main()
