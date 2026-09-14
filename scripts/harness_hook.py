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
    pre-tool-use  BEFORE writing: protects the layer that does the verifying, and
                  keeps each agent inside the scope its own .md declares. It is
                  the only moment a write can be prevented, because the other two
                  hooks arrive once it already happened.

What it can and cannot do
    The typed tools (Write/Edit/MultiEdit/NotebookEdit) are checked by path and
    the check is reliable. Shell commands are checked by shape — a segment that
    names the protected zone has to look like a read — which covers far more than
    the old token list but is still static analysis of a shell, so a path
    assembled from a variable, or a program written into src/ and then run, is
    beyond it. This raises the cost of tampering; it is not a security boundary
    against an agent that has Bash and runs as the same user. Say so plainly
    rather than implying otherwise.

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
import shlex
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

# --- who is writing ---------------------------------------------------------
#
# The scope rules in `.claude/agents/*.md` ("you have Write only for
# progress/current.md", "do not write to any other file") enforced nothing: the
# `tools:` front matter restricts by tool, never by path, and all four agents
# have Bash. This table is the same rules, in the one place that can apply them.
#
# The key is `agent_type` from the hook input, which Claude Code sets and the
# model cannot. Absence of `agent_id` means the main thread — which CLAUDE.md
# defines as the leader for this repository.
AGENT_SCOPES = {
    "leader": ("progress/", "feature_list.json"),
    "implementer": ("src/", "tests/", "progress/", "feature_list.json"),
    "reviewer": ("progress/",),
    "analyst": ("specs/", "docs/architecture.md", "progress/", "feature_list.json"),
}

# Working material: legitimate for the role that owns it, off-limits to the
# others. Kept apart from PROTECTED_ZONE, which nobody writes during a session.
SCOPED_ZONE = (
    "src/",
    "tests/",
    "specs/",
    "progress/",
    "docs/architecture.md",
    "feature_list.json",
)

# --- the shell matcher ------------------------------------------------------
#
# This used to be a deny-list: "a write token AND a protected path in the same
# segment". The tokens were `>`, `rm `, `mv `, `sed -i` and a handful more, and
# the audit walked straight past it sixteen different ways — `python -c`, a
# heredoc into any interpreter, `install`, `dd`, `patch`, `git checkout HEAD~5
# -- scripts/`, `git restore`, `git apply`, `ln -sf`, `perl -pi -e`,
# `sed --in-place`, `find -exec truncate`, `cd scripts && echo x > f`, paths
# built from variables. Each fix would have added one more token, and the next
# way of writing would have walked past the new list too.
#
# So the question is inverted. A segment that names a protected path has to look
# like a READ to be allowed; anything else is refused. The unknown verb is now
# the blocked case rather than the allowed one.
#
# The authors' objection to this — "chasing every way of writing from Bash would
# mean constant false positives" — is answered by *when* the allow-list applies:
# only to segments that name a protected path. Ordinary work (`pytest tests/`,
# `git commit`, `npm test`, `python src/app.py`) never mentions `scripts/` or
# `AGENTS.md`, is never examined, and cannot be blocked by any of this.

# Verbs that only read. Anything here is allowed to name a protected path.
READ_ONLY_VERBS = frozenset({
    # POSIX reads
    "cat", "head", "tail", "less", "more", "ls", "stat", "file", "wc", "du",
    "sort", "uniq", "cut", "tr", "diff", "comm", "md5sum", "sha256sum", "echo",
    "printf", "test", "which", "type", "tree", "realpath", "basename", "dirname",
    "grep", "egrep", "fgrep", "rg", "pwd", "env", "date",
    # PowerShell reads
    "get-content", "get-childitem", "get-item", "get-itemproperty",
    "select-string", "test-path", "resolve-path", "compare-object",
    "measure-object", "select-object", "where-object", "sort-object",
    "format-table", "format-list", "write-host", "write-output", "get-help",
    "get-command", "gc", "gci", "sls", "dir",
})

# Verbs that read only if they are not asked to do otherwise. The flags that
# turn each one into a writer are listed next to it.
CONDITIONAL_VERBS = {
    "find": ("-exec", "-execdir", "-delete", "-ok", "-okdir", "-fprint", "-fls"),
    "sed": ("-i", "--in-place", "-i.bak", "--in-place=", "-i'"),
    "awk": ("-i", "inplace"),
    "gawk": ("-i", "inplace"),
}

# git is not one verb but two dozen, and the split is not cosmetic: `git log`
# cannot touch the working tree and `git checkout -- scripts/` replaces it
# wholesale with an older, weaker validator while looking innocuous in a
# transcript. `add` and `commit` stay on the read side because neither alters
# file *content* — and keeping them there is what preserves the fix for the
# false positive that used to block an ordinary `git commit`.
GIT_READ_ONLY = frozenset({
    "status", "log", "diff", "show", "blame", "ls-files", "ls-tree", "rev-parse",
    "rev-list", "describe", "cat-file", "grep", "remote", "shortlog", "branch",
    "tag", "fetch", "config", "add", "commit", "push",
})

# Interpreter flags that carry code in the command line, where no path analysis
# can see what the code does. `python -c "open('scripts/x.py','w')"` was the
# cleanest bypass in the audit.
INLINE_CODE_FLAGS = ("-c", "-e", "-e'", '-e"', "--eval", "-command", "-encodedcommand")
INTERPRETERS = frozenset({
    "python", "python3", "py", "perl", "ruby", "node", "sh", "bash", "zsh",
    "powershell", "pwsh", "php", "deno",
})

# Prefixes that wrap a real command without being one.
COMMAND_PREFIXES = frozenset({"sudo", "nohup", "time", "command", "exec", "&"})
ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

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

# Set HARNESS_HOOK_AUDIT=1 to see what the matcher WOULD block without blocking
# it. A guard that is switched on blind is a guard that gets ripped out a week
# later; this is how you find out what it costs before paying it.
AUDIT_ENV = "HARNESS_HOOK_AUDIT"


def caller_role(hook_input: dict) -> str | None:
    """Which agent is making this call, or None if it cannot be told.

    None matters: it means *do not enforce scopes*, not "assume the strictest".
    These fields come from Claude Code, so a version that stops sending them
    would otherwise turn every write in the repository into a block. Degrading
    to the previous behaviour is the only safe direction for a guard built on a
    field somebody else owns.
    """
    agent_type = hook_input.get("agent_type")
    if isinstance(agent_type, str) and agent_type in AGENT_SCOPES:
        return agent_type
    if agent_type is None and hook_input.get("agent_id") is None:
        # No subagent in sight: the main thread, which CLAUDE.md makes the leader.
        # Only trusted when the payload carries the surrounding session fields —
        # an empty dict means we were run by hand or by an older version, and
        # guessing "leader" from nothing would block an implementer's own code.
        if "session_id" in hook_input or "cwd" in hook_input:
            return "leader"
    return None


def scoped_path(path: str) -> str | None:
    """The SCOPED_ZONE prefix this path falls under, or None."""
    if not path:
        return None
    normalized = path.replace("\\", "/")
    absolute = normalized if os.path.isabs(normalized) else os.path.join(REPO_ROOT, normalized)
    try:
        relative = os.path.relpath(os.path.abspath(absolute), REPO_ROOT).replace("\\", "/")
    except ValueError:
        relative = normalized
    if relative.startswith(".."):
        return None
    relative = relative.lower()
    for prefix in SCOPED_ZONE:
        if relative == prefix.rstrip("/") or relative.startswith(prefix) or relative == prefix:
            return prefix
    return None


def scope_violation(role: str, prefix: str) -> bool:
    """Is `prefix` outside what `role` is allowed to write?"""
    return prefix not in AGENT_SCOPES.get(role, ())


def _scope_reason(role: str, target: str, prefix: str) -> str:
    allowed = ", ".join(AGENT_SCOPES[role]) or "nothing here"
    return (
        f"[harness] you are the `{role}`, and {prefix} is not yours to write "
        f"({target}).\n"
        f"Your scope is: {allowed}.\n"
        f"This is the rule your own agent file states; it is enforced here "
        f"because prose in a .md enforces nothing. If the work really belongs to "
        f"another role, that is the role that should be doing it."
    )


def mentions_protected(segment: str) -> str | None:
    """The protected prefix this segment names, or None.

    Matches both `scripts/` and a bare `scripts` at a word boundary: the bare
    form is how `mv scripts scripts_old` used to walk off with the validators.
    """
    lowered = segment.replace("\\", "/").lower()
    for prefix in PROTECTED_ZONE:
        bare = prefix.rstrip("/")
        if re.search(rf"(?<![\w./-]){re.escape(bare)}(?![\w-])", lowered):
            return prefix
    return None


def _words(segment: str) -> list[str]:
    try:
        return shlex.split(segment, posix=False)
    except ValueError:  # an unbalanced quote — treat it as opaque, not as safe
        return segment.split()


def read_only_shape(segment: str) -> str | None:
    """None if the segment only reads; otherwise why it does not.

    Only ever consulted for segments that name a protected path.
    """
    scrubbed = NULL_REDIRECTS.sub(" ", segment)
    if ">" in scrubbed:
        return "it redirects output into a file"

    words = [w for w in _words(scrubbed) if w]
    while words:
        head = words[0]
        if head.lower() in COMMAND_PREFIXES or ENV_ASSIGNMENT_RE.match(head):
            words.pop(0)
            continue
        break
    if not words:
        return None

    verb = os.path.basename(words[0].replace("\\", "/")).lower()
    verb = verb[:-4] if verb.endswith(".exe") else verb
    rest = [w.lower() for w in words[1:]]

    if verb in INTERPRETERS and any(flag in rest for flag in INLINE_CODE_FLAGS):
        return f"`{verb}` is being handed code on the command line, and no path check can read what that code does"

    if verb == "cd":
        # `cd scripts && echo x > f` splits into two segments, and the one that
        # writes names no protected path. The shell is also persistent across
        # tool calls, so a `cd` can taint a later command no per-command
        # analysis will ever see. Refusing the `cd` is cheaper than modelling it.
        return "it changes directory into the protected zone — work from the repository root instead"

    if verb == "git":
        sub = rest[0] if rest else ""
        if sub not in GIT_READ_ONLY:
            return f"`git {sub}` can rewrite the working tree"
        return None

    if verb in CONDITIONAL_VERBS:
        for flag in CONDITIONAL_VERBS[verb]:
            if any(word.startswith(flag) for word in rest):
                return f"`{verb} {flag}` writes"
        return None

    if verb in READ_ONLY_VERBS:
        return None

    if verb in INTERPRETERS:
        # Running a script file is how the validators are invoked; it is the
        # inline-code form, handled above, that cannot be checked.
        return None

    if verb in ("pytest", "unittest"):
        return None

    if verb.startswith("./") or verb in ("init.sh", "init.ps1"):
        return None

    return f"`{verb}` is not a known read-only command"


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
        if prefix:
            return _block(_reason(prefix))

        role = caller_role(hook_input)
        scoped = scoped_path(target)
        if role and scoped and scope_violation(role, scoped):
            message = _scope_reason(role, target, scoped)
            if os.environ.get(AUDIT_ENV):
                print(f"[harness][audit] would block: {role} writing {scoped}")
                return PASS
            return _block(message)
        return PASS

    if in_maintenance():
        return PASS

    if tool in ("Bash", "PowerShell"):
        verdict = inspect_command(str(data.get("command", "")))
        if verdict is None:
            return PASS
        prefix, why = verdict
        message = _shell_reason(prefix, why)
        if os.environ.get(AUDIT_ENV):
            # Audit mode: say what would have happened, change nothing.
            print(f"[harness][audit] would block ({why}): {prefix}")
            return PASS
        return _block(message)

    return PASS


def inspect_command(raw: str) -> tuple[str, str] | None:
    """(protected prefix, why it is not a read) for the first offending part.

    None means nothing in this command names the protected zone, or everything
    that does only reads it.
    """
    # Scrubbed before splitting, not after: `&` is one of the segment
    # separators, so `2>&1` was being torn into a dangling `2>` and a stray `1`,
    # and the dangling half read as a redirection into a file.
    command = NULL_REDIRECTS.sub(" ", raw.replace("\\", "/"))

    # Heredocs are checked against the whole command, not per segment: the body
    # does not respect `;` or `&&`, so splitting first is exactly how
    # `python - <<EOF ... open("scripts/x.py","w") ... EOF` got through.
    if "<<" in command:
        prefix = mentions_protected(command)
        if prefix:
            return prefix, "a heredoc feeds text to a command, and the guard cannot read what it does with it"

    for segment in SEGMENT_SEPARATORS.split(command):
        prefix = mentions_protected(segment)
        if not prefix:
            continue
        # Closing the maintenance door is always allowed — that is the whole
        # asymmetry: the agent cannot open it and should be able to shut it. A
        # guard that traps the session inside maintenance has it backwards.
        if prefix == MAINTENANCE_MARK and closes_maintenance(segment):
            continue
        why = read_only_shape(segment)
        if why:
            return prefix, why
    return None


DELETE_VERBS = frozenset({"rm", "del", "erase", "unlink", "remove-item", "ri"})


def closes_maintenance(segment: str) -> bool:
    """Is this segment deleting the maintenance mark and nothing else?"""
    words = [w for w in _words(segment) if w and not w.startswith("-")]
    if not words:
        return False
    verb = os.path.basename(words[0].replace("\\", "/")).lower()
    if verb not in DELETE_VERBS:
        return False
    targets = [w.strip("\"'").replace("\\", "/").lower() for w in words[1:]]
    # `lstrip("./")` would eat the leading dot of `.harness-maintenance` itself.
    targets = [t[2:] if t.startswith("./") else t for t in targets]
    return bool(targets) and all(t == MAINTENANCE_MARK for t in targets)


def _shell_reason(target: str, why: str) -> str:
    return (
        f"[harness] this command names {target}, part of the layer that verifies "
        f"the work, and {why}.\n"
        f"That layer is not touched during a development session: an agent that "
        f"sees red does not fix the red by editing the validator.\n"
        f"If you only meant to read it, say it with a read: cat, head, grep, ls, "
        f"git log/diff/show, or running one of the validators. If you really are "
        f"maintaining the harness, ask the human to create the {MAINTENANCE_MARK} "
        f"file at the root."
    )


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
