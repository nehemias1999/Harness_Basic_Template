"""Tests for scripts/validate_project_setup.py.

What matters most here is the conditional rule: an unapproved architecture only
blocks once there is work outside `draft`. If that breaks, either the analysis
phase runs red (and red stops meaning anything), or people program without any
quality criteria.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_project_setup as vps  # noqa: E402


ARCHITECTURE_READY = """# Architecture

## Principles

1. Clear layers: cli, domain, storage.
2. No external dependencies.
"""

ARCHITECTURE_DRAFT = """# Architecture

> **This file is a template: fill it in before writing the first feature.**

## Principles

1. Clear layers.
"""

ARCHITECTURE_WITH_HOLES = """# Architecture

## Principles

1. Layers: <module_1>, <module_2>.
"""


class ProjectSetupCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "docs"))
        os.makedirs(os.path.join(self.root, "src"))
        os.makedirs(os.path.join(self.root, "features"))
        self.write("README.md", "# my-project\n\n> Does something.\n")
        self.write("docs/architecture.md", ARCHITECTURE_READY)
        self.project("my-project")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, rel: str, content: str) -> None:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    def project(self, name: str, desc: str = "Does something.") -> None:
        self.write(
            "features/_project.md",
            f"---\nproject: {name}\ndescription: {desc}\n---\n",
        )

    def write_feature_note(self, status: str = "draft") -> None:
        content = (
            "---\n"
            "title: A feature\n"
            "description: What it does.\n"
            'spec: "[[REQ-001_a_requirement]]"\n'
            "priority: medium\n"
            "acceptance:\n"
            '  - "something verifiable"\n'
            f"status: {status}\n"
            "---\n"
        )
        self.write("features/F-001_a_feature.md", content)

    def check(self):
        return vps.check(self.root)


class TestConditionalArchitecture(ProjectSetupCase):
    def test_draft_with_everything_in_draft_only_warns(self) -> None:
        self.write("docs/architecture.md", ARCHITECTURE_DRAFT)
        self.write_feature_note("draft")
        fails, warns, _ = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("unapproved draft" in w for w in warns), warns)

    def test_draft_with_one_feature_outside_draft_blocks(self) -> None:
        self.write("docs/architecture.md", ARCHITECTURE_DRAFT)
        self.write_feature_note("pending")
        fails, _warns, _ = self.check()
        self.assertTrue(any("unfilled template" in f for f in fails), fails)

    def test_placeholders_with_work_started_block(self) -> None:
        self.write("docs/architecture.md", ARCHITECTURE_WITH_HOLES)
        self.write_feature_note("in_progress")
        fails, _warns, _ = self.check()
        self.assertTrue(any("placeholders" in f for f in fails), fails)

    def test_a_ready_architecture_says_nothing(self) -> None:
        self.write_feature_note("done")
        fails, warns, _ = self.check()
        self.assertEqual(fails, [])
        self.assertFalse([w for w in warns if "architecture" in w], warns)


class TestProjectPlaceholders(ProjectSetupCase):
    def test_unset_project_blocks(self) -> None:
        self.project("<YOUR_PROJECT>")
        fails, _warns, _ = self.check()
        self.assertTrue(any('"project" is still unset' in f for f in fails), fails)

    def test_readme_with_placeholder_blocks(self) -> None:
        self.write("README.md", "# <YOUR_PROJECT>\n")
        fails, _warns, _ = self.check()
        self.assertTrue(any("README.md still contains" in f for f in fails), fails)


class TestUninstantiatedTemplate(ProjectSetupCase):
    def test_the_pristine_repo_is_detected(self) -> None:
        self.project("<YOUR_PROJECT>")
        self.write("docs/architecture.md", ARCHITECTURE_DRAFT)
        self.write("README.md", "# <YOUR_PROJECT>\n\n> <PROJECT_DESCRIPTION>\n")
        _fails, _warns, pristine = self.check()
        self.assertTrue(pristine)

    def test_a_half_configured_project_is_not_pristine(self) -> None:
        # With the name set it is no longer the template: the concrete failures
        # are what matter, not the "run bootstrap" message.
        self.write("docs/architecture.md", ARCHITECTURE_DRAFT)
        _fails, _warns, pristine = self.check()
        self.assertFalse(pristine)


if __name__ == "__main__":
    unittest.main()