"""Checks the project is configured before letting anyone work on it.

Purpose
    An unconfigured harness is worse than no harness: the reviewer approves
    against `docs/architecture.md`, so if that file is still full of
    placeholders there are no quality criteria and any code that passes the
    tests counts as good. This validator blocks the session until the
    essentials are in place.

What it blocks (`[FAIL]`)
    - `feature_list.json` still carrying the `project` placeholder.
    - `docs/architecture.md` unfilled (`<...>` placeholders or the template note
      still there) **if there is already a feature outside `draft`**.
    - `README.md` with unreplaced placeholders.

Why the architecture only blocks sometimes
    The draft of `docs/architecture.md` is written by the `analyst` agent and
    you approve it by removing its template note. While every feature is still
    in `draft` nobody is programming, so an unapproved draft is a `[WARN]`: if
    it were a `[FAIL]`, the whole analysis phase would run red and red would
    stop meaning anything. As soon as a feature leaves `draft` it blocks again,
    which is when it matters: the reviewer needs criteria exactly when there is
    code to judge.

What it only warns about (`[WARN]`)
    - `docs/architecture.md` still a draft while everything is in `draft`.
    - `description` not filled in.
    - `feature_list.json` with no features.
    - `src/` with no modules yet.

Special case
    If NOTHING is configured, the repository is the freshly copied template:
    instead of spitting out every failure, it says what to run (`bootstrap.ps1`).

Who runs it
    `init.ps1` and `init.sh` (section 3). Both use this same module so the rules
    do not drift apart between Windows and POSIX.

Usage
    python scripts/validate_project_setup.py [repo_root]

Exit codes
    0  configured (warnings do not block)
    1  essential configuration is missing
"""
from __future__ import annotations

import json
import os
import re
import sys

PROJECT_PLACEHOLDER = "<YOUR_PROJECT>"
DESCRIPTION_PLACEHOLDER = "<PROJECT_DESCRIPTION>"
TEMPLATE_MARKER = "This file is a template"

# A placeholder is a token between angle brackets with no odd spacing:
# <module_1>, <YOUR_PROJECT>, <layer>. HTML comments and arrows do not count.
PLACEHOLDER_RE = re.compile(r"<[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_ .-]{0,40}>")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def find_placeholders(text: str) -> list[str]:
    """The document's placeholders, ignoring the helper HTML comments."""
    return sorted(set(PLACEHOLDER_RE.findall(HTML_COMMENT_RE.sub("", text))))


def check(root: str) -> tuple[list[str], list[str], bool]:
    """Returns (failures, warnings, is_uninstantiated_template)."""
    fails: list[str] = []
    warns: list[str] = []

    def path(*parts: str) -> str:
        return os.path.join(root, *parts)

    # --- feature_list.json --------------------------------------------------
    project_unset = False
    features_empty = False
    try:
        data = json.loads(_read(path("feature_list.json")))
    except (OSError, json.JSONDecodeError) as exc:
        fails.append(f"Could not read feature_list.json: {exc}")
        data = {}

    project = str(data.get("project", "")).strip()
    if not project or project == PROJECT_PLACEHOLDER:
        project_unset = True
        fails.append(
            f'feature_list.json: "project" is still unset (it says "{project or ""}")'
        )
    else:
        description = str(data.get("description", "")).strip()
        if not description or description.startswith("<"):
            warns.append('feature_list.json: "description" is not filled in')

    features = data.get("features")
    if isinstance(features, list) and not features:
        features_empty = True
        warns.append("feature_list.json: no feature has been defined yet")

    # --- docs/architecture.md ----------------------------------------------
    architecture_unset = False
    try:
        architecture = _read(path("docs", "architecture.md"))
    except OSError as exc:
        fails.append(f"Could not read docs/architecture.md: {exc}")
        architecture = ""

    architecture_issues: list[str] = []
    if architecture:
        placeholders = find_placeholders(architecture)
        if TEMPLATE_MARKER in architecture:
            architecture_unset = True
            architecture_issues.append(
                "docs/architecture.md is still the unfilled template. "
                "Read it and approve it: python scripts/approve.py architecture"
            )
        if placeholders:
            architecture_unset = True
            shown = ", ".join(placeholders[:6])
            extra = f" (and {len(placeholders) - 6} more)" if len(placeholders) > 6 else ""
            architecture_issues.append(
                f"docs/architecture.md has unfilled placeholders: {shown}{extra}"
            )

    # An unapproved architecture only blocks once there is real work: if
    # everything is still in `draft` we are in the analysis phase and the red
    # would be noise.
    work_started = any(
        isinstance(f, dict) and f.get("status") not in (None, "draft")
        for f in (features if isinstance(features, list) else [])
    )
    if architecture_issues:
        if work_started:
            fails.extend(architecture_issues)
        else:
            warns.extend(architecture_issues)
            warns.append(
                "docs/architecture.md is an unapproved draft; it does not block yet "
                "because no feature has left draft"
            )

    # --- README.md ----------------------------------------------------------
    try:
        readme = _read(path("README.md"))
    except OSError as exc:
        fails.append(f"Could not read README.md: {exc}")
        readme = ""

    for placeholder in (PROJECT_PLACEHOLDER, DESCRIPTION_PLACEHOLDER):
        if placeholder in readme:
            fails.append(f"README.md still contains {placeholder}")

    # --- src/ ---------------------------------------------------------------
    src_dir = path("src")
    modules: list[str] = []
    if os.path.isdir(src_dir):
        modules = [f for f in os.listdir(src_dir) if f.endswith(".py") and f != "__init__.py"]
    if not modules:
        warns.append("src/ has no modules yet")

    pristine = project_unset and architecture_unset and features_empty and not modules
    return fails, warns, pristine


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "."
    fails, warns, pristine = check(root)

    if pristine:
        print("[FAIL]  This repository is the harness template, NOT INSTANTIATED.")
        print("[FAIL]  You cannot work on a project that does not exist yet.")
        print("")
        print("        Instantiate it and run the verifier again:")
        print("")
        print('          ./bootstrap.ps1 -Name "my-project" -Description "What it does."')
        print('          ./bootstrap.sh --name "my-project" --description "What it does."')
        print("")
        print("        Then hand it your requirements in plain language (/requirements):")
        print("        the analyst leaves them in specs/ and drafts docs/architecture.md,")
        print("        and you approve them. See README.md § Quick start.")
        return 1

    for warn in warns:
        print(f"[WARN]  {warn}")
    for fail in fails:
        print(f"[FAIL]  {fail}")

    if fails:
        print("[FAIL]  Configuration is incomplete: sort it out before working.")
        return 1

    print("[OK]    Project configured")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
