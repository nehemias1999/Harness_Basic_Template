"""Tests for scripts/validate_feature_list.py.

They live in `scripts/tests/` and not in `tests/` for the same reason as their
neighbours: `tests/` belongs to the project, and the verifier discovers it. See
the header of test_validate_requirements.py.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_feature_list as vfl  # noqa: E402


SANE_RULES = {
    "one_feature_at_a_time": True,
    "require_tests_to_close": True,
    "work_order": "priority_then_id",
    "valid_status": list(vfl.VALID_STATUS),
}


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


class FeatureListCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, features: list, rules: dict | None = None) -> str:
        payload = {
            "project": "test",
            "rules": SANE_RULES if rules is None else rules,
            "features": features,
        }
        path = os.path.join(self.root, "feature_list.json")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return path

    def create_test_file(self) -> None:
        os.makedirs(os.path.join(self.root, "tests"), exist_ok=True)
        with open(os.path.join(self.root, "tests", "test_something.py"), "w") as handle:
            handle.write("# a test\n")

    def create_reports(self, name: str = "a_feature", verdict: str = "APPROVED") -> None:
        os.makedirs(os.path.join(self.root, "progress"), exist_ok=True)
        with open(os.path.join(self.root, "progress", f"impl_{name}.md"), "w") as handle:
            handle.write("# implementer report\n")
        with open(os.path.join(self.root, "progress", f"review_{name}.md"), "w") as handle:
            handle.write(f"# review\n\n**Verdict:** {verdict}\n")

    def close_properly(self, name: str = "a_feature") -> None:
        """Everything the harness demands for a feature to be allowed in `done`."""
        self.create_test_file()
        self.create_reports(name)

    def errors(self, features: list, rules: dict | None = None) -> list[str]:
        return vfl.validate(self.write(features, rules))

    def assertErrorWith(self, needle: str, features: list, rules: dict | None = None) -> None:
        errs = self.errors(features, rules)
        self.assertTrue(any(needle in e for e in errs), f"{needle!r} is not in {errs}")


class TestHappyPath(FeatureListCase):
    def test_an_empty_list_is_valid(self) -> None:
        self.assertEqual(self.errors([]), [])

    def test_a_well_formed_feature(self) -> None:
        self.assertEqual(self.errors([feature()]), [])

    def test_work_order_is_priority_then_id(self) -> None:
        features = [
            feature(id=1, name="a", priority="critical", status="pending"),
            feature(id=2, name="b", priority="high", status="pending"),
            feature(id=3, name="c", priority="critical", status="pending"),
            feature(id=4, name="d", priority="low", status="draft"),
        ]
        queue = [f["id"] for f in vfl.work_order(features)]
        self.assertEqual(queue, [1, 3, 2])


class TestHarnessRules(FeatureListCase):
    """The JSON declares the rules; it does not decide them."""

    def test_one_feature_at_a_time_cannot_be_switched_off(self) -> None:
        rules = dict(SANE_RULES, one_feature_at_a_time=False)
        self.assertErrorWith('"rules.one_feature_at_a_time"', [feature()], rules)

    def test_switching_it_off_does_not_avoid_the_two_in_progress_error(self) -> None:
        rules = dict(SANE_RULES, one_feature_at_a_time=False)
        errs = self.errors(
            [
                feature(id=1, name="a", status="in_progress"),
                feature(id=2, name="b", status="in_progress"),
            ],
            rules,
        )
        self.assertTrue(any("in_progress (max 1)" in e for e in errs), errs)

    def test_statuses_cannot_be_invented(self) -> None:
        rules = dict(SANE_RULES, valid_status=list(vfl.VALID_STATUS) + ["ready"])
        self.assertErrorWith('"rules.valid_status"', [feature()], rules)

    def test_an_invented_status_is_still_invalid(self) -> None:
        rules = dict(SANE_RULES, valid_status=list(vfl.VALID_STATUS) + ["ready"])
        self.assertErrorWith('invalid status "ready"', [feature(status="ready")], rules)

    def test_rules_that_is_not_an_object(self) -> None:
        self.assertErrorWith('"rules" must be an object', [], "a string")

    def test_require_tests_to_close_does_not_switch_off(self) -> None:
        rules = dict(SANE_RULES, require_tests_to_close=False)
        self.assertErrorWith('"rules.require_tests_to_close"', [feature()], rules)


class TestFeatureShape(FeatureListCase):
    def test_a_required_field_is_missing(self) -> None:
        without_spec = feature()
        del without_spec["spec"]
        self.assertErrorWith('the "spec" field is missing', [without_spec])

    def test_duplicate_id(self) -> None:
        self.assertErrorWith(
            "duplicate id", [feature(id=1, name="a"), feature(id=1, name="b")]
        )

    def test_duplicate_name(self) -> None:
        self.assertErrorWith(
            "duplicate name", [feature(id=1, name="same"), feature(id=2, name="same")]
        )

    def test_name_that_is_not_snake_case(self) -> None:
        self.assertErrorWith("snake_case", [feature(name="A Feature")])

    def test_id_that_is_not_an_integer(self) -> None:
        self.assertErrorWith("integer >= 1", [feature(id="1")])

    def test_empty_title(self) -> None:
        self.assertErrorWith('"title" cannot be empty', [feature(title="   ")])

    def test_spec_with_an_invalid_path(self) -> None:
        self.assertErrorWith('"spec" must be a', [feature(spec="docs/other.md")])

    def test_invalid_priority(self) -> None:
        self.assertErrorWith("invalid priority", [feature(priority="super_urgent")])

    def test_empty_acceptance(self) -> None:
        self.assertErrorWith('"acceptance" must be an array', [feature(acceptance=[])])

    def test_acceptance_with_empty_criteria(self) -> None:
        self.assertErrorWith("criteria", [feature(acceptance=["fine", "  "])])

    def test_feature_that_is_not_an_object(self) -> None:
        self.assertErrorWith("is not an object", ["this is not a feature"])


class TestClosingAFeature(FeatureListCase):
    """Nobody approves their own work: closing demands tests and both reports."""

    def test_done_without_a_single_test_fails(self) -> None:
        self.create_reports()
        self.assertErrorWith("not a single test", [feature(status="done")])

    def test_done_without_the_implementer_report_fails(self) -> None:
        self.create_test_file()
        os.makedirs(os.path.join(self.root, "progress"), exist_ok=True)
        with open(os.path.join(self.root, "progress", "review_a_feature.md"), "w") as h:
            h.write("**Verdict:** APPROVED\n")
        self.assertErrorWith("implementer's report", [feature(status="done")])

    def test_done_without_a_review_fails(self) -> None:
        self.create_test_file()
        os.makedirs(os.path.join(self.root, "progress"), exist_ok=True)
        with open(os.path.join(self.root, "progress", "impl_a_feature.md"), "w") as h:
            h.write("# report\n")
        self.assertErrorWith("reviewer's report", [feature(status="done")])

    def test_done_with_changes_requested_fails(self) -> None:
        self.create_test_file()
        self.create_reports(verdict="CHANGES_REQUESTED")
        self.assertErrorWith("requested changes", [feature(status="done")])

    def test_done_with_a_review_that_says_nothing_fails(self) -> None:
        self.create_test_file()
        os.makedirs(os.path.join(self.root, "progress"), exist_ok=True)
        with open(os.path.join(self.root, "progress", "impl_a_feature.md"), "w") as h:
            h.write("# report\n")
        with open(os.path.join(self.root, "progress", "review_a_feature.md"), "w") as h:
            h.write("# review\n\nLooks fine to me.\n")
        self.assertErrorWith("does not say APPROVED", [feature(status="done")])

    def test_a_properly_closed_feature_passes(self) -> None:
        self.close_properly()
        self.assertEqual(self.errors([feature(status="done")]), [])

    def test_with_no_done_features_nothing_is_demanded(self) -> None:
        self.assertEqual(self.errors([feature(status="pending")]), [])


class TestTheSchemaDoesNotDrift(unittest.TestCase):
    """The schema is documentation and nobody loads it: without this, it drifts.

    `schema/feature_list.schema.json` describes the format and
    `validate_feature_list.py` enforces it. They are two sources of truth, and
    the only way they will not say different things in six months is to compare
    them here.
    """

    @classmethod
    def setUpClass(cls) -> None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(root, "schema", "feature_list.schema.json"), encoding="utf-8") as h:
            cls.schema = json.load(h)
        cls.feature = cls.schema["definitions"]["feature"]

    def test_the_statuses_match(self) -> None:
        self.assertEqual(
            self.feature["properties"]["status"]["enum"], list(vfl.VALID_STATUS)
        )

    def test_the_priorities_match(self) -> None:
        self.assertEqual(
            self.feature["properties"]["priority"]["enum"], list(vfl.PRIORITIES)
        )

    def test_the_required_fields_match(self) -> None:
        self.assertEqual(
            sorted(self.feature["required"]), sorted(vfl.REQUIRED_FEATURE_KEYS)
        )

    def test_the_patterns_match(self) -> None:
        self.assertEqual(self.feature["properties"]["name"]["pattern"], vfl.NAME_RE.pattern)
        self.assertEqual(self.feature["properties"]["spec"]["pattern"], vfl.SPEC_RE.pattern)

    def test_the_declared_rules_are_in_the_schema(self) -> None:
        declared = set(self.schema["properties"]["rules"]["properties"])
        self.assertTrue(
            set(vfl.FIXED_RULES).issubset(declared),
            f"the schema does not declare {set(vfl.FIXED_RULES) - declared}",
        )


class TestTheFile(FeatureListCase):
    def test_missing_file(self) -> None:
        errs = vfl.validate(os.path.join(self.root, "does_not_exist.json"))
        self.assertEqual(len(errs), 1)
        self.assertIn("does not exist", errs[0])

    def test_invalid_json(self) -> None:
        path = os.path.join(self.root, "feature_list.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ broken")
        self.assertIn("is not valid JSON", vfl.validate(path)[0])


if __name__ == "__main__":
    unittest.main()
