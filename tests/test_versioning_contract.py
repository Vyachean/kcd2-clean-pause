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

    def test_release_publication_is_tag_backed_and_automatic_on_main(self):
        self.assertIn("github.event_name == 'push'", RELEASE)
        self.assertIn("github.ref == 'refs/heads/main'", RELEASE)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", RELEASE)
        self.assertIn('git tag "$TAG" "$GITHUB_SHA"', RELEASE)
        self.assertIn('git push origin "refs/tags/$TAG"', RELEASE)
        self.assertIn("--verify-tag", RELEASE)
        self.assertIn("Release $TAG already exists; leaving it unchanged.", RELEASE)
        self.assertNotIn('args+=(--target "$GITHUB_SHA")', RELEASE)

    def test_docs_define_semver_and_unreleased_flow(self):
        self.assertIn("Semantic Versioning", RELEASE_DOC)
        self.assertIn("features increment **MINOR**", RELEASE_DOC)
        self.assertIn("fixes increment **PATCH**", RELEASE_DOC)
        self.assertIn("It is not incremented for every merged PR", RELEASE_DOC)
        self.assertIn("automatically creates the exact `v<VERSION>` tag", RELEASE_DOC)
        self.assertIn("## Unreleased", CHANGELOG)


if __name__ == "__main__":
    unittest.main()
