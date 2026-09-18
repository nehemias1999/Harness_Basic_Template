"""Tests for scripts/validate_references.py.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_references as vref  # noqa: E402

FEATURE_NOTE = (
    "---\n"
    "title: A feature\n"
    "description: What it does.\n"
    'spec: "[[REQ-001_x]]"\n'
    "priority: medium\n"
    "acceptance:\n"
    '  - "something verifiable"\n'
    "status: pending\n"
    "---\n"
)


class ReferencesCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "docs"))
        os.makedirs(os.path.join(self.root, "scripts"))
        for document in vref.DOCUMENTS:
            self.write(document, "# empty\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, rel: str, content: str) -> None:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    def check(self) -> list[str]:
        return vref.check(self.root)


class TestReferences(ReferencesCase):
    def test_clean_repo(self) -> None:
        self.assertEqual(self.check(), [])

    def test_path_that_does_not_exist(self) -> None:
        self.write("AGENTS.md", "See `scripts/missing.py` for this.\n")
        failures = self.check()
        self.assertTrue(any("scripts/missing.py" in f for f in failures), failures)

    def test_path_that_does_exist(self) -> None:
        self.write("scripts/present.py", "# hi\n")
        self.write("AGENTS.md", "See `scripts/present.py` for this.\n")
        self.assertEqual(self.check(), [])

    def test_a_bare_name_is_an_example_not_a_path(self) -> None:
        # `storage.py` in a naming-conventions table is not a reference:
        # chasing it filled the output with noise.
        self.write("docs/conventions.md", "| Modules | snake_case | `storage.py` |\n")
        self.assertEqual(self.check(), [])

    def test_placeholders_are_ignored(self) -> None:
        self.write("AGENTS.md", "The report goes to `progress/impl_<feature>.md`.\n")
        self.assertEqual(self.check(), [])

    def test_requirements_txt_does_not_count(self) -> None:
        self.write("CHECKPOINTS.md", "- [ ] There is no `requirements.txt` with content.\n")
        self.assertEqual(self.check(), [])

    def test_missing_reference_document(self) -> None:
        os.remove(os.path.join(self.root, "AGENTS.md"))
        failures = self.check()
        self.assertTrue(any("AGENTS.md" in f for f in failures), failures)

    def test_dangling_spec_pointer(self) -> None:
        self.write("features/F-001_a_feature.md", FEATURE_NOTE)
        failures = self.check()
        self.assertTrue(any("REQ-001_x.md" in f for f in failures), failures)
        self.assertTrue(any("points at" in f for f in failures), failures)

    def test_valid_spec_pointer(self) -> None:
        self.write("specs/REQ-001_x.md", "---\nid: REQ-001\n---\n")
        self.write("features/F-001_a_feature.md", FEATURE_NOTE)
        self.assertEqual(self.check(), [])

    def test_a_feature_note_without_front_matter_is_reported_not_swallowed(self) -> None:
        # This used to assert `== []`: the validator returned early and `main`
        # went on to print "[OK] no dangling references" while half the check had
        # not run. Not exploding is the right instinct; staying quiet about it is
        # not. A validator that reports success when it could not look is worse
        # than no validator, because someone trusts it.
        self.write("features/F-001_broken.md", "# just a heading\n")
        failures = self.check()
        self.assertEqual(len(failures), 1)
        self.assertIn("has no front matter", failures[0])


class TestTheRealRepo(unittest.TestCase):
    def test_this_repository_has_no_dangling_references(self) -> None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertEqual(vref.check(root), [])


if __name__ == "__main__":
    unittest.main()