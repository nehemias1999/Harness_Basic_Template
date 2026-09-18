"""Tests for scripts/validate_features.py.

They live in `scripts/tests/` and not in `tests/` for the same reason as their
neighbours: `tests/` belongs to the project, and the verifier discovers it. See
the header of test_validate_requirements.py.

The scope lives as one note per feature in `features/F-<id>_<name>.md`, so
these tests write notes (flat YAML front matter, exactly as the templates do)
instead of a JSON list, and call `validate(root)` on the directory.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import features_io  # noqa: E402
import validate_features as vfl  # noqa: E402


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


def feature(**kwargs) -> dict:
    base = {
        "id": 1,
        "name": "a_feature",
        "title": "A feature",
        "description": "What it does.",
        "spec": "[[REQ-001_a_requirement]]",
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
        self.features_dir = os.path.join(self.root, "features")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, features: list) -> None:
        """Writes one note per feature: `features/F-{id:03d}_{name}.md`."""
        os.makedirs(self.features_dir, exist_ok=True)
        for feat in features:
            fid = int(feat["id"])
            name = feat["name"]
            overrides = dict(feat.get("_fm", {}))
            fields = {k: v for k, v in feat.items() if not k.startswith("_")}
            fields["id"] = fid
            fields["name"] = name
            fields.update(overrides)
            rel = os.path.join(self.features_dir, f"F-{fid:03d}_{name}.md")
            with open(rel, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(_frontmatter(fields) + "\n")

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

    def errors(self, features: list) -> list[str]:
        self.write(features)
        return vfl.validate(self.root)

    def assertErrorWith(self, needle: str, features: list) -> None:
        errs = self.errors(features)
        self.assertTrue(any(needle in e for e in errs), f"{needle!r} is not in {errs}")


class TestHappyPath(FeatureListCase):
    def test_an_empty_scope_is_valid(self) -> None:
        self.assertEqual(self.errors([]), [])

    def test_a_well_formed_feature(self) -> None:
        self.assertEqual(self.errors([feature()]), [])

    def test_work_order_is_priority_then_id(self) -> None:
        self.write(
            [
                feature(id=1, name="a", priority="critical", status="pending"),
                feature(id=2, name="b", priority="high", status="pending"),
                feature(id=3, name="c", priority="critical", status="pending"),
                feature(id=4, name="d", priority="low", status="draft"),
            ]
        )
        loaded, _ = features_io.load_features(self.root)
        queue = [f["id"] for f in vfl.work_order(loaded)]
        self.assertEqual(queue, [1, 3, 2])


class TestFeatureShape(FeatureListCase):
    def test_a_required_field_is_missing(self) -> None:
        for key in ("title", "description", "spec", "priority", "status"):
            without = feature()
            del without[key]
            self.assertErrorWith(f'the "{key}" field is missing', [without])
        without_acceptance = feature()
        del without_acceptance["acceptance"]
        self.assertErrorWith('the "acceptance" field is missing', [without_acceptance])

    def test_duplicate_id(self) -> None:
        self.assertErrorWith(
            "duplicate id", [feature(id=1, name="a"), feature(id=1, name="b")]
        )

    def test_duplicate_name(self) -> None:
        self.assertErrorWith(
            "duplicate name", [feature(id=1, name="same"), feature(id=2, name="same")]
        )

    def test_a_file_name_that_is_not_snake_case(self) -> None:
        self.write([])
        with open(
            os.path.join(self.features_dir, "F-001_A Feature.md"), "w", encoding="utf-8"
        ) as handle:
            handle.write(
                _frontmatter(
                    {
                        "title": "x",
                        "description": "y",
                        "spec": "[[REQ-001_x]]",
                        "priority": "high",
                        "acceptance": ["ok"],
                        "status": "draft",
                    }
                )
            )
            handle.write("\n")
        errs = vfl.validate(self.root)
        self.assertTrue(any("does not follow F-<id>_<name>.md" in e for e in errs), errs)

    def test_the_file_name_is_the_authority_on_id(self) -> None:
        # load_features rebuilds the id from the file name: a note whose front
        # matter repeats it differently (here id: 2 in F-001_...) is loaded as
        # the file says, so the scope stays coherent instead of flagging.
        self.write([feature(_fm={"id": 2})])
        loaded, _ = features_io.load_features(self.root)
        self.assertEqual(loaded[0]["id"], 1)
        self.assertEqual(vfl.validate(self.root), [])

    def test_the_file_name_is_the_authority_on_name(self) -> None:
        # Same rule for the name: the implementer's and the reviewer's reports
        # are named after what the file says, not after the contradicted value.
        self.write([feature(_fm={"name": "different"})])
        loaded, _ = features_io.load_features(self.root)
        self.assertEqual(loaded[0]["name"], "a_feature")
        self.assertEqual(vfl.validate(self.root), [])

    def test_empty_title(self) -> None:
        self.assertErrorWith('"title" cannot be empty', [feature(title="   ")])

    def test_spec_that_points_nowhere_usable(self) -> None:
        self.assertErrorWith('"spec" must be a', [feature(spec="docs/other.md")])

    def test_invalid_priority(self) -> None:
        self.assertErrorWith("invalid priority", [feature(priority="super_urgent")])

    def test_invalid_status(self) -> None:
        self.assertErrorWith('invalid status "ready"', [feature(status="ready")])

    def test_empty_acceptance(self) -> None:
        self.assertErrorWith('"acceptance" must be an array', [feature(acceptance=[])])

    def test_acceptance_with_empty_criteria(self) -> None:
        self.assertErrorWith("criteria", [feature(acceptance=["fine", "  "])])


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

    def _review_saying(self, text: str) -> None:
        self.create_test_file()
        os.makedirs(os.path.join(self.root, "progress"), exist_ok=True)
        with open(os.path.join(self.root, "progress", "impl_a_feature.md"), "w") as h:
            h.write("# report\n")
        with open(os.path.join(self.root, "progress", "review_a_feature.md"), "w") as h:
            h.write(text)

    def test_done_with_a_review_that_says_nothing_fails(self) -> None:
        self._review_saying("# review\n\nLooks fine to me.\n")
        self.assertErrorWith("no readable verdict line", [feature(status="done")])

    def test_the_unedited_template_legend_is_not_an_approval(self) -> None:
        # The reviewer template used to hand out `**Verdict:** APPROVED |
        # CHANGES_REQUESTED`. Containment read that as an approval, so a reviewer
        # who filled in nothing still closed the feature. No bad faith required —
        # which is what made it worth a test of its own.
        self._review_saying("# review\n\n**Verdict:** APPROVED | CHANGES_REQUESTED\n")
        self.assertErrorWith("no readable verdict line", [feature(status="done")])

    def test_an_explicit_rejection_is_not_an_approval(self) -> None:
        # "APPROVED" is a substring of "NOT APPROVED".
        self._review_saying("# review\n\n**Verdict:** CHANGES_REQUESTED\n\nThis is NOT APPROVED.\n")
        self.assertErrorWith("requested changes", [feature(status="done")])

    def test_the_word_approved_in_prose_is_not_a_verdict(self) -> None:
        self._review_saying("# review\n\nEverything here could be APPROVED, honestly.\n")
        self.assertErrorWith("no readable verdict line", [feature(status="done")])

    def test_two_verdict_lines_disagreeing_is_not_an_approval(self) -> None:
        self._review_saying("**Verdict:** APPROVED\n\n**Verdict:** CHANGES_REQUESTED\n")
        self.assertErrorWith("no readable verdict line", [feature(status="done")])

    def test_a_properly_closed_feature_passes(self) -> None:
        self.close_properly()
        self.assertEqual(self.errors([feature(status="done")]), [])

    def test_with_no_done_features_nothing_is_demanded(self) -> None:
        self.assertEqual(self.errors([feature(status="pending")]), [])


class TestTheScopeNotes(FeatureListCase):
    """The scope notes themselves: the files validate() sees."""

    def test_the_template_notes_are_not_features(self) -> None:
        self.write([])
        for name in ("_project.md", "_template.md"):
            with open(os.path.join(self.features_dir, name), "w", encoding="utf-8") as h:
                h.write("---\ntitle: template\n---\n")
        self.assertEqual(vfl.validate(self.root), [])

    def test_missing_features_directory(self) -> None:
        errs = vfl.validate(self.root)
        self.assertTrue(any("features/ does not exist yet" in e for e in errs), errs)

    def test_a_note_with_no_front_matter_fails(self) -> None:
        self.write([])
        with open(os.path.join(self.features_dir, "F-001_plain.md"), "w", encoding="utf-8") as h:
            h.write("just a note, no front matter\n")
        errs = vfl.validate(self.root)
        self.assertTrue(any("has no front matter, or it is not closed with ---" in e for e in errs), errs)

    def test_an_unterminated_front_matter_fails(self) -> None:
        self.write([])
        with open(os.path.join(self.features_dir, "F-001_plain.md"), "w", encoding="utf-8") as h:
            h.write("---\nid: 1\n")
        errs = vfl.validate(self.root)
        self.assertTrue(any("not closed with ---" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()