# Feature notes — the task list as a vault

> The exact, field-by-field anatomy of a feature note. The authoritative shape
> lives in `features/_template.md`; this file explains *why* each field exists
> and who may touch it. The validator that enforces it is
> `scripts/validate_features.py`.

## One note per feature

Every feature of the project is a single Markdown file in `features/`:

```
features/F-<id>_<name>.md
```

The **file name is the identity**: `F-`, then a zero-padded id of at least
three digits, then `_`, then a `snake_case` name — `F-001_auth_login.md`. The
harness parses id and name from the file name and **ignores the `id` and
`name` values inside the front matter** (if present, they are overwritten).
Rename the file if you must change either.

Two notes break the pattern on purpose and are **ignored** by the validators
because of the leading underscore:

- `features/_project.md` — the project's name and description;
- `features/_template.md` — the shape to copy when the analyst derives a
  feature.

## The front matter

```yaml
---
title: Readable feature title
description: What it does and why, in 1-2 sentences.
spec: "[[REQ-001_requirement_name]]"
priority: high
status: draft
acceptance:
  - "an acceptance criterion, verifiable and concrete"
  - "another acceptance criterion"
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
tags:
  - feature
---
```

Key by key:

| Key | Required | Meaning |
|-----|----------|---------|
| `title` | yes | One-line human-readable summary. |
| `description` | yes | 1-2 sentences: what it does and why. |
| `spec` | yes | A **wikilink** to the requirement it was derived from: `[[REQ-001_name]]`. This is the traceability edge. |
| `priority` | yes | `critical` > `high` > `medium` > `low`. Inherited from the requirement; the analyst may **lower** it, never raise it. |
| `status` | yes | The state machine: `draft` → `pending` → `in_progress` → `done`, plus `blocked`. |
| `acceptance` | yes | The criteria from section 5 of the spec, transferred **mechanically** — a criterion that will not transfer is a badly written criterion, not a reason to paraphrase. One per `- "..."` line. |
| `created` / `updated` | yes | Dates, `YYYY-MM-DD`. |
| `tags` | no | Anything; `feature` is conventional. |

Everything before the closing `---` must be flat `key: value`. The only lists
(`acceptance` and `tags`) are written as indented `- "item"` lines. No
PyYAML is involved: `scripts/features_io.py` parses this shape directly.

## The state machine

| Status | What it means | Who moves it |
|--------|---------------|--------------|
| `draft` | Derived, but its requirement is not approved yet. Inert: nothing develops on it. | the `analyst`, when it creates the feature |
| `pending` | The requirement is approved and the feature is waiting to be built. | `scripts/approve.py` when the human runs `/approve <ids>` |
| `in_progress` | Someone is implementing it. | the `implementer`, when it takes the feature |
| `done` | Implemented and reviewed. | the `leader`, **only after** a reviewer's `APPROVED` |
| `blocked` | Something external stops it; the reason lives in `progress/current.md`. | the `implementer` or the `leader` |

Hard rules that cannot be expressed as a table:

- A feature outside `draft` is only legal if its requirement is `approved`
  (`scripts/validate_requirements.py` enforces it).
- At most **one** feature may be `in_progress` at a time.
- `done` requires `progress/impl_<name>.md` and `progress/review_<name>.md`,
  the latter carrying a `Verdict: APPROVED` line, and at least one test file
  in `tests/`. Writing `done` by hand is possible but stays red until those
  artefacts exist.

## Validation

```bash
python scripts/validate_features.py            # project root (.)
python scripts/validate_features.py /other/repo
```

Errors print one `[FAIL]` line per problem and exit `1`. The work order of
`pending` features (priority, then id) is also computed here, and printed by
the verifier's section 4 — do not re-derive it by eye.

## See also

- `docs/obsidian.md` — the vault as a whole, opening it, and the dashboard.
- `features/_template.md` — the file to copy when creating a feature.
- `scripts/features_io.py` — the parser used by every migration script.