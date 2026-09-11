"""Tests for scripts/reset_workspace.py.

This is the most destructive script in the harness: it deletes a project's
working copy. So most of what is covered here is the refusals — and, every
time it refuses, that **nothing was touched**.

Everything runs against local bare repositories in a temporary directory, so
the suite never touches the network and never touches a real remote.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instantiate  # noqa: E402
import reset_workspace  # noqa: E402

# git's object files are read-only, and on Windows that makes shutil.rmtree
# fail outright. The harness already solved this; the tests borrow it.
rmtree = instantiate.rmtree


HARNESS_FILES = {
    "README.md": "# <YOUR_PROJECT>\n\n> <PROJECT_DESCRIPTION>\n",
    "AGENTS.md": "# AGENTS\n",
    "init.sh": "#!/usr/bin/env bash\necho ok\n",
    "docs/architecture.md": "# Architecture of <YOUR_PROJECT>\n",
    "docs/conventions.md": "# Conventions\n",
    "docs/verification.md": "# Verification\n",
    "progress/current.md": "# Current session\n",
    "progress/history.md": "# Session history\n\n---\n\n_No sessions._\n",
    "scripts/instantiate.py": '"""stand-in for the real module"""\n',
    "specs/_req_template.md": "---\nid: REQ-00N\n---\n",
    ".gitignore": "__pycache__/\n.venv/\n.env\n",
}


@unittest.skipUnless(shutil.which("git"), "git is needed for these tests")
class ResetCase(unittest.TestCase):
    """A template repo, a project repo and a workspace, all local."""

    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        # Keep the developer's global git config out of this: init.defaultBranch,
        # commit.gpgsign and global hooks would all change the outcome.
        self.env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.path.join(self.base, "gitconfig"),
            "GIT_CONFIG_SYSTEM": os.path.join(self.base, "gitconfig"),
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@localhost",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@localhost",
        }
        self.template_url = self.bare("template.git")
        self.origin_url = self.bare("origin.git")
        self.seed_template()
        self.workspace = os.path.join(self.base, "workspace")
        self.git("clone", "--quiet", self.template_url, self.workspace, cwd=self.base)
        self.instantiate_as("notes", self.origin_url)

    def tearDown(self) -> None:
        rmtree(self.base)

    # -- fixture ---------------------------------------------------------
    def git(self, *arguments: str, cwd: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd or self.workspace,
            capture_output=True,
            text=True,
            env=self.env,
        )

    def bare(self, name: str) -> str:
        path = os.path.join(self.base, name)
        self.git("init", "--bare", "--quiet", "-b", "main", path, cwd=self.base)
        return path

    def seed_template(self) -> None:
        seed = os.path.join(self.base, "seed")
        for rel, content in HARNESS_FILES.items():
            path = os.path.join(seed, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
        with open(os.path.join(seed, "feature_list.json"), "w", encoding="utf-8") as handle:
            json.dump(
                {"project": "<YOUR_PROJECT>", "description": "", "rules": {}, "features": []},
                handle,
            )
        self.git("init", "--quiet", "-b", "main", cwd=seed)
        self.git("add", "-A", cwd=seed)
        self.git("commit", "--quiet", "-m", "harness", cwd=seed)
        self.git("push", "--quiet", self.template_url, "main", cwd=seed)
        rmtree(seed)

    def instantiate_as(self, name: str, repo: str) -> None:
        """Bootstraps the workspace, the way a human would the first time."""
        args = self.namespace(name=name, repo=repo)
        with redirect_stdout(io.StringIO()):
            instantiate.Instantiator(self.workspace, args).run()

    def namespace(self, **overrides) -> "object":
        import argparse

        base = {
            "name": "notes", "description": "", "repo": "", "template_repo": "",
            "force": True, "reset_git": True, "no_git": False, "dry_run": False,
            "branch": "",
        }
        base.update(overrides)
        return argparse.Namespace(**base)

    # -- helpers ---------------------------------------------------------
    def write(self, rel: str, content: str = "x\n") -> None:
        path = os.path.join(self.workspace, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    def read(self, rel: str) -> str:
        with open(os.path.join(self.workspace, rel), encoding="utf-8") as handle:
            return handle.read()

    def exists(self, rel: str) -> bool:
        return os.path.exists(os.path.join(self.workspace, rel))

    def project_name(self) -> str:
        with open(os.path.join(self.workspace, "feature_list.json"), encoding="utf-8") as handle:
            return json.load(handle)["project"]

    def commit_all(self, message: str = "work") -> None:
        self.git("add", "-A")
        self.git("commit", "--quiet", "-m", message)

    def push(self) -> None:
        self.git("push", "--quiet", "-u", "origin", "HEAD")

    def do_work(self) -> None:
        """A feature's worth of files, committed and pushed."""
        self.write("src/notes.py", "def search(): pass\n")
        self.write("specs/REQ-001_search.md", "---\nid: REQ-001\n---\n")
        self.commit_all("feat: search")
        self.push()

    def reset(self, **overrides) -> tuple[int, str]:
        import argparse

        options = {
            "name": "ecommerce", "description": "", "repo": self.other_repo(),
            "template_repo": "", "source": "", "force": False, "clean_ignored": False,
            "no_bundle": False, "no_git": False, "dry_run": False, "branch": "main",
        }
        options.update(overrides)
        output = io.StringIO()
        with redirect_stdout(output):
            code = reset_workspace.Resetter(
                self.workspace, argparse.Namespace(**options)
            ).run()
        return code, output.getvalue()

    def other_repo(self) -> str:
        path = os.path.join(self.base, "ecommerce.git")
        if not os.path.isdir(path):
            self.bare("ecommerce.git")
        return path


class TestTheHappyPath(ResetCase):
    def test_the_workspace_becomes_the_next_project(self) -> None:
        self.do_work()
        code, _output = self.reset()
        self.assertEqual(code, 0)

        self.assertEqual(self.project_name(), "ecommerce")
        self.assertFalse(self.exists("src/notes.py"))
        self.assertFalse(self.exists("specs/REQ-001_search.md"))
        self.assertIn("ecommerce", self.read("README.md"))

    def test_a_file_the_project_had_modified_comes_back(self) -> None:
        self.write("AGENTS.md", "# the project wrecked this\n")
        self.commit_all()
        self.push()

        self.reset()
        self.assertEqual(self.read("AGENTS.md"), "# AGENTS\n")

    def test_a_file_the_project_had_deleted_comes_back(self) -> None:
        os.remove(os.path.join(self.workspace, "docs/conventions.md"))
        self.commit_all()
        self.push()

        self.reset()
        self.assertTrue(self.exists("docs/conventions.md"))

    def test_the_git_topology_afterwards(self) -> None:
        self.do_work()
        self.reset()

        self.assertEqual(
            self.git("remote", "get-url", "origin").stdout.strip(), self.other_repo()
        )
        self.assertEqual(
            self.git("remote", "get-url", "template").stdout.strip(), self.template_url
        )
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "1")
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main")

    def test_the_previous_project_repo_is_untouched(self) -> None:
        self.do_work()
        before = self.git("log", "--oneline", cwd=self.origin_url).stdout
        self.reset()
        self.assertEqual(self.git("log", "--oneline", cwd=self.origin_url).stdout, before)


class TestItRefuses(ResetCase):
    """And every time, nothing is touched."""

    def test_uncommitted_changes(self) -> None:
        self.do_work()
        self.write("src/notes.py", "half-written\n")

        code, output = self.reset()
        self.assertEqual(code, 1)
        self.assertIn("uncommitted changes", output)
        self.assertEqual(self.project_name(), "notes")
        self.assertTrue(self.exists("src/notes.py"))

    def test_unpushed_commits(self) -> None:
        self.do_work()
        self.write("src/more.py")
        self.commit_all("feat: not pushed")

        code, output = self.reset()
        self.assertEqual(code, 1)
        self.assertIn("not on", output)
        self.assertEqual(self.project_name(), "notes")

    def test_a_stash_entry(self) -> None:
        self.do_work()
        self.write("src/notes.py", "wip\n")
        self.git("stash", "push", "--quiet")

        code, output = self.reset()
        self.assertEqual(code, 1)
        self.assertIn("stash", output)

    def test_force_gets_past_all_of_them(self) -> None:
        self.do_work()
        self.write("src/notes.py", "half-written\n")
        self.write("src/more.py")
        self.commit_all("feat: not pushed")

        code, _output = self.reset(force=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.project_name(), "ecommerce")

    def test_repo_equal_to_the_template_is_never_allowed(self) -> None:
        self.do_work()
        for force in (False, True):
            with self.subTest(force=force):
                code, output = self.reset(repo=self.template_url, force=force)
                self.assertEqual(code, 1)
                self.assertIn("template's own URL", output)
                self.assertEqual(self.project_name(), "notes")

    def test_an_unreachable_template_touches_nothing(self) -> None:
        self.do_work()
        code, output = self.reset(template_repo=os.path.join(self.base, "nope.git"))
        self.assertEqual(code, 1)
        self.assertIn("Could not read the template", output)
        self.assertEqual(self.project_name(), "notes")
        self.assertTrue(self.exists("src/notes.py"))

    def test_a_source_that_is_not_the_harness_touches_nothing(self) -> None:
        self.do_work()
        impostor = os.path.join(self.base, "impostor")
        os.makedirs(impostor)
        with open(os.path.join(impostor, "README.md"), "w") as handle:
            handle.write("not the harness\n")

        code, output = self.reset(source=impostor)
        self.assertEqual(code, 1)
        self.assertIn("does not carry the harness template", output)
        self.assertTrue(self.exists("src/notes.py"))


class TestDryRun(ResetCase):
    def test_it_writes_nothing(self) -> None:
        self.do_work()
        code, output = self.reset(dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("simulated", output)
        self.assertEqual(self.project_name(), "notes")
        self.assertTrue(self.exists("src/notes.py"))

    def test_it_names_a_file_it_would_delete(self) -> None:
        self.do_work()
        _code, output = self.reset(dry_run=True)
        self.assertIn("src/notes.py", output)


class TestWhatSurvives(ResetCase):
    def test_ignored_files_survive_and_are_reported(self) -> None:
        self.do_work()
        self.write(".env", "SECRET=abc\n")
        self.write(".venv/marker")

        _code, output = self.reset()
        self.assertTrue(self.exists(".env"))
        self.assertIn("Kept, because git ignores them", output)
        self.assertIn(".env", output)

    def test_clean_ignored_deletes_them(self) -> None:
        self.do_work()
        self.write(".env", "SECRET=abc\n")

        code, _output = self.reset(clean_ignored=True)
        self.assertEqual(code, 0)
        self.assertFalse(self.exists(".env"))

    def test_the_maintenance_mark_never_travels(self) -> None:
        # It disarms the PreToolUse hook, so it must not survive into the next
        # project — and it must not block the reset either, or the maintainer
        # who declared maintenance learns to reach for --force.
        self.do_work()
        self.write(reset_workspace.MAINTENANCE_MARK, "")

        code, _output = self.reset()
        self.assertEqual(code, 0)
        self.assertFalse(self.exists(reset_workspace.MAINTENANCE_MARK))


class TestTheSafetyNet(ResetCase):
    def test_the_bundle_holds_the_previous_history(self) -> None:
        self.do_work()
        head = self.git("rev-parse", "HEAD").stdout.strip()

        _code, output = self.reset()
        line = [l for l in output.splitlines() if "pre-reset-" in l and "Backup" in l]
        self.assertTrue(line, output)
        bundle = line[0].split("history: ", 1)[1].strip()
        self.assertTrue(os.path.isfile(bundle))

        recovered = os.path.join(self.base, "recovered")
        self.git("clone", "--quiet", bundle, recovered, cwd=self.base)
        self.assertIn(head, self.git("log", "--format=%H", cwd=recovered).stdout)

    def test_no_bundle_skips_it(self) -> None:
        self.do_work()
        _code, output = self.reset(no_bundle=True)
        self.assertNotIn("Backup of the previous history", output)


if __name__ == "__main__":
    unittest.main()
