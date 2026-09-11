"""Tests for scripts/harness_hook.py.

What has to be protected here is a detail that is easy to lose in a refactor and
hard to notice: **the exit code**. A hook that exits 1 blocks nothing, and a
harness whose hooks do not block gives a sense of control that does not exist.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import harness_hook as hh  # noqa: E402


class TestStopEvent(unittest.TestCase):
    def _run(self, returncode: int, stdout: str = "", hook_input: dict | None = None):
        result = mock.Mock(returncode=returncode, stdout=stdout, stderr="")
        err = io.StringIO()
        with mock.patch.object(hh.subprocess, "run", return_value=result) as run, \
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
             mock.patch.object(hh, "_hook_input", return_value={}), \
             redirect_stderr(err):
            code = hh.event_stop()
        self.assertEqual(code, 2)
        self.assertIn("could not run the verifier", err.getvalue())


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


if __name__ == "__main__":
    unittest.main()
