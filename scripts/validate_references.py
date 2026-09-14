"""Checks the harness does not point at files that do not exist.

Purpose
    `CHECKPOINTS.md` C1 asks that every path mentioned in the documentation
    really exists. Until now that was prose: nobody checked it, and a dangling
    reference is especially expensive in this repository because the documents
    are the map agents navigate by. An agent that looks for a script
    because `AGENTS.md` mentions it, and does not find it, improvises.

What it looks at
    Backtick-quoted paths in the reference documents, and the `spec` field of
    every feature in `feature_list.json`.

    Only mentions **with a folder** count (`scripts/x.py`, `.claude/agents/y.md`).
    A bare name — `storage.py` in a naming-conventions table, `history.md` in the
    middle of a sentence — is an example or an abbreviation, not a path, and
    chasing those filled the output with noise until nobody read it. Examples
    with placeholders (`progress/impl_<f>.md`) are ignored too, and so is
    `requirements.txt`, which is precisely what must not exist.

Who runs it
    `/harness-check` and CI. **Not** the verifier: a broken reference is
    documentation debt, not a reason to stop a working session.

Usage
    python scripts/validate_references.py [repo_root]

Exit codes
    0  no dangling references
    1  at least one
"""
from __future__ import annotations

import json
import os
import re
import sys

DOCUMENTS = (
    "CLAUDE.md",
    "AGENTS.md",
    "README.md",
    "CHECKPOINTS.md",
    "docs/scripts.md",
    "docs/architecture.md",
    "docs/conventions.md",
    "docs/verification.md",
    # The files subagents actually navigate by. They were missing, which is odd
    # for a check whose whole point is that agents improvise when the map lies.
    ".claude/agents/leader.md",
    ".claude/agents/analyst.md",
    ".claude/agents/implementer.md",
    ".claude/agents/reviewer.md",
    ".claude/commands/requirements.md",
    ".claude/commands/approve.md",
    ".claude/commands/approve-all.md",
    ".claude/commands/next-feature.md",
    ".claude/commands/close-session.md",
    ".claude/commands/harness-check.md",
)

PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py|ps1|sh|json|yml|yaml))`")

# A bare name in prose ("...and `history.md` stays append-only") or in a table
# of examples is not a path.
NO_FOLDER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# …with one exception: the harness's own root-level files. Skipping every mention
# without a `/` meant `init.sh`, `bootstrap.ps1`, `reset.sh` and `AGENTS.md` — the
# entry points the documentation sends agents to — were the only files the
# validator structurally could not check, while CHECKPOINTS.md C1 claimed every
# mentioned path was verified.
ROOT_FILES = frozenset({
    "AGENTS.md",
    "CLAUDE.md",
    "CHECKPOINTS.md",
    "README.md",
    "feature_list.json",
    "init.ps1",
    "init.sh",
    "bootstrap.ps1",
    "bootstrap.sh",
    "reset.ps1",
    "reset.sh",
})

# `requirements.txt` shows up in CHECKPOINTS.md as something that must NOT exist.
IGNORED = {"requirements.txt"}

# Session artefacts. A mention of `progress/impl_storage.md` is a naming
# convention being explained, not a map reference: those files are written during
# a session and a fresh template has none of them. Only the two files that ship
# with the template are real references.
TRANSIENT_DIR = "progress/"
PERMANENT_PROGRESS = {"progress/current.md", "progress/history.md"}


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def check(root: str) -> list[str]:
    failures: list[str] = []

    for document in DOCUMENTS:
        doc_path = os.path.join(root, document)
        if not os.path.isfile(doc_path):
            failures.append(f"{document}: does not exist, and it is a reference document")
            continue

        for mention in sorted(set(PATH_RE.findall(_read(doc_path)))):
            if mention in IGNORED or "<" in mention:
                continue
            if NO_FOLDER_RE.match(mention) and mention not in ROOT_FILES:
                continue
            if mention.startswith(TRANSIENT_DIR) and mention not in PERMANENT_PROGRESS:
                continue
            if os.path.exists(os.path.join(root, mention)):
                continue
            failures.append(f"{document} mentions `{mention}`, which does not exist")

    # Each feature's pointer to its requirement.
    try:
        data = json.loads(_read(os.path.join(root, "feature_list.json")))
    except (OSError, json.JSONDecodeError) as exc:
        # Reported, not swallowed. This used to `return failures`, so an
        # unreadable feature_list.json printed "[OK] no dangling references"
        # while half the check had silently not run — a validator that says
        # nothing is wrong when it could not look is worse than no validator.
        failures.append(
            f"feature_list.json cannot be read ({exc}), so no feature -> spec "
            f"pointer could be checked"
        )
        return failures

    for feature in data.get("features") or []:
        if not isinstance(feature, dict):
            continue
        spec = feature.get("spec")
        if spec and not os.path.exists(os.path.join(root, spec)):
            failures.append(f"feature {feature.get('id')} points at `{spec}`, which does not exist")

    return failures


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "."
    failures = check(root)

    for failure in failures:
        print(f"[FAIL]  {failure}")
    if failures:
        print("[FAIL]  There are dangling references: a map that lies is worse")
        print("        than no map at all.")
        return 1

    print(f"[OK]    {len(DOCUMENTS)} documents checked, no dangling references")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
