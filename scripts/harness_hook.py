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
                  it blocks (exit 2) and tells the agent what is missing. The one
                  exception is the uninstantiated template, where red is the
                  expected state and blocking would be circular.
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
import re
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


def _pristine_template() -> bool:
    """Is this the uninstantiated template rather than a real project?

    `validate_project_setup` already knows how to tell: its `pristine` flag is
    true when nothing at all is configured. We reuse it instead of re-deriving
    the condition, so the two cannot drift apart.
    """
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from validate_project_setup import check
    except ImportError:
        return False
    try:
        _fails, _warns, pristine = check(REPO_ROOT)
    except Exception:  # noqa: BLE001 — if we cannot tell, assume it is a project
        return False
    return bool(pristine)


def event_stop() -> int:
    hook_input = _hook_input()
    if hook_input.get("stop_hook_active"):
        # We already come from a block: insisting would leave the session unable
        # to close.
        return PASS

    if _pristine_template():
        # The template repository itself. The verifier is red here **by design**
        # — section 3 reporting "NOT INSTANTIATED" is it doing its job, not a
        # defect to be worked around. Blocking on it would make the condition
        # circular: no session on the template could ever close, and every one
        # would end by writing a blocker note that says the same thing. There is
        # no project here to leave in a bad state, so there is nothing to guard.
        print(
            "[harness] this is the uninstantiated template, not a project: the "
            "verifier is red by design and there is nothing to close. Copy the "
            "folder, run the bootstrap script there, and work on the copy."
        )
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
#
# Lowercase on purpose: `protected_path` folds the case before comparing. NTFS
# is case-insensitive, so `Scripts/validate_requirements.py` used to sail past a
# case-sensitive comparison and write the very same file.
PROTECTED_ZONE = (
    ".claude/",
    "scripts/",
    "schema/",
    ".github/",
    "init.ps1",
    "init.sh",
    "bootstrap.ps1",
    "bootstrap.sh",
    "reset.ps1",
    "reset.sh",
    "agents.md",
    "claude.md",
    "checkpoints.md",
    ".harness-maintenance",
)

MAINTENANCE_MARK = ".harness-maintenance"

# Signs of a write in a shell line. A deliberately short heuristic: `Bash` can
# write in a thousand ways and chasing all of them would mean constant false
# positives. It covers the ones that actually show up.
WRITE_TOKENS = (
    ">", ">>", "tee ", "rm ", "mv ", "cp ", "sed -i", "truncate ",
    "Set-Content", "Add-Content", "Out-File", "Remove-Item", "New-Item",
)

# Redirections that cannot write to a file in the repository: discarding output
# and duplicating a descriptor. They carry a `>` and used to trip the check on
# their own, so `... 2>&1` was enough to make a plain read look like a write.
NULL_REDIRECTS = re.compile(r"\d?>>?\s*(?:&\d|/dev/null|NUL\b)", re.IGNORECASE)

# Shell separators. Splitting on them keeps the pairing local: a write operator
# only counts against a protected path when both land in the same piece of the
# command. Without this the two halves only had to appear *somewhere* in the
# same string, and a commit message that quoted a path — or a `>` inside the
# email address of a trailer — was enough to block an ordinary `git commit`.
SEGMENT_SEPARATORS = re.compile(r"[\n;|&]+")

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
    """Returns the protected prefix `path` touches, or None.

    The comparison is case-insensitive because the filesystems this runs on
    mostly are. On NTFS `Scripts/x.py` and `scripts/x.py` are the same file, and
    a case-sensitive check protected only one of the two spellings — which is to
    say it protected neither.
    """
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
    relative = relative.lower()
    for prefix in PROTECTED_ZONE:
        # A bare `scripts` names the directory just as `scripts/` does, and
        # `mv scripts scripts_old` used to slip through on that distinction.
        if relative == prefix or relative == prefix.rstrip("/") or relative.startswith(prefix):
            return prefix
    return None


def _mark_reason() -> str:
    return (
        f"[harness] {MAINTENANCE_MARK} is the switch that disarms this guard, so "
        f"the guard does not let a tool create it: otherwise declaring maintenance "
        f"would cost one write and mean nothing.\n"
        f"If you are maintaining the harness, ask the human to create it from "
        f"their own shell (in Claude Code: `! type nul > {MAINTENANCE_MARK}` on "
        f"Windows, `! touch {MAINTENANCE_MARK}` on POSIX). Deleting it is allowed."
    )


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

    if tool in WRITING_TOOLS:
        target = str(data.get("file_path", ""))
        # The mark is refused BEFORE `in_maintenance()` is consulted, and refused
        # even while maintenance is open. A door the agent can install for itself
        # is not a door: it used to take one allowed `Write` to disarm every
        # protection below, and a second one to remove the evidence.
        # Deleting it only re-arms the guard, so that stays allowed.
        if protected_path(target) == MAINTENANCE_MARK:
            return _block(_mark_reason())
        if in_maintenance():
            return PASS
        prefix = protected_path(target)
        return _block(_reason(prefix)) if prefix else PASS

    if in_maintenance():
        return PASS

    if tool in ("Bash", "PowerShell"):
        command = NULL_REDIRECTS.sub(" ", str(data.get("command", "")).replace("\\", "/"))
        for segment in SEGMENT_SEPARATORS.split(command):
            if not any(token in segment for token in WRITE_TOKENS):
                continue
            for prefix in PROTECTED_ZONE:
                if prefix in segment:
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
