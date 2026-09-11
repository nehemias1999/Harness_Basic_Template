---
id: REQ-00N
title: <One line, in business language>
status: draft
priority: medium
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
approved_on:
approved_hash:
round: 1
---

<!-- Requirement template. The `analyst` agent writes it, a human reads it.
     Size target: under 80 lines. If it does not fit, it is two requirements.

     The front matter is the ONLY thing scripts/validate_requirements.py reads:
     keep it to flat `key: value` pairs, no lists and no nesting.

     Statuses: draft (under analysis) · approved (signed by the human) ·
     discarded (the human dropped it; the file stays as history).
     Priority: critical · high · medium · low. Its features inherit it.

     `approved_on` and `approved_hash` are written by scripts/approve.py when
     the human signs (`/approve <id>`). Do not fill them in by hand. The
     fingerprint covers this file's content (minus §7 and §8, which change
     afterwards): if somebody edits the criteria of an already approved
     requirement, the verifier says so instead of leaving the reviewer judging
     against something nobody read.

     This file starts with `_`, so the validator ignores it: that is why it can
     keep its <placeholders>. -->

# REQ-00N — <title>

## 1. Origin (the human's words, verbatim)

> <paste here what the human asked for, without rewriting it or "improving" it>

Full intake: `specs/_intake.md#<date>`.

## 2. Problem and goal

<2-4 sentences: what hurts today and what we want to achieve. Not the solution.>

## 3. Scope

**Includes:** <short list>

**Does not include:** <short list — this is what keeps the scope from growing on its own>

## 4. Expected behaviour

- **Happy path:** given <context>, when <action>, then <result>.
- **Errors:** when <case>, <what the system does> (message and exit code).

## 5. Acceptance criteria

<Numbered and verifiable. The features' `acceptance` comes from here, one by
one. If a criterion cannot be turned into a test, it is badly written: "fast"
is not a criterion, "responds in under 200 ms over 10,000 notes" is.>

1. <criterion>
2. <criterion>

## 6. Assumptions and open questions

<Everything they did not tell you and that you need. None of this gets resolved
by inventing. While an unticked `- [ ]` box remains, the requirement CANNOT be
approved: scripts/validate_requirements.py blocks it.>

- **Assumption (unconfirmed):** <what we are assuming and nobody has confirmed>
- [ ] **Q1:** <question that blocks or changes a criterion>

## 7. Derived features

<Informative, for the human. The truth lives in feature_list.json: the pointer
goes from the feature to the spec, not the other way round, and this table is
NOT validated.>

| feature `name` | id | priority | which criteria it covers |
|----------------|----|----------|--------------------------|
| <snake_case_name> | <id> | <inherited, or lower with a reason> | 1, 2 |

## 8. Change log

| round | date | what changed | requested by |
|-------|------|--------------|--------------|
| 1 | <YYYY-MM-DD> | initial version | <human> |
