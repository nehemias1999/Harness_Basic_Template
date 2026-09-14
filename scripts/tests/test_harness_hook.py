"""Tests for scripts/harness_hook.py.

What has to be protected here is a detail that is easy to lose in a refactor and
hard to notice: **the exit code**. A hook that exits 1 blocks nothing, and a
harness whose hooks do not block gives a sense of control that does not exist.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import harness_hook as hh  # noqa: E402


class TestStopEvent(unittest.TestCase):
    def _run(
        self,
        returncode: int,
        stdout: str = "",
        hook_input: dict | None = None,
        pristine: bool = False,
    ):
        # `pristine=False` by default: these tests are about a real project. It
        # has to be said out loud, because the repository the suite runs in is
        # the template itself — left to the real check, every one of them would
        # take the "nothing to close" path and stop testing what it claims to.
        result = mock.Mock(returncode=returncode, stdout=stdout, stderr="")
        err = io.StringIO()
        with mock.patch.object(hh.subprocess, "run", return_value=result) as run, \
             mock.patch.object(hh, "_pristine_template", return_value=pristine), \
             mock.patch.object(hh, "_hook_input", return_value=hook_input or {}), \
             redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = hh.event_stop()
        return code, err.getvalue(), run

    def test_a_green_verifier_does_not_block(self) -> None:
        code, _err, _run = self._run(0)
        self.assertEqual(code, hh.PASS)

    def test_a_red_verifier_blocks_with_exit_2(self) -> None:
        code, err, _run = self._run(1, "[OK]    fine\n[FAIL]  REQ-001 needs approval\n")
        self.assertEqual(code, 2)
        self.assertIn("REQ-001 needs approval", err)

    def test_the_reason_goes_to_stderr(self) -> None:
        # That is the channel Claude Code feeds back to the model: on stdout the
        # block would be mute.
        _code, err, _run = self._run(1, "[FAIL]  something\n")
        self.assertTrue(err.strip())

    def test_it_does_not_insist_if_it_already_came_from_a_block(self) -> None:
        code, _err, run = self._run(1, "[FAIL]  x\n", hook_input={"stop_hook_active": True})
        self.assertEqual(code, hh.PASS)
        run.assert_not_called()

    def test_if_the_verifier_does_not_start_it_blocks(self) -> None:
        err = io.StringIO()
        with mock.patch.object(hh.subprocess, "run", side_effect=OSError("missing")), \
             mock.patch.object(hh, "_pristine_template", return_value=False), \
             mock.patch.object(hh, "_hook_input", return_value={}), \
             redirect_stderr(err):
            code = hh.event_stop()
        self.assertEqual(code, 2)
        self.assertIn("could not run the verifier", err.getvalue())

    def test_the_uninstantiated_template_does_not_block(self) -> None:
        # Red is the expected state here: section 3 saying "NOT INSTANTIATED" is
        # the verifier working. Blocking on it made the condition circular — no
        # session on the template could close, and each one ended by writing a
        # blocker note repeating what the verifier already said.
        code, err, run = self._run(1, "[FAIL]  NOT INSTANTIATED\n", pristine=True)
        self.assertEqual(code, hh.PASS)
        self.assertEqual(err, "")
        run.assert_not_called()

    def test_once_instantiated_a_red_verifier_blocks_again(self) -> None:
        # The exemption is for the template, not a way out of a red verifier.
        code, err, _run = self._run(1, "[FAIL]  tests broken\n", pristine=False)
        self.assertEqual(code, 2)
        self.assertIn("tests broken", err)


class TestPristineTemplate(unittest.TestCase):
    """The exemption leans on validate_project_setup: check the wiring holds."""

    # Deliberately NOT asserting on the repository's own state: these tests
    # travel with the harness into every instantiated project, where the honest
    # answer flips to False. What is worth pinning is the delegation, not which
    # repo happens to be running the suite.

    def test_a_pristine_repo_is_reported_as_the_template(self) -> None:
        with mock.patch("validate_project_setup.check", return_value=([], [], True)):
            self.assertTrue(hh._pristine_template())

    def test_a_configured_project_is_not_pristine(self) -> None:
        with mock.patch("validate_project_setup.check", return_value=([], [], False)):
            self.assertFalse(hh._pristine_template())

    def test_if_it_cannot_tell_it_assumes_a_project(self) -> None:
        # Failing closed: an unreadable repo must keep blocking, not slip out.
        with mock.patch("validate_project_setup.check", side_effect=OSError("boom")):
            self.assertFalse(hh._pristine_template())


class TestVerifierCommand(unittest.TestCase):
    def test_windows_uses_the_ps1(self) -> None:
        with mock.patch.object(hh.os, "name", "nt"):
            self.assertIn("./init.ps1", hh.verifier_command())

    def test_posix_uses_the_sh(self) -> None:
        with mock.patch.object(hh.os, "name", "posix"):
            command = hh.verifier_command()
        self.assertEqual(command[0], "./init.sh")
        self.assertIn("--quiet", command)


class TestPostEditEvent(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self._patch = mock.patch.object(hh, "REPO_ROOT", self.root)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def _tests_dir(self) -> str:
        path = os.path.join(self.root, "tests")
        os.makedirs(path, exist_ok=True)
        return path

    def _run(self) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = hh.event_post_edit("tests")
        return code, out.getvalue(), err.getvalue()

    def test_no_tests_folder_does_not_block(self) -> None:
        code, out, _err = self._run()
        self.assertEqual(code, hh.PASS)
        self.assertIn("nothing to run", out)

    def test_zero_tests_does_not_block(self) -> None:
        self._tests_dir()
        code, out, _err = self._run()
        self.assertEqual(code, hh.PASS)
        self.assertIn("0 tests", out)

    def test_green_tests_do_not_block(self) -> None:
        path = self._tests_dir()
        with open(os.path.join(path, "test_ok.py"), "w", encoding="utf-8") as handle:
            handle.write(
                "import unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n"
            )
        code, out, _err = self._run()
        self.assertEqual(code, hh.PASS)
        self.assertIn("green", out)

    def test_broken_tests_block_with_exit_2(self) -> None:
        path = self._tests_dir()
        with open(os.path.join(path, "test_broken.py"), "w", encoding="utf-8") as handle:
            handle.write(
                "import unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_broken(self):\n"
                "        self.assertTrue(False)\n"
            )
        code, _out, err = self._run()
        self.assertEqual(code, 2)
        self.assertIn("BROKEN", err)

    def test_an_import_error_blocks(self) -> None:
        # unittest does not blow up during discovery: it turns the broken import
        # into a failing test. Whichever path it takes, what matters is that it
        # blocks and that the reason is visible.
        path = self._tests_dir()
        with open(os.path.join(path, "test_import.py"), "w", encoding="utf-8") as handle:
            handle.write("import a_module_that_does_not_exist\n")
        code, _out, err = self._run()
        self.assertEqual(code, 2)
        self.assertIn("a_module_that_does_not_exist", err)

    def test_if_discovery_explodes_it_blocks(self) -> None:
        self._tests_dir()
        with mock.patch.object(hh, "_count_tests", return_value=None):
            code, _out, err = self._run()
        self.assertEqual(code, 2)
        self.assertIn("import error", err)

    def test_the_tests_dir_is_an_argument_not_an_interpolation(self) -> None:
        # The old hook put the name inside a string of Python code: one quote in
        # the parameter and you could run whatever you liked.
        code, out, err = self._run()
        self.assertIn(code, (hh.PASS, 2))
        self.assertNotIn("Traceback", out + err)


class TestPreToolUse(unittest.TestCase):
    """The layer that verifies is not edited mid-session."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self._patch = mock.patch.object(hh, "REPO_ROOT", self.root)
        self._patch.start()
        # No maintenance mark and no environment variable.
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop("HARNESS_MAINTENANCE", None)

    def tearDown(self) -> None:
        self._env.stop()
        self._patch.stop()
        self._tmp.cleanup()

    def _run(self, hook_input: dict) -> tuple[int, str]:
        err = io.StringIO()
        with mock.patch.object(hh, "_hook_input", return_value=hook_input), \
             redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = hh.event_pre_tool_use()
        return code, err.getvalue()

    def _write(self, path: str, tool: str = "Write") -> tuple[int, str]:
        return self._run({"tool_name": tool, "tool_input": {"file_path": path}})

    def _shell(self, command: str) -> tuple[int, str]:
        return self._run({"tool_name": "Bash", "tool_input": {"command": command}})

    def test_it_blocks_writing_to_the_validators(self) -> None:
        code, err = self._write("scripts/validate_requirements.py")
        self.assertEqual(code, 2)
        self.assertIn("layer that verifies", err)

    def test_it_blocks_writing_to_the_hooks(self) -> None:
        self.assertEqual(self._write(".claude/settings.json", "Edit")[0], 2)

    def test_it_blocks_writing_to_the_verifier(self) -> None:
        self.assertEqual(self._write("init.sh")[0], 2)
        self.assertEqual(self._write("init.ps1")[0], 2)

    def test_it_blocks_writing_to_the_contract(self) -> None:
        for path in ("AGENTS.md", "CLAUDE.md", "CHECKPOINTS.md"):
            with self.subTest(path=path):
                self.assertEqual(self._write(path)[0], 2)

    def test_it_lets_the_project_code_through(self) -> None:
        for path in ("src/module.py", "tests/test_module.py", "feature_list.json",
                     "progress/current.md", "specs/REQ-001_x.md", "docs/architecture.md"):
            with self.subTest(path=path):
                self.assertEqual(self._write(path)[0], hh.PASS)

    def test_it_blocks_a_disguised_shell_write(self) -> None:
        # The Edit|Write matcher does not see this; PreToolUse over Bash does.
        self.assertEqual(self._shell("echo pass > scripts/validate_requirements.py")[0], 2)
        self.assertEqual(self._shell("rm -rf scripts/tests")[0], 2)

    def test_it_does_not_get_in_the_way_of_a_shell_read(self) -> None:
        self.assertEqual(self._shell("cat scripts/validate_requirements.py")[0], hh.PASS)
        self.assertEqual(self._shell("python scripts/validate_requirements.py .")[0], hh.PASS)

    def test_a_write_elsewhere_in_the_line_does_not_count(self) -> None:
        # The write token and the protected path have to be in the same piece of
        # the command. Before, they only had to appear somewhere in the same
        # string, which blocked plenty of commands that wrote nothing.
        cases = (
            # A commit message quoting a path, and a `>` inside the trailer's
            # email address. This is the one that actually showed up.
            "git add scripts/harness_hook.py && git commit -m 'fix it'\n"
            "Co-Authored-By: Someone <noreply@example.com>",
            # Reading two things, one of them redirected.
            "ls -la .github/workflows/ && find .claude -type f",
            # A write, but to somewhere that is none of the hook's business.
            "echo note > /tmp/scratch.txt && cat scripts/harness_hook.py",
        )
        for command in cases:
            with self.subTest(command=command.splitlines()[0]):
                self.assertEqual(self._shell(command)[0], hh.PASS)

    def test_discarding_output_is_not_a_write(self) -> None:
        # `2>&1` and `>/dev/null` carry a `>` but cannot touch a file in the
        # repo. They used to be enough on their own to make a read look like a
        # write.
        for command in (
            "python -m pytest scripts/tests -q 2>&1 | tail -15",
            "cat scripts/harness_hook.py 2>/dev/null",
            "ls scripts/ >/dev/null",
        ):
            with self.subTest(command=command):
                self.assertEqual(self._shell(command)[0], hh.PASS)

    def test_a_real_write_in_a_longer_line_still_blocks(self) -> None:
        # The loosening must not become a way through: a genuine write to the
        # protected zone blocks no matter what else is on the line.
        for command in (
            "cat README.md && echo x > scripts/harness_hook.py",
            "python -m pytest -q 2>&1; rm -rf scripts/tests",
            "git log --oneline | head -5 && sed -i 's/a/b/' init.sh",
        ):
            with self.subTest(command=command):
                self.assertEqual(self._shell(command)[0], 2)

    def test_the_maintenance_mark_opens_the_door(self) -> None:
        with open(os.path.join(self.root, hh.MAINTENANCE_MARK), "w") as handle:
            handle.write("")
        self.assertEqual(self._write("scripts/validate_requirements.py")[0], hh.PASS)

    def test_the_environment_variable_does_too(self) -> None:
        os.environ["HARNESS_MAINTENANCE"] = "1"
        try:
            self.assertEqual(self._write("init.ps1")[0], hh.PASS)
        finally:
            os.environ.pop("HARNESS_MAINTENANCE", None)

    def test_a_path_outside_the_repo_is_none_of_its_business(self) -> None:
        self.assertEqual(self._write("/tmp/other/scripts/thing.py")[0], hh.PASS)

    def test_the_case_of_the_path_does_not_let_it_through(self) -> None:
        # NTFS is case-insensitive: `Scripts/x.py` and `scripts/x.py` are the
        # same file. A case-sensitive guard protected one spelling of the two,
        # which is to say it protected neither.
        for path in (
            "Scripts/validate_requirements.py",
            "SCRIPTS/validate_requirements.py",
            ".CLAUDE/settings.json",
            "Init.ps1",
            "init.PS1",
            "Agents.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(self._write(path)[0], 2)

    def test_the_bare_directory_name_counts_too(self) -> None:
        # `mv scripts scripts_old` names the directory without a trailing slash,
        # and moving the validators away is as good as editing them.
        self.assertEqual(hh.protected_path("scripts"), "scripts/")
        self.assertEqual(hh.protected_path(".github"), ".github/")

    def test_it_blocks_writing_to_the_newly_covered_paths(self) -> None:
        for path in (
            ".github/workflows/harness.yml",
            "reset.ps1",
            "reset.sh",
        ):
            with self.subTest(path=path):
                self.assertEqual(self._write(path)[0], 2)

    def test_the_agent_cannot_install_its_own_maintenance_door(self) -> None:
        # One allowed Write used to disarm every protection below it, and a
        # second removed the evidence.
        code, err = self._write(hh.MAINTENANCE_MARK)
        self.assertEqual(code, 2)
        self.assertIn("does not let a tool create it", err)

    def test_not_even_while_maintenance_is_already_open(self) -> None:
        # Otherwise the door renews itself: declare once, keep it forever.
        with open(os.path.join(self.root, hh.MAINTENANCE_MARK), "w") as handle:
            handle.write("")
        self.assertEqual(self._write(hh.MAINTENANCE_MARK)[0], 2)

    def test_the_powershell_tool_is_treated_like_bash(self) -> None:
        # The tool was missing from the settings matcher, so this branch had
        # never run on a win32 repo where PowerShell is the primary shell.
        blocked = self._run({
            "tool_name": "PowerShell",
            "tool_input": {"command": "Set-Content scripts/validate_requirements.py -Value x"},
        })
        self.assertEqual(blocked[0], 2)


class TestShellCorpus(unittest.TestCase):
    """The two lists this matcher exists to satisfy at the same time.

    Inverting a guard is where holes hide, and over-tightening one is how it ends
    up switched off. So both directions are pinned: real commands must keep
    working, and every bypass the audit found must stay shut.
    """

    MUST_PASS = (
        # Reading the harness — the reason the deny-list existed in the first
        # place was to not get in the way of this.
        "cat scripts/harness_hook.py",
        "head -50 scripts/approve.py",
        "grep -n 'def ' scripts/validate_requirements.py",
        "sed -n '1,40p' scripts/approve.py",
        "wc -l scripts/harness_hook.py",
        "find scripts -name '*.py'",
        "ls -la .claude/agents/",
        # Running it.
        "python scripts/validate_requirements.py .",
        "python scripts/validate_feature_list.py feature_list.json",
        "python -m unittest discover -s scripts/tests -q",
        "python -m pytest scripts/tests -q",
        "./init.sh --quiet",
        # git that cannot rewrite the tree.
        "git log --oneline -5",
        "git diff scripts/harness_hook.py",
        "git status --porcelain",
        "git add scripts/harness_hook.py",
        # Ordinary project work, which never names the zone at all.
        "pytest tests/",
        "npm test",
        "python src/app.py",
        "mkdir src/api",
        "rm -rf build/",
        # The false positive that started all this: a path in a commit message.
        "git commit -m 'touch up scripts/harness_hook.py'",
        # And output-discarding, which carries a `>` but writes nothing.
        "python -m pytest scripts/tests -q 2>&1 | tail -15",
        "cat scripts/harness_hook.py 2>/dev/null",
    )

    MUST_BLOCK = (
        # The inline-code family: no path analysis can read what the code does.
        'python -c "open(\'scripts/validate_requirements.py\',\'w\')"',
        "perl -pi -e 's/x/y/' scripts/validate_requirements.py",
        # Writers the old token list had never heard of.
        "install -m644 /tmp/fake.py scripts/validate_requirements.py",
        "dd of=scripts/validate_requirements.py if=/tmp/f",
        "ln -sf /tmp/fake.py scripts/validate_requirements.py",
        "sed --in-place 's/a/b/' init.sh",
        "find scripts -name '*.py' -exec truncate -s0 {} +",
        # The git-native family — the worst of them, because a transcript full of
        # these looks like ordinary work and leaves a clean tree.
        "git checkout HEAD~5 -- scripts/",
        "git restore --source=HEAD~1 scripts/validate_requirements.py",
        "git apply /tmp/evil.diff scripts/",
        "git stash pop scripts/",
        # Taking the whole directory away instead of editing it.
        "mv scripts scripts_old",
        "rm -rf scripts/tests",
        # Moving the goalposts, including across tool calls: the Bash shell is
        # persistent, so a `cd` taints commands this hook will never see.
        "cd scripts",
        # What the old list did catch, still caught.
        "echo pass > scripts/validate_requirements.py",
        "truncate -s0 init.sh",
        "Set-Content scripts/harness_hook.py -Value y",
    )

    def test_real_commands_are_not_blocked(self) -> None:
        for command in self.MUST_PASS:
            with self.subTest(command=command):
                self.assertIsNone(hh.inspect_command(command))

    def test_every_bypass_the_audit_found_is_shut(self) -> None:
        for command in self.MUST_BLOCK:
            with self.subTest(command=command):
                self.assertIsNotNone(hh.inspect_command(command))

    def test_a_heredoc_into_an_interpreter_is_blocked(self) -> None:
        # Checked against the whole command: a heredoc body ignores `;` and `&&`,
        # so splitting into segments first is precisely how this used to pass.
        self.assertIsNotNone(hh.inspect_command(
            'python - <<EOF\nopen("scripts/validate_requirements.py","w").write("x")\nEOF'
        ))

    def test_a_command_that_never_names_the_zone_is_not_examined(self) -> None:
        # This is what keeps the inversion affordable: the allow-list is only
        # consulted for commands that mention the harness, so ordinary work
        # cannot be blocked by any rule in it.
        for command in ("dd of=/tmp/x if=/dev/zero", "curl -X POST https://example.com",
                        "docker compose up -d", "rm -rf node_modules"):
            with self.subTest(command=command):
                self.assertIsNone(hh.inspect_command(command))

    def test_audit_mode_reports_without_blocking(self) -> None:
        out = io.StringIO()
        with mock.patch.dict(os.environ, {hh.AUDIT_ENV: "1"}), \
             mock.patch.object(hh, "in_maintenance", return_value=False), \
             mock.patch.object(hh, "_hook_input", return_value={
                 "tool_name": "Bash",
                 "tool_input": {"command": "rm -rf scripts/tests"}}), \
             redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = hh.event_pre_tool_use()
        self.assertEqual(code, hh.PASS)
        self.assertIn("would block", out.getvalue())


class TestSettingsWiring(unittest.TestCase):
    """The hook can only guard the tools the settings actually route to it."""

    def _matchers(self) -> dict:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(root, ".claude", "settings.json"), encoding="utf-8") as handle:
            settings = json.load(handle)
        return {
            event: [entry.get("matcher", "") for entry in entries]
            for event, entries in settings["hooks"].items()
        }

    def test_pre_tool_use_covers_powershell(self) -> None:
        # harness_hook.py has handled "PowerShell" all along; the settings never
        # routed it, so the branch was dead code on the platform that needed it.
        self.assertTrue(any("PowerShell" in m for m in self._matchers()["PreToolUse"]))

    def test_post_tool_use_covers_every_writing_tool(self) -> None:
        matchers = " ".join(self._matchers()["PostToolUse"])
        for tool in hh.WRITING_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, matchers)


if __name__ == "__main__":
    unittest.main()
