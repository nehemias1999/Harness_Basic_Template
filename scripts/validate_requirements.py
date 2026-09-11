"""Checks that nobody is working on a requirement nobody approved.

Purpose
    Approving a requirement is not a "sure, go ahead" in the chat: it is
    `status: approved` in the front matter of `specs/REQ-00N_*.md`, versioned in
    git, plus its features moving from `draft` to `pending`. This validator
    checks that both halves agree, and blocks the session if someone moved ahead
    on a requirement that is still under analysis.

    It is the counterpart of the harness's other gate: `validate_project_setup.py`
    demands that quality criteria exist, this one demands that approved scope
    exists.

What it blocks (`[FAIL]`)
    - A feature whose `status` is anything but `draft` hanging off a spec that
      is not approved. "Anything but draft" is evaluated by complement:
      inventing a new status is not a way out of the gate.
    - There is code under `src/` (recursively, any language) and no approved
      requirement: somebody started programming before deciding what to build.
    - A feature with no `spec` field, or pointing at a file that does not exist.
    - An approved spec with unanswered open questions (`- [ ]`): the "assume
      nothing" rule, made executable.
    - An approved spec with no `approved_on`, with a date that is not YYYY-MM-DD,
      or with no feature referencing it.
    - An approved spec with no `approved_hash`, or whose content changed after it
      was approved. Without that fingerprint, "approved" only means somebody
      typed the word: editing the criteria afterwards left no trace.
    - Front matter with repeated keys, or an `id` that does not match the file
      name (that spec is not loaded).
    - A feature with a HIGHER priority than its requirement. Lowering it is legal
      (an accessory part); raising it is a silent contradiction.
    - A file name outside `REQ-00N_snake_case_name.md`, a duplicate `id`, or an
      invalid `status` or `priority`.

What it only warns about (`[WARN]`)
    - `specs/` does not exist yet, or there are no requirements.
    - There are requirements in `draft` waiting for the human's OK.
    - An approved spec whose features are all still in `draft` (half-finished
      approval: `/approve` did not run to the end).
    - A `discarded` spec that still has features in `draft` hanging off it.
    - A feature is `in_progress` with lower priority than something queued. The
      harness flags the overtake; deciding whether to interrupt is the human's.

Who runs it
    `init.ps1` and `init.sh` (section 5). Both use this same module so the rules
    cannot drift apart between Windows and POSIX. Also by hand.

Usage
    python scripts/validate_requirements.py [repo_root]
    python scripts/validate_requirements.py --fingerprint specs/REQ-001_x.md

    The second form prints a spec's content fingerprint: it is what `/approve`
    writes into `approved_hash` when it signs it.

Exit codes
    0  requirement -> feature traceability is coherent (warnings do not block)
    1  there is work on something unapproved, or traceability is broken
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

SPEC_DIR = "specs"
SPEC_FILE_RE = re.compile(r"^REQ-(\d{3})_[a-z0-9]+(?:_[a-z0-9]+)*\.md$")
SPEC_POINTER_RE = re.compile(r"^specs/REQ-\d{3}_[a-z0-9]+(?:_[a-z0-9]+)*\.md$")
# An unanswered question is any empty checkbox, however it is written:
# "- [ ]", "- [  ]", "* []". Accepting a single spelling left a trivial way out
# for approving a requirement full of holes.
OPEN_QUESTION_RE = re.compile(r"^\s*[-*+]\s*\[\s*\]", re.MULTILINE)
FENCED_BLOCK_RE = re.compile(r"^\s*(?:```|~~~).*?^\s*(?:```|~~~)", re.MULTILINE | re.DOTALL)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
# §7 (derived features) and §8 (change log) change after approval without what
# was approved changing: they stay out of the fingerprint.
MUTABLE_SECTIONS_RE = re.compile(
    r"^##\s*[78]\..*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL
)

# Extensions that count as "application code" when checking that nobody
# programmed before having an approved requirement. Not just Python: the
# template happens to be Python, but the harness does not have to be.
CODE_EXT = (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb",
            ".cs", ".php", ".kt", ".swift", ".sh", ".ps1", ".sql")

VALID_STATUS = ("draft", "approved", "discarded")
PRIORITIES = ("critical", "high", "medium", "low")
REQUIRED_KEYS = ("id", "title", "status", "priority")

# Anything that is NOT `draft` means somebody already worked on the feature.
# It is defined by complement rather than as an allowlist on purpose: with an
# allowlist, inventing a new status in `rules.valid_status` was enough for a
# feature to escape the gate without any validator looking at it.
DRAFT = "draft"


def is_worked_on(status: object) -> bool:
    """Any status other than `draft` counts as work already started."""
    return status is not None and status != DRAFT


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def parse_frontmatter(text: str) -> tuple[dict[str, str], list[str]] | None:
    """Flat YAML front matter (`key: value`). None if absent or unterminated.

    Returns (fields, repeated_keys). Deliberately minimal: the harness has no
    external dependencies, so there is no PyYAML. In exchange, the spec template
    requires flat keys.

    `#` is not treated as a comment inside a value: a legitimate title can carry
    a hash (`Fix bug #123`), and truncating it silently is worse than not
    supporting inline comments.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    fields: dict[str, str] = {}
    repeated: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return fields, repeated
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("\"'")
        if not key:
            continue
        if key in fields:
            repeated.append(key)
            continue
        fields[key] = value
    return None


def spec_fingerprint(content: str) -> str:
    """Fingerprint of the content that was approved.

    Approving a requirement cannot mean only "at some point somebody wrote
    `approved`": without a fingerprint of the text, editing its criteria
    afterwards leaves no trace and the reviewer ends up judging against
    something the human never read.

    Two sections that do change legitimately after approval are excluded: the
    derived-features table (§7) and the change log (§8). Everything else counts,
    which makes it a deliberately short denylist: any new section is protected
    by default.
    """
    body = FRONTMATTER_RE.sub("", content, count=1)
    body = MUTABLE_SECTIONS_RE.sub("", body)
    lines = [line.rstrip() for line in body.splitlines()]
    normalized = "\n".join(line for line in lines if line)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def count_code(src_dir: str) -> int:
    """Code files under `src/`, recursively.

    Recursive and multi-language on purpose: looking only at `src/*.py` left the
    harness blind to `src/package/module.py` and to any project that was not
    Python.
    """
    total = 0
    if not os.path.isdir(src_dir):
        return 0
    for _folder, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv", "node_modules")]
        for name in files:
            if name == "__init__.py":
                continue
            if name.endswith(CODE_EXT):
                total += 1
    return total


def priority_rank(priority: str) -> int:
    """0 is the most critical. An unknown value goes last."""
    try:
        return PRIORITIES.index(priority)
    except ValueError:
        return len(PRIORITIES)


def load_specs(root: str) -> tuple[dict[str, dict], list[str]]:
    """Returns ({relative path: spec data}, format errors)."""
    specs: dict[str, dict] = {}
    fails: list[str] = []
    spec_dir = os.path.join(root, SPEC_DIR)

    if not os.path.isdir(spec_dir):
        return specs, fails

    seen_ids: dict[str, str] = {}
    for name in sorted(os.listdir(spec_dir)):
        if not name.endswith(".md") or name.startswith("_"):
            continue

        rel = f"{SPEC_DIR}/{name}"
        match = SPEC_FILE_RE.match(name)
        if not match:
            fails.append(
                f"{rel}: the file name does not follow REQ-00N_snake_case_name.md"
            )
            continue

        content = _read(os.path.join(spec_dir, name))
        parsed = parse_frontmatter(content)
        if parsed is None:
            fails.append(f"{rel}: has no front matter, or it is not closed with ---")
            continue
        fields, repeated = parsed
        if repeated:
            fails.append(
                f"{rel}: the front matter repeats {', '.join(sorted(set(repeated)))}. "
                f"With duplicate keys there is no telling which one counts: keep one"
            )

        missing = [key for key in REQUIRED_KEYS if not fields.get(key)]
        if missing:
            fails.append(f"{rel}: missing from the front matter: {', '.join(missing)}")
            continue

        spec_id = fields["id"]
        if spec_id != f"REQ-{match.group(1)}":
            fails.append(
                f"{rel}: the front matter id ({spec_id}) does not match the one in "
                f"the file name (REQ-{match.group(1)}). It is not loaded: fix one "
                f"of the two before going on"
            )
            continue
        if spec_id in seen_ids:
            fails.append(f"{rel}: duplicate id {spec_id} (already used by {seen_ids[spec_id]})")
        seen_ids[spec_id] = rel

        if fields["status"] not in VALID_STATUS:
            fails.append(
                f"{rel}: invalid status \"{fields['status']}\" "
                f"(use: {', '.join(VALID_STATUS)})"
            )
        if fields["priority"] not in PRIORITIES:
            fails.append(
                f"{rel}: invalid priority \"{fields['priority']}\" "
                f"(use: {', '.join(PRIORITIES)})"
            )

        fields["_path"] = rel
        fields["_fingerprint"] = spec_fingerprint(content)
        # Fenced blocks are ignored: an example checkbox inside triple backticks
        # is not an unanswered question.
        fields["_open_questions"] = len(
            OPEN_QUESTION_RE.findall(FENCED_BLOCK_RE.sub("", content))
        )
        specs[rel] = fields

    return specs, fails


def check(root: str) -> tuple[list[str], list[str]]:
    """Returns (failures, warnings)."""
    fails: list[str] = []
    warns: list[str] = []

    specs, spec_fails = load_specs(root)
    fails.extend(spec_fails)

    if not os.path.isdir(os.path.join(root, SPEC_DIR)):
        warns.append(
            "specs/ does not exist yet: the project has no approved scope, so "
            "there is nothing to build. Start with /requirements"
        )
    elif not specs:
        warns.append(
            "specs/ has no requirements yet: there is no approved scope, so there "
            "is nothing to build. Start with /requirements"
        )

    # --- feature_list.json --------------------------------------------------
    try:
        data = json.loads(_read(os.path.join(root, "feature_list.json")))
    except (OSError, json.JSONDecodeError):
        # The diagnosis is not duplicated: the shape of that file is section 4's
        # job. But we carry on: whatever can be said about specs/ is still worth
        # saying, and staying quiet would leave the human fixing problems one at
        # a time.
        fails.append("Could not read feature_list.json (see section 4)")
        data = {}

    features = data.get("features")
    if not isinstance(features, list):
        if data:
            fails.append("\"features\" is not an array (see section 4)")
        features = []

    referenced: dict[str, list[dict]] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue

        label = f"feature {feature.get('id', '?')} {feature.get('name', '')}".strip()
        status = feature.get("status")
        spec_path = feature.get("spec")

        if not spec_path:
            fails.append(
                f"{label}: has no \"spec\" field. Every feature comes from a "
                f"requirement in specs/"
            )
            continue
        if not SPEC_POINTER_RE.match(str(spec_path)):
            fails.append(
                f"{label}: \"spec\" must be a specs/REQ-00N_name.md path "
                f"(it says \"{spec_path}\")"
            )
            continue

        spec = specs.get(spec_path)
        if spec is None:
            fails.append(f"{label}: points at {spec_path}, which does not exist")
            continue

        referenced.setdefault(spec_path, []).append(feature)

        if is_worked_on(status) and spec["status"] != "approved":
            fails.append(
                f"{label}: status \"{status}\" but {spec_path} is still "
                f"\"{spec['status']}\" (nobody approved that requirement)"
            )

        priority = feature.get("priority")
        if priority in PRIORITIES and spec["priority"] in PRIORITIES:
            if priority_rank(priority) < priority_rank(spec["priority"]):
                fails.append(
                    f"{label}: priority \"{priority}\" is higher than its "
                    f"requirement's (\"{spec['priority']}\"). A feature may lower it, "
                    f"not raise it: change the requirement if it really is more urgent"
                )

    # --- per-requirement coherence ------------------------------------------
    approved = 0
    in_draft: list[str] = []
    for rel, spec in sorted(specs.items()):
        status = spec["status"]
        its_features = referenced.get(rel, [])

        if status == DRAFT:
            in_draft.append(f"{spec['id']} [{spec['priority']}]")
            continue
        if status == "discarded":
            # Features that already left draft are caught by the gate above. The
            # ones still in draft are zombie scope: nobody is going to implement
            # them and nobody is going to miss them until they get in the way.
            alive = [f for f in its_features if f.get("status") == DRAFT]
            if alive:
                names = ", ".join(str(f.get("id")) for f in alive)
                warns.append(
                    f"{rel}: is discarded but {len(alive)} feature(s) in draft still "
                    f"hang off it (id {names}): delete them or move them to another "
                    f"requirement"
                )
            continue
        if status != "approved":
            continue

        approved += 1
        date = spec.get("approved_on", "")
        if not date:
            fails.append(f"{rel}: is approved but has no date in approved_on")
        elif not DATE_RE.match(date):
            fails.append(
                f"{rel}: approved_on says \"{date}\" and it has to be a YYYY-MM-DD "
                f"date. An approval without a real date is no use as a trace"
            )

        declared = spec.get("approved_hash", "")
        if not declared:
            fails.append(
                f"{rel}: is approved but has no approved_hash. Without a fingerprint "
                f"of the approved text, editing its criteria later leaves no trace: "
                f"approve it again with /approve"
            )
        elif declared != spec["_fingerprint"]:
            fails.append(
                f"{rel}: the requirement changed AFTER being approved "
                f"(fingerprint {declared}, now {spec['_fingerprint']}). "
                f"Send the spec back to draft and have the human approve the new "
                f"version, or undo the change"
            )
        if spec["_open_questions"]:
            fails.append(
                f"{rel}: is approved with {spec['_open_questions']} unanswered open "
                f"question(s). A requirement is not approved with holes in it: "
                f"answer them and tick the box, or send the spec back to draft"
            )
        if not its_features:
            fails.append(
                f"{rel}: is approved but no feature references it. "
                f"Derive its features or send it back to draft"
            )
        elif all(f.get("status") == DRAFT for f in its_features):
            warns.append(
                f"{rel}: approved but its {len(its_features)} feature(s) are still in "
                f"draft (half-finished approval: run /approve to the end)"
            )

    if in_draft:
        warns.append(
            f"{len(in_draft)} requirement(s) in draft waiting for your OK: "
            f"{', '.join(in_draft)}"
        )

    # --- no programming without requirements --------------------------------
    modules = count_code(os.path.join(root, "src"))
    if modules and approved == 0:
        fails.append(
            f"there are {modules} code file(s) in src/ and no approved requirement: "
            f"somebody started programming before deciding what to build"
        )

    # --- priority overtake ---------------------------------------------------
    in_progress = [f for f in features if isinstance(f, dict) and f.get("status") == "in_progress"]
    queued = [f for f in features if isinstance(f, dict) and f.get("status") == "pending"]
    for feature in in_progress:
        rank = priority_rank(str(feature.get("priority")))
        urgent = [f for f in queued if priority_rank(str(f.get("priority"))) < rank]
        if urgent:
            ids = ", ".join(str(f.get("id")) for f in urgent)
            warns.append(
                f"feature {feature.get('id')} {feature.get('name')} "
                f"({feature.get('priority')}) is in_progress and there is "
                f"higher-priority work queued (id {ids}): finish it, or move it to "
                f"blocked with a reason before going on"
            )

    return fails, warns


def main(argv: list[str]) -> int:
    if len(argv) > 2 and argv[1] == "--fingerprint":
        try:
            print(spec_fingerprint(_read(argv[2])))
        except OSError as exc:
            print(f"[FAIL]  could not read {argv[2]}: {exc}")
            return 1
        return 0

    root = argv[1] if len(argv) > 1 else "."
    fails, warns = check(root)

    for warn in warns:
        print(f"[WARN]  {warn}")
    for fail in fails:
        print(f"[FAIL]  {fail}")

    if fails:
        print("[FAIL]  There is work on unapproved requirements, or traceability")
        print("        is broken: resolve it before going on.")
        return 1

    specs, _ = load_specs(root)
    approved = sum(1 for s in specs.values() if s.get("status") == "approved")
    try:
        total_features = len(json.loads(_read(os.path.join(root, "feature_list.json")))["features"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        total_features = 0
    print(
        f"[OK]    {len(specs)} requirements ({approved} approved), "
        f"{total_features} features traced"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
