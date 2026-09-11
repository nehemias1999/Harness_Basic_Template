"""Signs requirements: the mechanical half of approval.

Purpose
    Turn your OK into verifiable state, without depending on an agent
    remembering seven steps in the right order. Approving means touching four
    things at once — the spec's status, the date, the content fingerprint and
    the status of its features — and halfway through the repository is
    incoherent. That is a script's job, not a `.md`'s prose.

    What it does NOT automate is the decision. You name what gets approved; the
    script refuses if what you named has unanswered questions or was already
    approved.

Usage
    python scripts/approve.py 1 2              # REQ-001 and REQ-002
    python scripts/approve.py REQ-003          # spell the id however you like
    python scripts/approve.py all              # every requirement in draft
    python scripts/approve.py 1 architecture   # and also sign docs/architecture.md
    python scripts/approve.py all --dry-run

What it does per named requirement
    1. `status: draft` -> `approved`, with today's `approved_on` and `updated`.
    2. Computes and writes `approved_hash`: the fingerprint of the approved text.
    3. Appends the change-log row (§8).
    4. Moves its features from `draft` to `pending`.

The `architecture` keyword
    Removes the template note from `docs/architecture.md`, which is the act that
    makes that document approved. It goes separately and has to be named on
    purpose: it is the criterion the reviewer judges all the code against, and
    approving it as a side effect of a requirement would be exactly the
    oversight the harness is trying to prevent.

Exit codes
    0  signed (or simulated) · 1 could not: the reason is printed
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_requirements as vr  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The keywords are English, like the commands. Spanish still works: the same
# tolerance the ids get, which are valid as 1, 001 or REQ-001.
ALL = ("all", "todos")
ARCHITECTURE = ("architecture", "arquitectura")
TEMPLATE_MARKER = "This file is a template"
ID_RE = re.compile(r"^(?:req-)?0*(\d{1,3})$", re.IGNORECASE)
# Careful with `\s*$`: it eats the trailing newline and the new row ends up
# separated by a blank line, which in markdown splits the table in two.
LOG_ROW_RE = re.compile(r"^\|.*\|[ \t]*$", re.MULTILINE)


def ok(message: str) -> None:
    print(f"[OK]    {message}")


def warn(message: str) -> None:
    print(f"[WARN]  {message}")


def fail(message: str) -> None:
    print(f"[FAIL]  {message}")


def normalize_id(text: str) -> str | None:
    """`1`, `001`, `REQ-001`, `req-1` -> `REQ-001`. None if it is not an id."""
    match = ID_RE.match(text.strip())
    if not match:
        return None
    return f"REQ-{int(match.group(1)):03d}"


def who_signs(root: str) -> str:
    """The name of whoever approves, for the change log."""
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=root, capture_output=True, text=True, encoding="utf-8",
        )
        name = result.stdout.strip()
    except OSError:
        name = ""
    return name or "human"


class Approver:
    def __init__(self, root: str, targets: list[str], dry_run: bool, by: str = "") -> None:
        self.root = root
        self.targets = targets
        self.dry_run = dry_run
        self.by = by or who_signs(root)
        self.today = datetime.date.today().isoformat()
        self.specs, self.format_errors = vr.load_specs(root)

    # -- helpers ---------------------------------------------------------
    def read(self, rel: str) -> str:
        with open(os.path.join(self.root, rel), encoding="utf-8") as handle:
            return handle.read()

    def write(self, rel: str, content: str) -> None:
        if self.dry_run:
            return
        with open(os.path.join(self.root, rel), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    def suffix(self) -> str:
        return " (simulated)" if self.dry_run else ""

    # -- resolving what was asked for -------------------------------------
    def resolve(self) -> tuple[list[str], bool, list[str]]:
        """Returns (spec paths to sign, whether architecture is included, errors)."""
        errors: list[str] = []
        architecture = False
        requested: list[str] = []

        for target in self.targets:
            plain = target.strip().lower().rstrip(",")
            if plain in ARCHITECTURE:
                architecture = True
                continue
            if plain in ALL:
                requested.extend(
                    rel for rel, spec in sorted(self.specs.items())
                    if spec["status"] == vr.DRAFT
                )
                continue

            req_id = normalize_id(plain)
            if not req_id:
                errors.append(
                    f'I do not understand "{target}": use an id (1, 001, REQ-001), '
                    f'"{ALL[0]}" or "{ARCHITECTURE[0]}"'
                )
                continue

            paths = [rel for rel, spec in self.specs.items() if spec["id"] == req_id]
            if not paths:
                errors.append(f"{req_id}: there is no requirement with that id")
                continue
            requested.extend(paths)

        # No duplicates, stable order.
        seen: list[str] = []
        for path in requested:
            if path not in seen:
                seen.append(path)
        return seen, architecture, errors

    def check(self, paths: list[str]) -> list[str]:
        """Reasons why something that was asked for cannot be signed."""
        problems: list[str] = []
        for rel in paths:
            spec = self.specs[rel]
            if spec["status"] == "approved":
                problems.append(f"{spec['id']}: was already approved")
            elif spec["status"] != vr.DRAFT:
                problems.append(
                    f"{spec['id']}: its status is \"{spec['status']}\", not draft"
                )
            if spec["_open_questions"]:
                problems.append(
                    f"{spec['id']}: has {spec['_open_questions']} unanswered "
                    f"question(s). Answer them and tick the box before approving"
                )
        return problems

    # -- signing -----------------------------------------------------------
    def sign(self, rel: str) -> None:
        spec = self.specs[rel]
        content = self.read(rel)
        header, _, body = content.partition("\n---\n")

        fields = []
        for line in header.splitlines():
            key = line.split(":", 1)[0].strip()
            if key == "status":
                fields.append("status: approved")
            elif key == "approved_on":
                fields.append(f"approved_on: {self.today}")
            elif key == "updated":
                fields.append(f"updated: {self.today}")
            elif key == "approved_hash":
                continue  # recomputed below
            else:
                fields.append(line)
        if not any(f.startswith("approved_on:") for f in fields):
            fields.append(f"approved_on: {self.today}")

        body = self.append_log_row(body, spec.get("round", "?"))
        updated = "\n".join(fields) + "\n---\n" + body

        # The fingerprint ignores the front matter and the change log, so the
        # order does not matter; it is computed over the final text so there are
        # no surprises.
        fingerprint = vr.spec_fingerprint(updated)
        fields.append(f"approved_hash: {fingerprint}")
        updated = "\n".join(fields) + "\n---\n" + body

        self.write(rel, updated)
        ok(f"{spec['id']} -> approved on {self.today}, fingerprint {fingerprint}{self.suffix()}")

    def append_log_row(self, body: str, round_number: str) -> str:
        row = f"| {round_number} | {self.today} | approved | {self.by} |"
        marker = re.search(r"^##\s*8\..*$", body, re.MULTILINE)
        if not marker:
            return body.rstrip("\n") + f"\n\n## 8. Change log\n\n{row}\n"
        section = body[marker.end():]
        rows = list(LOG_ROW_RE.finditer(section))
        if not rows:
            return body.rstrip("\n") + f"\n{row}\n"
        cut = marker.end() + rows[-1].end()
        return body[:cut] + f"\n{row}" + body[cut:]

    def promote_features(self, paths: list[str]) -> int:
        json_path = os.path.join(self.root, "feature_list.json")
        with open(json_path, encoding="utf-8") as handle:
            data = json.load(handle)

        promoted = 0
        for feature in data.get("features") or []:
            if not isinstance(feature, dict):
                continue
            if feature.get("spec") in paths and feature.get("status") == vr.DRAFT:
                feature["status"] = "pending"
                promoted += 1
                ok(
                    f"feature {feature.get('id')} {feature.get('name')} "
                    f"-> pending{self.suffix()}"
                )

        if promoted and not self.dry_run:
            with open(json_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return promoted

    def check_architecture(self) -> list[str]:
        try:
            content = self.read("docs/architecture.md")
        except OSError as exc:
            return [f"could not read docs/architecture.md: {exc}"]

        if TEMPLATE_MARKER not in content:
            return []

        holes = pending_placeholders(content)
        if holes:
            return [
                f"docs/architecture.md still has unfilled placeholders "
                f"({', '.join(holes[:4])}). It does not get approved half-done: "
                f"send it back to the analyst"
            ]
        return []

    def sign_architecture(self) -> None:
        rel = "docs/architecture.md"
        content = self.read(rel)

        if TEMPLATE_MARKER not in content:
            warn("docs/architecture.md was already approved, there was no note to remove")
            return

        lines = [line for line in content.splitlines() if TEMPLATE_MARKER not in line]
        self.write(rel, "\n".join(lines).strip() + "\n")
        ok(f"docs/architecture.md -> approved (template note removed){self.suffix()}")

    # -- orchestration ------------------------------------------------------
    def run(self) -> int:
        if self.format_errors:
            for error in self.format_errors:
                fail(error)
            fail("There are malformed specs: fix them before approving anything.")
            return 1

        paths, architecture, errors = self.resolve()
        for error in errors:
            fail(error)
        if errors:
            return 1

        if not paths and not architecture:
            warn("there is nothing to approve: no requirement is in draft")
            return 0

        problems = self.check(paths)
        if architecture:
            problems.extend(self.check_architecture())
        for problem in problems:
            fail(problem)
        if problems:
            # All or nothing: signing half of it leaves the repository in a state
            # the verifier flags red and nobody asked for.
            fail("Nothing was signed.")
            return 1

        mode = " (dry run: nothing is written)" if self.dry_run else ""
        print(f"-- Signing {len(paths)} requirement(s){mode} ----------------------")

        for rel in paths:
            self.sign(rel)
        promoted = self.promote_features(paths)

        if architecture:
            self.sign_architecture()

        print("")
        if paths and not promoted:
            warn(
                "no requirement had features in draft: derive them with "
                "/requirements before going on, or the verifier will say so"
            )
        ok(f"{len(paths)} requirement(s) signed, {promoted} feature(s) now pending")
        print("        Next: run the verifier and then /next-feature.")
        return 0


def pending_placeholders(text: str) -> list[str]:
    """Any `<holes>` left, ignoring the helper HTML comments."""
    import validate_project_setup as vps

    return vps.find_placeholders(text)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Signs the requirements you name."
    )
    parser.add_argument(
        "targets",
        nargs="+",
        metavar="ID",
        help='ids (1, 001, REQ-001), "all", or "architecture"',
    )
    parser.add_argument("--dry-run", action="store_true", help="Writes nothing")
    parser.add_argument("--by", default="", help="Who approves (for the change log)")
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv[1:])

    return Approver(args.root, args.targets, args.dry_run, args.by).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
