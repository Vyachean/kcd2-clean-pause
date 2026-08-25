import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
RELEASE_DOC = (ROOT / "docs/RELEASE.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


class VersioningContractTests(unittest.TestCase):
    def test_version_uses_supported_semver_shape(self):
        pattern = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-(alpha|beta|rc)\.[1-9][0-9]*)?$"
        self.assertRegex(VERSION, pattern)

    def test_release_publication_is_tag_driven(self):
        self.assertIn("github.event_name == 'push'", RELEASE)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", RELEASE)
        self.assertIn("Release publication requires an existing tag", RELEASE)
        self.assertIn("--verify-tag", RELEASE)
        self.assertNotIn('args+=(--target "$GITHUB_SHA")', RELEASE)

    def test_docs_define_semver_and_unreleased_flow(self):
        self.assertIn("Semantic Versioning", RELEASE_DOC)
        self.assertIn("features increment **MINOR**", RELEASE_DOC)
        self.assertIn("fixes increment **PATCH**", RELEASE_DOC)
        self.assertIn("It is not incremented for every merged PR", RELEASE_DOC)
        self.assertIn("## Unreleased", CHANGELOG)


if __name__ == "__main__":
    unittest.main()
