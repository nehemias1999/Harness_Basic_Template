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
)

PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py|ps1|sh|json|yml|yaml))`")

# A bare name in prose ("...and `history.md` stays append-only") or in a table
# of examples is not a path.
NO_FOLDER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# `requirements.txt` shows up in CHECKPOINTS.md as something that must NOT exist.
IGNORED = {"requirements.txt"}


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
            if NO_FOLDER_RE.match(mention):
                continue
            if os.path.exists(os.path.join(root, mention)):
                continue
            failures.append(f"{document} mentions `{mention}`, which does not exist")

    # Each feature's pointer to its requirement.
    try:
        data = json.loads(_read(os.path.join(root, "feature_list.json")))
    except (OSError, json.JSONDecodeError):
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
