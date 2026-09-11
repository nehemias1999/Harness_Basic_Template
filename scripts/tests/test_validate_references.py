"""Tests for scripts/validate_references.py.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_references as vref  # noqa: E402


class ReferencesCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "docs"))
        os.makedirs(os.path.join(self.root, "scripts"))
        for document in vref.DOCUMENTS:
            self.write(document, "# empty\n")
        self.write("feature_list.json", json.dumps({"features": []}))

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
        self.write(
            "feature_list.json",
            json.dumps({"features": [{"id": 1, "spec": "specs/REQ-001_x.md"}]}),
        )
        failures = self.check()
        self.assertTrue(any("REQ-001_x.md" in f for f in failures), failures)

    def test_valid_spec_pointer(self) -> None:
        self.write("specs/REQ-001_x.md", "---\nid: REQ-001\n---\n")
        self.write(
            "feature_list.json",
            json.dumps({"features": [{"id": 1, "spec": "specs/REQ-001_x.md"}]}),
        )
        self.assertEqual(self.check(), [])

    def test_unreadable_feature_list_does_not_explode(self) -> None:
        self.write("feature_list.json", "{ broken")
        self.assertEqual(self.check(), [])


class TestTheRealRepo(unittest.TestCase):
    def test_this_repository_has_no_dangling_references(self) -> None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertEqual(vref.check(root), [])


if __name__ == "__main__":
    unittest.main()
