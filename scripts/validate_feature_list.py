"""Validates feature_list.json against the harness rules.

Purpose
    Check that the project scope is in a coherent state before letting a session
    move on: valid statuses, at most one `in_progress` feature, unique ids and
    names, valid priority, correct types and required fields present.

    This module only looks at the SHAPE of the scope. How each feature relates to
    the requirement it comes from (specs/) is checked by
    scripts/validate_requirements.py: one error, one cause.

Why the harness rules are not read from the JSON
    `rules` describes how the harness works, and any agent with write access can
    edit that file. Reading the status vocabulary or the "one feature at a time"
    switch from there turned the rule into a suggestion: widening `valid_status`
    or setting `one_feature_at_a_time: false` was enough. The rules now live in
    the code and what this validator does is check that the JSON **matches**
    them; if somebody changed them, that is an explicit `[FAIL]`.

Who runs it
    `init.ps1` and `init.sh` (section 4). Both call this same module so the
    validation logic is neither duplicated nor drifts apart between Windows and
    POSIX. You can also run it by hand.

Usage
    python scripts/validate_feature_list.py [path]     # defaults to feature_list.json

Output
    One line per check, prefixed [OK] / [FAIL], and when everything is in order,
    which feature comes next according to the work order.

Exit codes
    0  the file is valid
    1  the file is invalid (or could not be read)
"""
from __future__ import annotations

import json
import os
import re
import sys

VALID_STATUS = ("draft", "pending", "in_progress", "done", "blocked")
PRIORITIES = ("critical", "high", "medium", "low")
REQUIRED_FEATURE_KEYS = (
    "id",
    "name",
    "title",
    "description",
    "spec",
    "priority",
    "acceptance",
    "status",
)
NAME_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
SPEC_RE = re.compile(r"^specs/REQ-\d{3}_[a-z0-9]+(?:_[a-z0-9]+)*\.md$")

# Harness rules the JSON may declare but not change.
FIXED_RULES = {
    "one_feature_at_a_time": True,
    "require_tests_to_close": True,
    "work_order": "priority_then_id",
}


def priority_rank(priority: object) -> int:
    """0 is the most critical. An unknown value goes last."""
    try:
        return PRIORITIES.index(str(priority))
    except ValueError:
        return len(PRIORITIES)


def work_order(features: list) -> list:
    """The `pending` features, in the order they should be worked on."""
    pending = [f for f in features if isinstance(f, dict) and f.get("status") == "pending"]
    return sorted(pending, key=lambda f: (priority_rank(f.get("priority")), f.get("id", 0)))


def has_tests(root: str) -> bool:
    """Is there at least one test file? It does not run them: that is the verifier's job."""
    tests_dir = os.path.join(root, "tests")
    if not os.path.isdir(tests_dir):
        return False
    for _folder, _dirs, files in os.walk(tests_dir):
        if any(f.startswith("test") and f.endswith(".py") for f in files):
            return True
    return False


def closing_reports(root: str, name: str) -> list[str]:
    """What a `done` feature is missing to really be closed.

    The cycle says a feature closes after the reviewer's APPROVED, but until now
    no code ever looked at that verdict: writing "done" in the JSON was enough.
    This does not make the review unforgeable — an agent writes the report — but
    it forces the artefact to exist and to land in git, which is what makes it
    auditable afterwards.
    """
    missing: list[str] = []
    impl = os.path.join(root, "progress", f"impl_{name}.md")
    review = os.path.join(root, "progress", f"review_{name}.md")

    if not os.path.isfile(impl):
        missing.append(f"the implementer's report is missing (progress/impl_{name}.md)")

    if not os.path.isfile(review):
        missing.append(f"the reviewer's report is missing (progress/review_{name}.md)")
        return missing

    try:
        with open(review, encoding="utf-8") as handle:
            content = handle.read()
    except OSError as exc:
        missing.append(f"could not read progress/review_{name}.md: {exc}")
        return missing

    if "CHANGES_REQUESTED" in content and "APPROVED" not in content:
        missing.append(f"the reviewer requested changes in progress/review_{name}.md")
    elif "APPROVED" not in content:
        missing.append(f"progress/review_{name}.md does not say APPROVED anywhere")
    return missing


def _validate_rules(rules: object) -> list[str]:
    """Checks that nobody loosened the harness rules from the JSON."""
    errors: list[str] = []
    if not isinstance(rules, dict):
        return ['"rules" must be an object']

    declared = rules.get("valid_status")
    if declared is not None and list(declared) != list(VALID_STATUS):
        errors.append(
            '"rules.valid_status" does not match the harness statuses '
            f"({', '.join(VALID_STATUS)}). Inventing or removing statuses from the "
            "JSON does not change the rules, it only breaks the validation"
        )

    for key, expected in FIXED_RULES.items():
        value = rules.get(key)
        if value is not None and value != expected:
            errors.append(
                f'"rules.{key}" says {value!r} and the harness works with {expected!r}. '
                f"That rule is not switched off by editing the JSON"
            )
    return errors


def _validate_feature(feature: object, index: int, seen_ids: set, seen_names: set) -> list[str]:
    errors: list[str] = []
    if not isinstance(feature, dict):
        return [f"feature #{index} is not an object"]

    label = f"feature {feature.get('id', f'#{index}')}"

    for key in REQUIRED_FEATURE_KEYS:
        if key not in feature:
            errors.append(f'{label}: the "{key}" field is missing')

    feature_id = feature.get("id")
    if "id" in feature and (not isinstance(feature_id, int) or feature_id < 1):
        errors.append(f'{label}: "id" must be an integer >= 1')
    if feature_id in seen_ids:
        errors.append(f"{label}: duplicate id")
    seen_ids.add(feature_id)

    name = feature.get("name")
    if "name" in feature:
        if not isinstance(name, str) or not NAME_RE.match(name):
            errors.append(f'{label}: "name" must be snake_case (it says "{name}")')
        elif name in seen_names:
            # The implementer's and the reviewer's reports are named after the
            # feature's `name`: two identical features overwrite each other's.
            errors.append(f'{label}: duplicate name "{name}"')
        else:
            seen_names.add(name)

    for key in ("title", "description"):
        value = feature.get(key)
        if key in feature and (not isinstance(value, str) or not value.strip()):
            errors.append(f'{label}: "{key}" cannot be empty')

    spec = feature.get("spec")
    if "spec" in feature and (not isinstance(spec, str) or not SPEC_RE.match(spec)):
        errors.append(
            f'{label}: "spec" must be a specs/REQ-00N_name.md path (it says "{spec}")'
        )

    priority = feature.get("priority")
    if "priority" in feature and priority not in PRIORITIES:
        errors.append(
            f'{label}: invalid priority "{priority}" (use: {", ".join(PRIORITIES)})'
        )

    status = feature.get("status")
    if status is not None and status not in VALID_STATUS:
        errors.append(f'{label}: invalid status "{status}"')

    acceptance = feature.get("acceptance")
    if acceptance is not None:
        if not isinstance(acceptance, list) or not acceptance:
            errors.append(f'{label}: "acceptance" must be an array with at least one criterion')
        elif any(not isinstance(c, str) or not c.strip() for c in acceptance):
            errors.append(f'{label}: there are empty or non-text "acceptance" criteria')

    return errors


def validate(path: str) -> list[str]:
    """Returns the list of errors found. Empty means valid."""
    errors: list[str] = []

    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return [f"{path} does not exist"]
    except json.JSONDecodeError as exc:
        return [f"{path} is not valid JSON: {exc}"]

    if not isinstance(data, dict):
        return [f"{path} must contain an object at the root"]

    for key in ("project", "rules", "features"):
        if key not in data:
            errors.append(f'The required "{key}" key is missing')

    errors.extend(_validate_rules(data.get("rules", {})))

    features = data.get("features")
    if features is None:
        return errors
    if not isinstance(features, list):
        return errors + ['"features" must be an array']

    seen_ids: set = set()
    seen_names: set = set()
    for index, feature in enumerate(features):
        errors.extend(_validate_feature(feature, index, seen_ids, seen_names))

    in_progress = [f for f in features if isinstance(f, dict) and f.get("status") == "in_progress"]
    if len(in_progress) > 1:
        names = ", ".join(str(f.get("name", f.get("id"))) for f in in_progress)
        errors.append(f"There are {len(in_progress)} features in_progress (max 1): {names}")

    # require_tests_to_close, made executable: closing a feature without a single
    # test is not "verified", it is "nobody looked". The verifier runs them; here
    # we only check that they exist.
    root = os.path.dirname(os.path.abspath(path))
    closed = [f for f in features if isinstance(f, dict) and f.get("status") == "done"]
    if closed and not has_tests(root):
        errors.append(
            f"there are {len(closed)} feature(s) done and not a single test in tests/: "
            f"a feature does not close without proof (rules.require_tests_to_close)"
        )

    # Nobody approves their own work: closing demands both reports of the cycle.
    for feature in closed:
        name = feature.get("name")
        if not isinstance(name, str) or not name:
            continue
        for problem in closing_reports(root, name):
            errors.append(f"feature {feature.get('id')} {name} is done and {problem}")

    return errors


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else "feature_list.json"
    errors = validate(path)

    if errors:
        for error in errors:
            print(f"[FAIL]  {error}")
        return 1

    with open(path, encoding="utf-8") as handle:
        features = json.load(handle)["features"]
    print(f"[OK]    {path} valid ({len(features)} features)")

    queue = work_order(features)
    if queue:
        following = queue[0]
        print(
            f"[OK]    next: feature {following['id']} {following['name']} "
            f"[{following['priority']}] — {len(queue)} pending"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
