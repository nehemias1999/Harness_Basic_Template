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
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instantiate  # noqa: E402


class InstantiateCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        for folder in ("progress", "docs", "specs", "src", "features"):
            os.makedirs(os.path.join(self.root, folder))
        # AGENTS.md is part of what `refuse_foreign_root` recognises a harness
        # workspace by, so the fixture has to look like one.
        self.write("AGENTS.md", "# AGENTS\n")
        self.write("features/_project.md", "---\nproject: <YOUR_PROJECT>\ndescription:\n---\n")
        self.write("features/_template.md", "# Feature template\n")
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
            "repo": "",
            "template_repo": "",
            "branch": "",
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

        note = self.read("features/_project.md")
        self.assertIn("project: my-project", note)
        self.assertIn("Does something.", note)
        self.assertIn("my-project", self.read("README.md"))
        self.assertNotIn("<YOUR_PROJECT>", self.read("README.md"))
        self.assertIn("Feature in progress", self.read("progress/current.md"))

    def test_without_a_description_the_placeholder_stays(self) -> None:
        self.run_it(description="")
        self.assertIn("<PROJECT_DESCRIPTION>", self.read("README.md"))

    def test_a_template_file_is_missing(self) -> None:
        os.remove(os.path.join(self.root, "features", "_template.md"))
        code, output = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("A template file is missing", output)


class TestDoNotDestroyALiveProject(InstantiateCase):
    """The guardrail that matters."""

    def test_it_refuses_if_it_already_has_a_name(self) -> None:
        note = self.read("features/_project.md").replace(
            "project: <YOUR_PROJECT>", "project: live-project"
        )
        self.write("features/_project.md", note)

        code, output = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("already an instantiated project", output)
        # And it touched nothing.
        self.assertIn("project: live-project", self.read("features/_project.md"))

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
        # Recorded sessions now refuse the whole instantiation, not just the
        # history file. A workspace with a month of sessions behind it is a live
        # project however empty features/_project.md happens to look.
        self.write(
            "progress/history.md",
            "# History\n\n---\n\n## 2026-01-01 — feature 1 something\n\n- Result: done\n",
        )
        code, output = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("records previous sessions", output)
        self.assertIn("2026-01-01", self.read("progress/history.md"))

    def test_a_history_entry_is_found_even_after_its_own_horizontal_rule(self) -> None:
        # The old check asked "is there a heading after the second `---`?", and
        # /close-session invites free-form notes. An entry carrying its own rule
        # shifted the accounting, and a file ending in one read as empty — which
        # silently overwrote the append-only memory of the project.
        self.write(
            "progress/history.md",
            "# History\n\n---\n\n## 2026-01-01 — feature 1 x\n\n- Notes:\n\n---\n",
        )
        code, output = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("records previous sessions", output)

    def test_code_in_src_counts_as_a_live_project(self) -> None:
        # Neither implied by the other signals: a workspace can be unnamed and
        # specless and still hold weeks of code.
        self.write("src/app.py", "print('hello')\n")
        code, output = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("source file(s) in src/", output)
        self.assertTrue(self.exists("src/app.py"))

    def test_a_damaged_project_note_is_a_reason_to_stop_not_to_proceed(self) -> None:
        # The guard used to swallow the parse error into "no project", going
        # quiet exactly when the workspace was damaged.
        self.write("features/_project.md", "# just a heading\n")
        code, output = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("has no front matter", output)


class TestForeignRoot(InstantiateCase):
    """`--root` is hidden and the POSIX wrappers pass it straight through."""

    def test_a_folder_that_is_not_a_harness_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as outsider:
            with open(os.path.join(outsider, "thesis.txt"), "w") as handle:
                handle.write("a year of work\n")

            self.assertIsNotNone(instantiate.refuse_foreign_root(outsider))
            # And nothing was touched by the asking.
            self.assertTrue(os.path.isfile(os.path.join(outsider, "thesis.txt")))

    def test_a_missing_directory_is_refused(self) -> None:
        self.assertIsNotNone(
            instantiate.refuse_foreign_root(os.path.join(self.root, "nowhere"))
        )

    def test_a_real_workspace_is_allowed(self) -> None:
        self.assertIsNone(instantiate.refuse_foreign_root(self.root))


class TestDryRun(InstantiateCase):
    def test_dry_run_writes_nothing(self) -> None:
        before = self.read("features/_project.md")
        self.write("specs/REQ-001_something.md", "---\nid: REQ-001\n---\n")

        code, output = self.run_it(dry_run=True, force=True)
        self.assertEqual(code, 0)
        self.assertIn("simulated", output)
        self.assertEqual(self.read("features/_project.md"), before)
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


@unittest.skipUnless(shutil.which("git"), "git is needed for these tests")
class TestTheTwoRemotes(InstantiateCase):
    """`origin` is your project, `template` is the harness.

    Everything runs against a local repository: no network, no real remote.
    """

    TEMPLATE_URL = "https://example.invalid/someone/the-harness.git"
    PROJECT_URL = "https://example.invalid/me/my-project.git"

    def setUp(self) -> None:
        super().setUp()
        # The workspace as it looks after cloning the template: a repository
        # whose `origin` is the harness.
        self.git("init", "--quiet", "-b", "main")
        self.git("config", "user.email", "test@localhost")
        self.git("config", "user.name", "Test")
        self.git("remote", "add", "origin", self.TEMPLATE_URL)
        self.git("add", "-A")
        self.git("commit", "--quiet", "-m", "harness")

    def git(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *arguments], cwd=self.root, capture_output=True, text=True
        )

    def remote(self, name: str) -> str:
        return self.git("remote", "get-url", name).stdout.strip()

    def run_git(self, **kwargs) -> tuple[int, str]:
        return self.run_it(no_git=False, reset_git=True, **kwargs)

    def test_the_template_is_whatever_origin_was(self) -> None:
        # Nobody has to type --template-repo: you cloned the harness to get
        # here, so `origin` already holds its URL.
        code, _output = self.run_git(repo=self.PROJECT_URL)
        self.assertEqual(code, 0)
        self.assertEqual(self.remote("template"), self.TEMPLATE_URL)
        self.assertEqual(self.remote("origin"), self.PROJECT_URL)

    def test_the_flag_wins_over_what_origin_says(self) -> None:
        other = "https://example.invalid/fork/harness.git"
        self.run_git(repo=self.PROJECT_URL, template_repo=other)
        self.assertEqual(self.remote("template"), other)

    def test_the_new_history_keeps_the_templates_branch(self) -> None:
        # Not `init.defaultBranch`: this machine's may well be `master`.
        self.run_git(repo=self.PROJECT_URL)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main")
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_repo_equal_to_the_template_is_refused(self) -> None:
        code, output = self.run_git(repo=self.TEMPLATE_URL)
        self.assertEqual(code, 1)
        self.assertIn("template's own URL", output)

    def test_with_no_repo_origin_is_disconnected_from_the_harness(self) -> None:
        # Leaving it in place is how a project's first push lands on the
        # harness's repository.
        code, output = self.run_git()
        self.assertEqual(code, 0)
        self.assertEqual(self.remote("origin"), "")
        self.assertEqual(self.remote("template"), self.TEMPLATE_URL)
        self.assertIn("git remote add origin", output)


if __name__ == "__main__":
    unittest.main()