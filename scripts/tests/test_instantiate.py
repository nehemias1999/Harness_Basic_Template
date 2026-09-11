"""Tests for scripts/instantiate.py.

Bootstrapping is the most destructive script in the harness: it empties the
scope, deletes the requirements and can delete `.git`. What matters most to
cover is that it **refuses** when the repository is already a project, and that
the dry run writes nothing.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instantiate  # noqa: E402


TEMPLATE_FEATURE_LIST = {
    "project": "<YOUR_PROJECT>",
    "description": "<One line describing what the project does.>",
    "rules": {"one_feature_at_a_time": True},
    "features": [{"id": 1, "name": "inherited", "status": "done"}],
}


class InstantiateCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        for folder in ("progress", "docs", "specs"):
            os.makedirs(os.path.join(self.root, folder))
        self.write("feature_list.json", json.dumps(TEMPLATE_FEATURE_LIST, ensure_ascii=False))
        self.write("README.md", "# <YOUR_PROJECT>\n\n> <PROJECT_DESCRIPTION>\n")
        self.write("docs/architecture.md", "# Architecture of <YOUR_PROJECT>\n")
        self.write("progress/current.md", "# Current session\n\njunk from the last session\n")
        self.write("progress/history.md", "# Session history\n\n---\n\n_No sessions._\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------
    def write(self, rel: str, content: str) -> None:
        with open(os.path.join(self.root, rel), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    def read(self, rel: str) -> str:
        with open(os.path.join(self.root, rel), encoding="utf-8") as handle:
            return handle.read()

    def exists(self, rel: str) -> bool:
        return os.path.exists(os.path.join(self.root, rel))

    def run_it(self, **kwargs) -> tuple[int, str]:
        options = {
            "name": "my-project",
            "description": "Does something.",
            "force": False,
            "reset_git": False,
            "no_git": True,
            "dry_run": False,
        }
        options.update(kwargs)
        args = argparse.Namespace(**options)
        output = io.StringIO()
        with redirect_stdout(output):
            code = instantiate.Instantiator(self.root, args).run()
        return code, output.getvalue()


class TestInstantiation(InstantiateCase):
    def test_the_happy_path(self) -> None:
        code, _output = self.run_it()
        self.assertEqual(code, 0)

        data = json.loads(self.read("feature_list.json"))
        self.assertEqual(data["project"], "my-project")
        self.assertEqual(data["description"], "Does something.")
        self.assertEqual(data["features"], [])
        self.assertIn("my-project", self.read("README.md"))
        self.assertNotIn("<YOUR_PROJECT>", self.read("README.md"))
        self.assertIn("Feature in progress", self.read("progress/current.md"))

    def test_without_a_description_the_placeholder_stays(self) -> None:
        self.run_it(description="")
        self.assertIn("<PROJECT_DESCRIPTION>", self.read("README.md"))

    def test_a_template_file_is_missing(self) -> None:
        os.remove(os.path.join(self.root, "progress", "history.md"))
        code, output = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("A template file is missing", output)


class TestDoNotDestroyALiveProject(InstantiateCase):
    """The guardrail that matters."""

    def test_it_refuses_if_it_already_has_a_name(self) -> None:
        data = json.loads(self.read("feature_list.json"))
        data["project"] = "live-project"
        self.write("feature_list.json", json.dumps(data, ensure_ascii=False))

        code, output = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("already an instantiated project", output)
        # And it touched nothing.
        self.assertEqual(json.loads(self.read("feature_list.json"))["project"], "live-project")

    def test_it_refuses_if_there_are_requirements(self) -> None:
        self.write("specs/REQ-001_something.md", "---\nid: REQ-001\n---\n")
        code, output = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("1 requirement(s) in specs/", output)
        self.assertTrue(self.exists("specs/REQ-001_something.md"))

    def test_with_force_it_goes_ahead(self) -> None:
        self.write("specs/REQ-001_something.md", "---\nid: REQ-001\n---\n")
        code, _output = self.run_it(force=True)
        self.assertEqual(code, 0)
        self.assertFalse(self.exists("specs/REQ-001_something.md"))

    def test_a_history_with_entries_is_not_overwritten_without_force(self) -> None:
        self.write(
            "progress/history.md",
            "# History\n\n---\n\n## 2026-01-01 — feature 1 something\n\n- Result: done\n",
        )
        _code, output = self.run_it()
        self.assertIn("has entries from previous sessions", output)
        self.assertIn("2026-01-01", self.read("progress/history.md"))


class TestDryRun(InstantiateCase):
    def test_dry_run_writes_nothing(self) -> None:
        before = self.read("feature_list.json")
        self.write("specs/REQ-001_something.md", "---\nid: REQ-001\n---\n")

        code, output = self.run_it(dry_run=True, force=True)
        self.assertEqual(code, 0)
        self.assertIn("simulated", output)
        self.assertEqual(self.read("feature_list.json"), before)
        self.assertTrue(self.exists("specs/REQ-001_something.md"))


class TestCleanup(InstantiateCase):
    def test_it_deletes_the_previous_session_reports(self) -> None:
        for name in ("impl_something.md", "review_something.md", "explore_x.md", "intake_r1.md"):
            self.write(f"progress/{name}", "old report\n")
        self.write("progress/my_notes.md", "this is not a report\n")

        self.run_it()

        for name in ("impl_something.md", "review_something.md", "explore_x.md", "intake_r1.md"):
            self.assertFalse(self.exists(f"progress/{name}"), name)
        self.assertTrue(self.exists("progress/my_notes.md"))

    def test_it_creates_specs_if_it_does_not_exist(self) -> None:
        os.rmdir(os.path.join(self.root, "specs"))
        self.run_it()
        self.assertTrue(os.path.isdir(os.path.join(self.root, "specs")))

    def test_it_keeps_the_specs_template(self) -> None:
        self.write("specs/_req_template.md", "template\n")
        self.run_it()
        self.assertTrue(self.exists("specs/_req_template.md"))


if __name__ == "__main__":
    unittest.main()
