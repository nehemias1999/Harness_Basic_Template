"""Validates the feature notes in features/ against the harness rules.

Purpose
    Check that the project scope is in a coherent state before letting a session
    move on: valid statuses, at most one `in_progress` feature, unique ids and
    names, valid priority, correct types and required fields present.

    This module only looks at the SHAPE of the scope. How each feature relates to
    the requirement it comes from (specs/) is checked by
    scripts/validate_requirements.py: one error, one cause.

Where the features live
    One note per feature, `features/F-<id>_<name>.md`, with flat front matter
    plus two list-valued keys (`acceptance`, `tags`) and a `spec` wikilink to
    `specs/`. The template notes (`features/_project.md`, `features/_template.md`)
    start with `_` and are not features. Reading and writing the notes is done
    through scripts/features_io.py, so the validator, the approver and the
    bootstrap never drift apart on the shape of the file.

Why the harness rules are not configuration
    The template's `features/_project.md` used to be `feature_list.json`, and the
    file carried a `rules` block. Reading the status vocabulary or the
    "one feature at a time" switch from there turned the rule into a suggestion:
    widening `valid_status` or setting `one_feature_at_a_time: false` was enough.
    The rules now live in the code, and nothing in the notes can switch them off.

Who runs it
    `init.ps1` and `init.sh` (section 4). Both call this same module so the
    validation logic is neither duplicated nor drifts apart between Windows and
    POSIX. You can also run it by hand.

Usage
    python scripts/validate_features.py [root]     # defaults to the current dir

Output
    One line per check, prefixed [OK] / [FAIL], and when everything is in order,
    which feature comes next according to the work order.

Exit codes
    0  the scope is valid
    1  the scope is invalid (or features/ could not be read)
"""
from __future__ import annotations

import os
import re
import sys

import features_io
from features_io import FEATURE_FILE_RE, spec_basename

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
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# A note may only use lists for these keys; a scalar (`key: value`) elsewhere.
LIST_KEYS = ("acceptance", "tags")


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


VERDICT_LINE_RE = re.compile(r"^[ \t]*\**[ \t]*verdict[ \t]*\**[ \t]*:(.*)$", re.IGNORECASE | re.MULTILINE)
VERDICTS = ("APPROVED", "CHANGES_REQUESTED")


def read_verdict(content: str) -> str | None:
    """The reviewer's verdict, or None if the report does not state one.

    Substring containment was not good enough, and not only against bad faith.
    The template in `.claude/agents/reviewer.md` hands the reviewer the line
    `**Verdict:** APPROVED | CHANGES_REQUESTED`; a report that kept the legend
    contained both words, and "APPROVED is in there somewhere" read it as an
    approval. So did the phrase "this is NOT APPROVED".

    The verdict is now a line that has to pick one. If the report states both, or
    states neither, that is not an approval — it is a report to go back and
    finish.
    """
    found: set[str] = set()
    for match in VERDICT_LINE_RE.finditer(content):
        rest = match.group(1).upper()
        # "APPROVED" is not a substring of "CHANGES_REQUESTED", so a line naming
        # both really is naming both — the unedited legend.
        on_line = {verdict for verdict in VERDICTS if verdict in rest}
        if len(on_line) != 1:
            return None
        found |= on_line
    if len(found) != 1:
        return None
    return found.pop()


def closing_reports(root: str, name: str) -> list[str]:
    """What a `done` feature is missing to really be closed.

    The cycle says a feature closes after the reviewer's APPROVED, but until now
    no code ever looked at that verdict: writing "done" in a note was enough.
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

    verdict = read_verdict(content)
    if verdict is None:
        missing.append(
            f"progress/review_{name}.md has no readable verdict line "
            f'(expected one "**Verdict:** APPROVED" or "**Verdict:** CHANGES_REQUESTED")'
        )
    elif verdict != "APPROVED":
        missing.append(f"the reviewer requested changes in progress/review_{name}.md")
    return missing


def _validate_note(feature: dict, seen_ids: set, seen_names: set) -> list[str]:
    errors: list[str] = []
    label = f"feature {feature['id']} {feature['name']}"
    fields = {key: value for key, value in feature.items() if not key.startswith("_")}

    # The file name is the authority on id and name: F-<id>_<name>.md. The note
    # may repeat them, and when it does they have to agree.
    declared_id = fields.get("id")
    if declared_id is not None:
        id_matches = (
            str(declared_id).strip().isdigit()
            and int(str(declared_id).strip()) == feature["id"]
        )
        if not id_matches:
            errors.append(
                f'{label}: "id" says "{declared_id}" and the file name says '
                f'{feature["id"]} (F-<id>_<name>.md). Keep one truth'
            )

    declared_name = fields.get("name")
    if declared_name is not None and str(declared_name) != feature["name"]:
        errors.append(
            f'{label}: "name" says "{declared_name}" and the file name says '
            f'"{feature["name"]}". The implementer\'s and the reviewer\'s reports '
            f"are named after the feature, so one of the two has to give"
        )

    for key in REQUIRED_FEATURE_KEYS:
        if key not in fields or fields[key] in ("", [], None):
            if key in ("id", "name"):
                continue  # always present, derived from the file name
            errors.append(f'{label}: the "{key}" field is missing')

    if feature["id"] in seen_ids:
        errors.append(f"{label}: duplicate id")
    seen_ids.add(feature["id"])

    if feature["name"] in seen_names:
        # The implementer's and the reviewer's reports are named after the
        # feature's `name`: two identical features overwrite each other's.
        errors.append(f'{label}: duplicate name "{feature["name"]}"')
    else:
        seen_names.add(feature["name"])

    for key in ("title", "description"):
        value = fields.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(f'{label}: "{key}" cannot be empty')

    spec = fields.get("spec")
    if spec is not None and spec_basename(spec) is None:
        errors.append(
            f'{label}: "spec" must be a specs/REQ-00N_name.md path or a '
            f"[[REQ-00N_name]] wikilink (it says \"{spec}\")"
        )

    priority = fields.get("priority")
    if priority is not None and priority not in PRIORITIES:
        errors.append(
            f'{label}: invalid priority "{priority}" (use: {", ".join(PRIORITIES)})'
        )

    status = fields.get("status")
    if status is not None and status not in VALID_STATUS:
        errors.append(f'{label}: invalid status "{status}"')

    acceptance = fields.get("acceptance")
    if acceptance is not None:
        if not isinstance(acceptance, list) or not acceptance:
            errors.append(f'{label}: "acceptance" must be an array with at least one criterion')
        elif any(not isinstance(c, str) or not c.strip() for c in acceptance):
            errors.append(f'{label}: there are empty or non-text "acceptance" criteria')

    for key in ("created", "updated"):
        value = fields.get(key)
        if value is not None and not DATE_RE.match(str(value)):
            errors.append(f'{label}: "{key}" says "{value}" and it has to be a YYYY-MM-DD date')

    tags = fields.get("tags")
    if tags is not None and (not isinstance(tags, list) or any(not isinstance(t, str) for t in tags)):
        errors.append(f'{label}: "tags" must be a list of text')

    non_lists = [key for key in fields if isinstance(fields[key], list) and key not in LIST_KEYS]
    for key in non_lists:
        errors.append(
            f'{label}: "{key}" is written as a list, and a feature note only '
            f"allows lists for {', '.join(LIST_KEYS)}"
        )

    return errors


def validate(root: str) -> list[str]:
    """Returns the list of errors found. Empty means valid."""
    features, load_errors = features_io.load_features(root)
    errors: list[str] = list(load_errors)

    features_dir = os.path.join(root, features_io.FEATURE_DIR)
    if not os.path.isdir(features_dir):
        errors.append(
            "features/ does not exist yet: the scope lives in one note per "
            "feature (features/F-<id>_<name>.md)"
        )
        return errors

    non_notes = [
        name for name in sorted(os.listdir(features_dir))
        if name.endswith(".md") and not name.startswith("_") and not FEATURE_FILE_RE.match(name)
    ]
    for name in non_notes:
        errors.append(
            f"features/{name}: the file name does not follow F-<id>_<name>.md "
            f"(an underscore-prefixed file is a template note, not a feature)"
        )

    seen_ids: set = set()
    seen_names: set = set()
    for feature in features:
        errors.extend(_validate_note(feature, seen_ids, seen_names))

    in_progress = [f for f in features if f.get("status") == "in_progress"]
    if len(in_progress) > 1:
        names = ", ".join(str(f.get("name", f.get("id"))) for f in in_progress)
        errors.append(f"There are {len(in_progress)} features in_progress (max 1): {names}")

    # require_tests_to_close, made executable: closing a feature without a single
    # test is not "verified", it is "nobody looked". The verifier runs them; here
    # we only check that they exist.
    closed = [f for f in features if f.get("status") == "done"]
    if closed and not has_tests(root):
        errors.append(
            f"there are {len(closed)} feature(s) done and not a single test in tests/: "
            f"a feature does not close without proof (require_tests_to_close)"
        )

    # Nobody approves their own work: closing demands both reports of the cycle.
    for feature in closed:
        name = feature.get("name")
        if not isinstance(name, str) or not name:
            continue
        for problem in closing_reports(root, name):
            errors.append(f"feature {feature['id']} {name} is done and {problem}")

    return errors


def main(argv: list[str]) -> int:
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    errors = validate(root)

    if errors:
        for error in errors:
            print(f"[FAIL]  {error}")
        return 1

    import features_io

    features, _ = features_io.load_features(root)
    print(f"[OK]    features valid ({len(features)} features)")

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