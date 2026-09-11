"""Tests for scripts/validate_requirements.py.

They live here and not in `tests/` on purpose: `tests/` belongs to the project,
and the verifier discovers it with `unittest discover -s tests`. If these tests
were in there, a freshly instantiated project would come out "green" with tests
that are not its own, and the harness would stop telling "unverified" apart from
"verified".

They are run by hand or from /harness-check:

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_requirements as vr  # noqa: E402


SPEC = """---
id: {spec_id}
title: A test requirement
status: {status}
priority: {priority}
created: 2026-09-10
updated: 2026-09-10
approved_on: {approved_on}
round: 1
---

# {spec_id} — A test requirement

## 6. Assumptions and open questions

{questions}
"""


def feature(**kwargs) -> dict:
    base = {
        "id": 1,
        "name": "a_feature",
        "title": "A feature",
        "description": "What it does.",
        "spec": "specs/REQ-001_a_requirement.md",
        "priority": "medium",
        "acceptance": ["does something verifiable"],
        "status": "draft",
    }
    base.update(kwargs)
    return base


class HarnessCase(unittest.TestCase):
    """Sets up a fake repo in a temporary directory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "specs"))
        os.makedirs(os.path.join(self.root, "src"))
        self.write_features([])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------
    def write_features(self, features: list[dict]) -> None:
        payload = {"project": "test", "rules": {}, "features": features}
        path = os.path.join(self.root, "feature_list.json")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def write_spec(
        self,
        name: str = "REQ-001_a_requirement.md",
        spec_id: str = "REQ-001",
        status: str = "draft",
        priority: str = "medium",
        approved_on: str = "",
        questions: str = "- [x] **Q1:** answered",
        body: str | None = None,
    ) -> None:
        content = body if body is not None else SPEC.format(
            spec_id=spec_id,
            status=status,
            priority=priority,
            approved_on=approved_on,
            questions=questions,
        )
        # An approved spec carries its content fingerprint; /approve computes it
        # when signing. Since the fingerprint ignores the front matter, adding
        # the line does not change it.
        if status == "approved" and "approved_hash:" not in content:
            fingerprint = vr.spec_fingerprint(content)
            header, rest = content.split("\n---\n", 1)
            content = f"{header}\napproved_hash: {fingerprint}\n---\n{rest}"
        with open(os.path.join(self.root, "specs", name), "w", encoding="utf-8", newline="\n") as h:
            h.write(content)

    def write_module(self, name: str = "thing.py") -> None:
        with open(os.path.join(self.root, "src", name), "w", encoding="utf-8") as handle:
            handle.write('"""A module."""\n')

    def check(self) -> tuple[list[str], list[str]]:
        return vr.check(self.root)

    def assertFailsWith(self, needle: str) -> None:
        fails, _ = self.check()
        self.assertTrue(
            any(needle in f for f in fails),
            f"no [FAIL] contains {needle!r}. Failures: {fails}",
        )

    def assertNoFails(self) -> None:
        fails, _ = self.check()
        self.assertEqual(fails, [])


class TestNormalStates(HarnessCase):
    def test_no_specs_no_features_only_warns(self) -> None:
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(warns)

    def test_a_missing_specs_folder_only_warns(self) -> None:
        os.rmdir(os.path.join(self.root, "specs"))
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("specs/ does not exist" in w for w in warns))

    def test_draft_with_draft_features_is_valid(self) -> None:
        self.write_spec()
        self.write_features([feature()])
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("waiting for your OK" in w for w in warns))

    def test_approved_with_pending_features_is_valid_and_silent(self) -> None:
        self.write_spec(status="approved", approved_on="2026-09-10")
        self.write_features([feature(status="pending")])
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertEqual(warns, [])

    def test_several_features_per_requirement(self) -> None:
        self.write_spec(status="approved", approved_on="2026-09-10")
        self.write_features(
            [
                feature(id=1, name="one", status="pending"),
                feature(id=2, name="another", status="pending"),
            ]
        )
        self.assertNoFails()

    def test_the_template_with_placeholders_is_ignored(self) -> None:
        self.write_spec(name="_req_template.md", body="---\nid: <REQ-00N>\n")
        self.assertNoFails()


class TestTheGate(HarnessCase):
    def test_a_feature_in_progress_over_a_draft_fails(self) -> None:
        self.write_spec()
        self.write_features([feature(status="in_progress")])
        self.assertFailsWith("is still \"draft\"")

    def test_a_blocked_feature_over_a_draft_also_fails(self) -> None:
        self.write_spec()
        self.write_features([feature(status="blocked")])
        self.assertFailsWith("nobody approved that requirement")

    def test_code_in_src_with_no_approved_requirement_fails(self) -> None:
        self.write_spec()
        self.write_features([feature()])
        self.write_module()
        self.assertFailsWith("before deciding what to build")

    def test_code_in_src_with_an_approved_requirement_is_valid(self) -> None:
        self.write_spec(status="approved", approved_on="2026-09-10")
        self.write_features([feature(status="done")])
        self.write_module()
        self.assertNoFails()


class TestTraceability(HarnessCase):
    def test_a_feature_without_the_spec_field_fails(self) -> None:
        without_spec = feature()
        del without_spec["spec"]
        self.write_features([without_spec])
        self.assertFailsWith("has no \"spec\" field")

    def test_a_dangling_pointer_fails(self) -> None:
        self.write_features([feature()])
        self.assertFailsWith("which does not exist")

    def test_a_badly_formatted_pointer_fails(self) -> None:
        self.write_features([feature(spec="docs/something_else.md")])
        self.assertFailsWith("must be a specs/REQ-00N_name.md path")

    def test_approved_with_no_features_fails(self) -> None:
        self.write_spec(status="approved", approved_on="2026-09-10")
        self.assertFailsWith("no feature references it")

    def test_approved_with_draft_features_only_warns(self) -> None:
        self.write_spec(status="approved", approved_on="2026-09-10")
        self.write_features([feature(status="draft")])
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("half-finished approval" in w for w in warns))


class TestSpecFormat(HarnessCase):
    def test_an_invalid_file_name_fails(self) -> None:
        self.write_spec(name="REQ-001 Bad Name.md")
        self.assertFailsWith("does not follow")

    def test_no_front_matter_fails(self) -> None:
        self.write_spec(body="# A requirement with no front matter\n")
        self.assertFailsWith("has no front matter")

    def test_unterminated_front_matter_fails(self) -> None:
        self.write_spec(body="---\nid: REQ-001\ntitle: x\n")
        self.assertFailsWith("has no front matter")

    def test_a_required_key_is_missing(self) -> None:
        self.write_spec(body="---\nid: REQ-001\ntitle: x\npriority: high\n---\n")
        self.assertFailsWith("missing from the front matter: status")

    def test_an_invalid_status_fails(self) -> None:
        self.write_spec(status="ready")
        self.assertFailsWith("invalid status")

    def test_an_invalid_priority_fails(self) -> None:
        self.write_spec(priority="super_urgent")
        self.assertFailsWith("invalid priority")

    def test_an_id_that_does_not_match_the_file_fails(self) -> None:
        self.write_spec(spec_id="REQ-002")
        self.assertFailsWith("does not match the one in")

    def test_a_duplicate_id_fails(self) -> None:
        self.write_spec()
        self.write_spec(name="REQ-001_another_name.md")
        self.assertFailsWith("duplicate")

    def test_approved_with_no_date_fails(self) -> None:
        self.write_spec(status="approved")
        self.write_features([feature(status="pending")])
        self.assertFailsWith("has no date in approved_on")

    def test_approved_with_open_questions_fails(self) -> None:
        self.write_spec(
            status="approved",
            approved_on="2026-09-10",
            questions="- [ ] **Q1:** how was this again?",
        )
        self.write_features([feature(status="pending")])
        self.assertFailsWith("unanswered open question")


class TestPriority(HarnessCase):
    def test_a_feature_may_lower_the_priority(self) -> None:
        self.write_spec(status="approved", priority="high", approved_on="2026-09-10")
        self.write_features([feature(status="pending", priority="low")])
        self.assertNoFails()

    def test_a_feature_may_not_raise_the_priority(self) -> None:
        self.write_spec(status="approved", priority="medium", approved_on="2026-09-10")
        self.write_features([feature(status="pending", priority="critical")])
        self.assertFailsWith("is higher than its")

    def test_it_warns_about_the_overtake(self) -> None:
        self.write_spec(status="approved", priority="critical", approved_on="2026-09-10")
        self.write_features(
            [
                feature(id=1, name="in_flight", status="in_progress", priority="medium"),
                feature(id=2, name="urgent", status="pending", priority="critical"),
            ]
        )
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("higher-priority work queued" in w for w in warns))

    def test_no_warning_when_the_queued_work_is_less_urgent(self) -> None:
        self.write_spec(status="approved", priority="critical", approved_on="2026-09-10")
        self.write_features(
            [
                feature(id=1, name="in_flight", status="in_progress", priority="critical"),
                feature(id=2, name="later", status="pending", priority="low"),
            ]
        )
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertEqual(warns, [])


class TestAdversarialScenarios(HarnessCase):
    """The attempts to slip past the gate that the audit found.

    All of these used to pass. They are here so they do not come back.
    """

    def test_an_invented_status_does_not_escape_the_gate(self) -> None:
        # Widening rules.valid_status let you invent a status no validator
        # looked at. Now anything that is not draft counts as work.
        self.write_spec()
        self.write_features([feature(status="ready")])
        self.assertFailsWith("nobody approved that requirement")

    def test_code_in_a_src_subfolder_counts_too(self) -> None:
        self.write_spec()
        self.write_features([feature()])
        os.makedirs(os.path.join(self.root, "src", "package"))
        with open(os.path.join(self.root, "src", "package", "mod.py"), "w") as handle:
            handle.write("x = 1\n")
        self.assertFailsWith("before deciding what to build")

    def test_code_that_is_not_python_counts_too(self) -> None:
        self.write_spec()
        self.write_features([feature()])
        with open(os.path.join(self.root, "src", "app.ts"), "w") as handle:
            handle.write("const x = 1\n")
        self.assertFailsWith("before deciding what to build")

    def test_the_approval_date_has_to_be_a_date(self) -> None:
        self.write_spec(status="approved", approved_on="whenever")
        self.write_features([feature(status="pending")])
        self.assertFailsWith("has to be a YYYY-MM-DD")

    def test_a_checkbox_inside_a_fenced_block_does_not_block(self) -> None:
        self.write_spec(
            status="approved",
            approved_on="2026-09-10",
            questions="```\n- [ ] example from the template\n```",
        )
        self.write_features([feature(status="pending")])
        self.assertNoFails()

    def test_a_checkbox_in_another_spelling_still_blocks(self) -> None:
        for spelling in ("- [  ] Q1", "* [ ] Q1", "+ [] Q1"):
            with self.subTest(spelling=spelling):
                self.write_spec(
                    status="approved", approved_on="2026-09-10", questions=spelling
                )
                self.write_features([feature(status="pending")])
                self.assertFailsWith("unanswered open question")

    def test_front_matter_with_repeated_keys_fails(self) -> None:
        self.write_spec(
            body=(
                "---\nid: REQ-001\ntitle: T\nstatus: draft\n"
                "status: approved\npriority: high\n---\n"
            )
        )
        self.assertFailsWith("repeats")

    def test_a_discarded_spec_with_draft_features_warns(self) -> None:
        self.write_spec(status="discarded")
        self.write_features([feature(status="draft")])
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("is discarded" in w for w in warns), warns)

    def test_a_discarded_spec_with_a_live_feature_fails(self) -> None:
        self.write_spec(status="discarded")
        self.write_features([feature(status="in_progress")])
        self.assertFailsWith("nobody approved that requirement")

    def test_an_unreadable_feature_list_does_not_silence_specs(self) -> None:
        self.write_spec(name="REQ-001 Bad Name.md")
        with open(os.path.join(self.root, "feature_list.json"), "w") as handle:
            handle.write("{ this is not json")
        fails, _ = self.check()
        self.assertTrue(any("does not follow" in f for f in fails), fails)
        self.assertTrue(any("feature_list.json" in f for f in fails), fails)

    def test_a_mismatched_id_is_not_loaded(self) -> None:
        # It used to report the failure but keep using the spec for
        # traceability, which produced contradictory diagnostics.
        self.write_spec(spec_id="REQ-002")
        self.write_features([feature()])
        fails, _ = self.check()
        self.assertTrue(any("does not match" in f for f in fails), fails)
        self.assertTrue(any("does not exist" in f for f in fails), fails)


class TestFingerprintOfWhatWasApproved(HarnessCase):
    """Approving has to mean "I approved *this*", not "I typed the word"."""

    def test_editing_an_approved_spec_is_detected(self) -> None:
        self.write_spec(status="approved", approved_on="2026-09-10")
        self.write_features([feature(status="pending")])
        self.assertNoFails()

        path = os.path.join(self.root, "specs", "REQ-001_a_requirement.md")
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content + "\n## 5. Criteria\n\n1. And also, delete everything.\n")

        self.assertFailsWith("changed AFTER being approved")

    def test_approved_without_a_fingerprint_fails(self) -> None:
        self.write_spec(
            body=(
                "---\nid: REQ-001\ntitle: T\nstatus: approved\n"
                "priority: high\napproved_on: 2026-09-10\n---\n# REQ-001\n"
            )
        )
        self.write_features([feature(status="pending")])
        self.assertFailsWith("has no approved_hash")

    def test_touching_the_change_log_does_not_void_the_approval(self) -> None:
        # §7 and §8 change legitimately after approval.
        self.write_spec(status="approved", approved_on="2026-09-10")
        self.write_features([feature(status="pending")])
        path = os.path.join(self.root, "specs", "REQ-001_a_requirement.md")
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n## 8. Change log\n\n| 2 | 2026-09-11 | another feature derived |\n")
        self.assertNoFails()

    def test_the_fingerprint_ignores_the_front_matter(self) -> None:
        body = "# T\n\n## 3. Scope\n\nSearch notes.\n"
        one = vr.spec_fingerprint("---\nid: REQ-001\nstatus: draft\n---\n" + body)
        two = vr.spec_fingerprint("---\nid: REQ-001\nstatus: approved\nround: 9\n---\n" + body)
        self.assertEqual(one, two)

    def test_the_fingerprint_ignores_trailing_whitespace(self) -> None:
        one = vr.spec_fingerprint("---\na: b\n---\n## 3. Scope\n\nSomething.\n")
        two = vr.spec_fingerprint("---\na: b\n---\n## 3. Scope   \n\nSomething.  \n")
        self.assertEqual(one, two)


class TestFrontMatterParser(unittest.TestCase):
    def test_it_strips_quotes(self) -> None:
        fields, repeated = vr.parse_frontmatter("---\ntitle: \"Quoted\"\n---\n")
        self.assertEqual(fields, {"title": "Quoted"})
        self.assertEqual(repeated, [])

    def test_it_does_not_truncate_a_title_with_a_hash(self) -> None:
        fields, _ = vr.parse_frontmatter("---\ntitle: Fix bug #123\n---\n")
        self.assertEqual(fields["title"], "Fix bug #123")

    def test_it_reports_repeated_keys(self) -> None:
        fields, repeated = vr.parse_frontmatter(
            "---\nstatus: draft\nstatus: approved\n---\n"
        )
        self.assertEqual(fields["status"], "draft")
        self.assertEqual(repeated, ["status"])

    def test_no_opening_delimiter_returns_none(self) -> None:
        self.assertIsNone(vr.parse_frontmatter("# Just a heading\n"))


if __name__ == "__main__":
    unittest.main()
