"""The harness hooks, in one module and on both platforms.

Purpose
    Claude Code runs these hooks; the agent does not, so it cannot skip them.
    But for a hook to **block**, it has to exit with code 2 and write the reason
    to stderr: with exit 1 Claude Code shows the error and carries on as if
    nothing happened. The harness hooks used to exit 1, so in practice they
    blocked nothing — the session closed with the verifier red.

    This module also exists so the hooks work the same on Windows and on POSIX.
    They used to be pure PowerShell and under WSL or Linux they failed on every
    single edit.

Events
    stop          Before closing the turn: runs the whole verifier. If it is red,
                  it blocks (exit 2) and tells the agent what is missing.
    post-edit     After every Edit/Write: runs the tests. If they are broken, it
                  blocks.
    pre-tool-use  BEFORE writing: protects the layer that does the verifying. It
                  is the only moment a write can be prevented, because the other
                  two hooks arrive once it already happened.

Usage
    python scripts/harness_hook.py stop
    python scripts/harness_hook.py post-edit [--tests-dir tests]
    python scripts/harness_hook.py pre-tool-use

    `.claude/settings.json` invokes them. By hand they are useful for testing.

Exit codes
    0  all good (or there is nothing to verify yet)
    2  blocks: the reason goes to stderr, which is the channel Claude Code feeds
       back to the model

A note about the loop
    Claude Code calls the `stop` hook again after the agent reacts. If the hook
    always blocked, the session could never close: hence `stop_hook_active` from
    the input JSON, which says we are already coming from a block. `stop` also
    does not fire if you interrupt with Ctrl+C.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BLOCK = 2
PASS = 0


def _block(message: str) -> int:
    """The reason goes to stderr: that is what Claude Code feeds back to the model."""
    print(message, file=sys.stderr)
    return BLOCK


def _hook_input() -> dict:
    """The JSON Claude Code passes on stdin. Empty when run by hand."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def verifier_command() -> list[str]:
    """This platform's verifier. They are the same one, in two dialects."""
    if os.name == "nt":
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "./init.ps1",
            "-Quiet",
        ]
    return ["./init.sh", "--quiet"]


def event_stop() -> int:
    hook_input = _hook_input()
    if hook_input.get("stop_hook_active"):
        # We already come from a block: insisting would leave the session unable
        # to close.
        return PASS

    try:
        result = subprocess.run(
            verifier_command(),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return _block(f"[harness] could not run the verifier: {exc}")

    if result.returncode == 0:
        return PASS

    lines = [
        line
        for line in (result.stdout or "").splitlines()
        if line.startswith("[FAIL]")
    ]
    detail = "\n".join(lines) or (result.stderr or "").strip()
    return _block(
        "[harness] the verifier is red and the session does not close like this.\n"
        f"{detail}\n"
        "Sort it out and try again, or record the blocker in progress/current.md."
    )


def _count_tests(tests_dir: str) -> int | None:
    """How many tests there are. None if they could not be discovered."""
    try:
        suite = unittest.TestLoader().discover(tests_dir)
    except Exception:  # noqa: BLE001 — any import error counts the same
        return None
    return suite.countTestCases()


def event_post_edit(tests_dir: str) -> int:
    path = os.path.join(REPO_ROOT, tests_dir)
    if not os.path.isdir(path):
        print(f"[harness] {tests_dir}/ does not exist — nothing to run")
        return PASS

    total = _count_tests(path)
    if total is None:
        return _block(
            f"[harness] could not discover the tests in {tests_dir}/: there is an "
            f"import error. Fix it before editing anything else."
        )
    if total == 0:
        print(f"[harness] 0 tests in {tests_dir}/ — nothing is being verified yet")
        return PASS

    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", tests_dir, "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        print(f"[harness] {total} tests green")
        return PASS

    output = ((result.stdout or "") + (result.stderr or "")).strip()
    return _block(
        f"[harness] tests BROKEN after your edit — fix them before going on.\n{output}"
    )


# --- pre-tool-use: the layer that verifies is not edited mid-session ---------

# The files that decide whether the work is any good. An agent that sees red
# does not fix the red by editing the validator, and that temptation is not
# resolved by asking nicely in a .md.
PROTECTED_ZONE = (
    ".claude/",
    "scripts/",
    "schema/",
    "init.ps1",
    "init.sh",
    "bootstrap.ps1",
    "bootstrap.sh",
    "AGENTS.md",
    "CLAUDE.md",
    "CHECKPOINTS.md",
)

MAINTENANCE_MARK = ".harness-maintenance"

# Signs of a write in a shell line. A deliberately short heuristic: `Bash` can
# write in a thousand ways and chasing all of them would mean constant false
# positives. It covers the ones that actually show up.
WRITE_TOKENS = (
    ">", ">>", "tee ", "rm ", "mv ", "cp ", "sed -i", "truncate ",
    "Set-Content", "Add-Content", "Out-File", "Remove-Item", "New-Item",
)

WRITING_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")


def in_maintenance() -> bool:
    """Are we working on the harness itself, and on purpose?

    The door exists because the template gets maintained too. What changes is
    that opening it is a deliberate, visible act — a file that shows up in
    `git status` — instead of a silent edit in the middle of a development
    session.
    """
    if os.environ.get("HARNESS_MAINTENANCE"):
        return True
    return os.path.exists(os.path.join(REPO_ROOT, MAINTENANCE_MARK))


def protected_path(path: str) -> str | None:
    """Returns the protected prefix `path` touches, or None."""
    if not path:
        return None
    normalized = path.replace("\\", "/")
    # A relative path resolves against the repository root, not the cwd: the
    # hook does not control where it is called from.
    absolute = normalized if os.path.isabs(normalized) else os.path.join(REPO_ROOT, normalized)
    try:
        relative = os.path.relpath(os.path.abspath(absolute), REPO_ROOT).replace("\\", "/")
    except ValueError:
        relative = normalized
    if relative.startswith(".."):
        return None
    for prefix in PROTECTED_ZONE:
        if relative == prefix or relative.startswith(prefix):
            return prefix
    return None


def _reason(target: str) -> str:
    return (
        f"[harness] {target} is part of the layer that verifies the work, and it "
        f"is not touched during a development session: an agent that sees red does "
        f"not fix the red by editing the validator.\n"
        f"If you really are maintaining the harness, say so explicitly by creating "
        f"the {MAINTENANCE_MARK} file at the root (or exporting "
        f"HARNESS_MAINTENANCE=1) and delete it when you are done."
    )


def event_pre_tool_use() -> int:
    hook_input = _hook_input()
    tool = hook_input.get("tool_name", "")
    data = hook_input.get("tool_input") or {}
    if not isinstance(data, dict):
        return PASS

    if in_maintenance():
        return PASS

    if tool in WRITING_TOOLS:
        prefix = protected_path(str(data.get("file_path", "")))
        return _block(_reason(prefix)) if prefix else PASS

    if tool in ("Bash", "PowerShell"):
        command = str(data.get("command", ""))
        if not any(token in command for token in WRITE_TOKENS):
            return PASS
        for prefix in PROTECTED_ZONE:
            if prefix in command.replace("\\", "/"):
                return _block(
                    _reason(prefix)
                    + "\n(Spotted in a shell command: if you were only reading, "
                    "rephrase it without write operators.)"
                )

    return PASS


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Harness hooks.")
    parser.add_argument("event", choices=("stop", "post-edit", "pre-tool-use"))
    parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Tests folder for post-edit (default: tests)",
    )
    args = parser.parse_args(argv[1:])

    if args.event == "stop":
        return event_stop()
    if args.event == "pre-tool-use":
        return event_pre_tool_use()
    return event_post_edit(args.tests_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
