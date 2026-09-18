"""Tests for scripts/approve.py.

Signing touches four things at once and halfway through the repository is
incoherent. What matters most to cover is that it does not sign when it must
not, and that when it refuses **nothing has been written**.

Features are written as notes (`features/F-<id>_<name>.md`) and read back
through scripts/features_io.load_features, like the approver reads them.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import approve  # noqa: E402
import features_io  # noqa: E402
import validate_requirements as vr  # noqa: E402


SPEC = """---
id: {spec_id}
title: A requirement
status: {status}
priority: high
created: 2026-09-01
updated: 2026-09-01
approved_on:
approved_hash:
round: 2
---

# {spec_id} — A requirement

## 5. Acceptance criteria

1. Does something verifiable.

## 6. Assumptions and open questions

{questions}

## 8. Change log

| round | date | what changed | requested by |
|-------|------|--------------|--------------|
| 1 | 2026-09-01 | initial version | human |
"""

ARCHITECTURE_DRAFT = """# Architecture

> **This file is a template: fill it in before writing the first feature.** — DRAFT, not approved

## Principles

1. Three layers: cli, domain, storage.
"""


def _quote(value: object) -> str:
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _frontmatter(fields: dict) -> str:
    """The note's front matter, in the exact shape the templates use."""
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f'  - "{_quote(item)}"')
        else:
            lines.append(f"{key}: {_quote(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


class ApproveCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "specs"))
        os.makedirs(os.path.join(self.root, "docs"))
        self.write("docs/architecture.md", ARCHITECTURE_DRAFT)
        self.spec("REQ-001", "req_one")
        self.features(
            [
                self.feature(1, "one", "specs/REQ-001_req_one.md"),
                self.feature(2, "another", "specs/REQ-001_req_one.md"),
            ]
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------
    def write(self, rel: str, content: str) -> None:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    def read(self, rel: str) -> str:
        with open(os.path.join(self.root, rel), encoding="utf-8") as handle:
            return handle.read()

    def snapshot(self, rel: str) -> dict:
        """Name -> content for every file under `rel`, for change detection."""
        folder = os.path.join(self.root, rel)
        return {
            name: self.read(f"{rel}/{name}")
            for name in sorted(os.listdir(folder))
        }

    def spec(self, spec_id: str, name: str, status: str = "draft",
             questions: str = "- [x] **Q1:** answered") -> str:
        rel = f"specs/{spec_id}_{name}.md"
        self.write(rel, SPEC.format(spec_id=spec_id, status=status, questions=questions))
        return rel

    def feature(self, fid: int, name: str, spec: str, status: str = "draft") -> dict:
        return {
            "id": fid, "name": name, "title": name, "description": "x",
            "spec": spec, "priority": "high", "acceptance": ["something"], "status": status,
        }

    def features(self, items: list[dict]) -> None:
        features_dir = os.path.join(self.root, "features")
        os.makedirs(features_dir, exist_ok=True)
        for feat in items:
            fields = dict(feat)
            fid = int(fields["id"])
            name = fields["name"]
            rel = os.path.join(features_dir, f"F-{fid:03d}_{name}.md")
            with open(rel, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(_frontmatter(fields) + "\n")

    def feature_statuses(self) -> list[str]:
        loaded, _ = features_io.load_features(self.root)
        loaded.sort(key=lambda f: f["id"])
        return [f["status"] for f in loaded]

    def run_approve(self, *targets: str, dry_run: bool = False) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = approve.Approver(self.root, list(targets), dry_run, by="tester").run()
        return code, output.getvalue()


class TestSigning(ApproveCase):
    def test_signs_by_id(self) -> None:
        code, _ = self.run_approve("1")
        self.assertEqual(code, 0)

        content = self.read("specs/REQ-001_req_one.md")
        self.assertIn("status: approved", content)
        self.assertIn("approved_hash: ", content)
        self.assertNotIn("approved_hash:\n", content)
        self.assertEqual(self.feature_statuses(), ["pending", "pending"])

    def test_the_written_fingerprint_is_the_one_that_validates(self) -> None:
        self.run_approve("1")
        content = self.read("specs/REQ-001_req_one.md")
        fields, _ = vr.parse_frontmatter(content)
        self.assertEqual(fields["approved_hash"], vr.spec_fingerprint(content))

    def test_the_result_passes_the_validator(self) -> None:
        self.run_approve("1")
        fails, _warns = vr.check(self.root)
        self.assertEqual(fails, [])

    def test_it_accepts_any_spelling_of_the_id(self) -> None:
        for text in ("1", "001", "REQ-001", "req-1"):
            with self.subTest(text=text):
                self.assertEqual(approve.normalize_id(text), "REQ-001")

    def test_all_signs_the_drafts(self) -> None:
        self.spec("REQ-002", "req_two")
        self.spec("REQ-003", "req_three", status="approved")
        code, output = self.run_approve("all")
        self.assertEqual(code, 0)
        self.assertIn("REQ-001", output)
        self.assertIn("REQ-002", output)
        self.assertNotIn("REQ-003 ->", output)

    def test_only_the_english_keywords_are_accepted(self) -> None:
        # There is one canonical spelling. The ids stay forgiving; the keywords
        # do not, so there is no second vocabulary to keep in sync.
        for word in ("todos", "arquitectura"):
            with self.subTest(word=word):
                code, output = self.run_approve(word)
                self.assertEqual(code, 1)
                self.assertIn("I do not understand", output)

    def test_it_appends_the_log_row_attached_to_the_table(self) -> None:
        self.run_approve("1")
        rows = [l for l in self.read("specs/REQ-001_req_one.md").splitlines() if l.startswith("|")]
        self.assertEqual(len(rows), 4)  # header, separator, the old one and the new one
        self.assertIn("tester", rows[-1])

    def test_the_same_id_twice_is_not_signed_twice(self) -> None:
        code, output = self.run_approve("1", "001")
        self.assertEqual(code, 0)
        self.assertEqual(output.count("REQ-001 -> approved"), 1)


class TestItRefuses(ApproveCase):
    """And when it refuses, it writes nothing."""

    def test_with_open_questions(self) -> None:
        self.spec("REQ-001", "req_one", questions="- [ ] **Q1:** how was this again?")
        before = self.read("specs/REQ-001_req_one.md")

        code, output = self.run_approve("1")
        self.assertEqual(code, 1)
        self.assertIn("unanswered", output)
        self.assertEqual(self.read("specs/REQ-001_req_one.md"), before)
        self.assertEqual(self.feature_statuses(), ["draft", "draft"])

    def test_already_approved(self) -> None:
        self.spec("REQ-001", "req_one", status="approved")
        code, output = self.run_approve("1")
        self.assertEqual(code, 1)
        self.assertIn("was already approved", output)

    def test_a_nonexistent_id(self) -> None:
        code, output = self.run_approve("99")
        self.assertEqual(code, 1)
        self.assertIn("there is no requirement", output)

    def test_a_word_that_means_nothing(self) -> None:
        code, output = self.run_approve("whatever")
        self.assertEqual(code, 1)
        self.assertIn("I do not understand", output)

    def test_one_bad_id_does_not_sign_the_good_one(self) -> None:
        # All or nothing: signing half leaves a state nobody asked for.
        self.spec("REQ-002", "req_two")
        code, _output = self.run_approve("1", "99")
        self.assertEqual(code, 1)
        self.assertIn("status: draft", self.read("specs/REQ-001_req_one.md"))

    def test_a_malformed_spec_stops_everything(self) -> None:
        self.write("specs/REQ-009_broken.md", "no front matter\n")
        code, output = self.run_approve("1")
        self.assertEqual(code, 1)
        self.assertIn("fix them before approving", output)


class TestArchitecture(ApproveCase):
    def test_it_is_named_separately(self) -> None:
        self.run_approve("1")
        # Signing a requirement does not touch the architecture.
        self.assertIn(approve.TEMPLATE_MARKER, self.read("docs/architecture.md"))

    def test_it_signs_the_architecture(self) -> None:
        code, _ = self.run_approve("1", "architecture")
        self.assertEqual(code, 0)
        self.assertNotIn(approve.TEMPLATE_MARKER, self.read("docs/architecture.md"))

    def test_with_holes_it_signs_nothing(self) -> None:
        self.write(
            "docs/architecture.md",
            ARCHITECTURE_DRAFT + "\n2. Layers: <module_1>, <module_2>.\n",
        )
        code, output = self.run_approve("1", "architecture")
        self.assertEqual(code, 1)
        self.assertIn("unfilled placeholders", output)
        # And the requirement was not signed either.
        self.assertIn("status: draft", self.read("specs/REQ-001_req_one.md"))

    def test_an_already_approved_architecture_only_warns(self) -> None:
        self.write("docs/architecture.md", "# Architecture\n\n1. Three layers.\n")
        code, output = self.run_approve("architecture")
        self.assertEqual(code, 0)
        self.assertIn("was already approved", output)


class TestDryRun(ApproveCase):
    def test_dry_run_writes_nothing(self) -> None:
        spec_before = self.read("specs/REQ-001_req_one.md")
        features_before = self.snapshot("features")

        code, output = self.run_approve("all", "architecture", dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("simulated", output)
        self.assertEqual(self.read("specs/REQ-001_req_one.md"), spec_before)
        self.assertEqual(self.snapshot("features"), features_before)
        self.assertIn(approve.TEMPLATE_MARKER, self.read("docs/architecture.md"))


class TestNothingToApprove(ApproveCase):
    def test_with_no_drafts_it_warns_and_does_not_fail(self) -> None:
        self.spec("REQ-001", "req_one", status="approved")
        code, output = self.run_approve("all")
        self.assertEqual(code, 0)
        self.assertIn("nothing to approve", output)


if __name__ == "__main__":
    unittest.main()