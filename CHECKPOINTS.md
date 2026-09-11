# CHECKPOINTS — Assessing the final state

> In multi-agent systems you do not assess the journey, you assess the
> destination. These are the objective checkpoints a judge (human or AI) can
> use to decide whether the project is healthy.

## C1 — The harness is complete

- [ ] The harness base files exist. Section 2 of the verifier checks them:
      `AGENTS.md`, `CLAUDE.md`, `CHECKPOINTS.md`, `README.md`,
      `feature_list.json`, `progress/current.md`, `progress/history.md`,
      `specs/_req_template.md` and the four `docs/`.
- [ ] The 4 docs exist: `docs/architecture.md`, `docs/conventions.md`,
      `docs/verification.md`, `docs/scripts.md`.
- [ ] The verifier finishes with exit code 0. (In the uninstantiated template
      it exits 1 on purpose: section 3 demands configuring the project first.)
- [ ] Every path mentioned in `CLAUDE.md`, `AGENTS.md` and `README.md` exists
      (no dangling references).
- [ ] `specs/` exists with at least one requirement, or the project has not
      started analysis yet (in which case there is no code either).

## C2 — The state is coherent

- [ ] At most one feature `in_progress` in `feature_list.json`.
- [ ] Every `done` feature has associated tests that pass, and both of its
      reports (`impl_` and `review_`) with an `APPROVED` verdict. Section 4 of
      the verifier checks it.
- [ ] `progress/current.md` is empty or describes the active session (it holds
      no leftovers from previous sessions).
- [ ] `feature_list.json` no longer carries the `<YOUR_PROJECT>` placeholder.
- [ ] No feature outside `draft` hangs off an unapproved requirement.
- [ ] Every `approved` requirement has at least one feature referencing it, and
      every feature points at a `spec` that exists.
- [ ] No approved requirement changed after being approved (`approved_hash`).

## C3 — The code respects the architecture

- [ ] `src/` contains only the modules planned in `docs/architecture.md`.
      (That `architecture.md` is written **and approved** is checked by section
      3 of the verifier as soon as there is a feature outside `draft`; if you
      are reading this with a green verifier and code in `src/`, it is done.)
- [ ] There are no external dependencies: no `requirements.txt` with content,
      and no imports outside the stdlib (bar an exception documented in a
      feature).
- [ ] There are no stray debug `print()` calls and no context-free TODOs.
- [ ] Errors go to `stderr` with a non-zero exit code, not through `print()`.

## C4 — The verification is real

- [ ] If `src/` has modules, `tests/` has at least one test per module.
      (In a freshly instantiated project this checkbox does not apply yet.)
- [ ] Section 6 of the verifier shows `[OK]`, not `[WARN]`: 0 tests means
      "unverified", not "green". While no feature is closed it is a warning; as
      soon as one is `done`, section 4 turns it into a `[FAIL]`.
- [ ] Tests that touch disk use `tempfile.TemporaryDirectory()`, not filesystem
      mocks and not user-specific paths.
- [ ] `python -m unittest discover -s tests -v` shows > 0 tests, all green.

## C5 — The session closed properly

- [ ] There are no suspicious untracked files (`*.tmp`, `__pycache__` outside
      the `.gitignore`).
- [ ] `progress/history.md` has an entry for the last session.
- [ ] The last feature worked on is reflected in its correct status.
- [ ] The implementer's report (`progress/impl_<feature>.md`) and the
      reviewer's (`progress/review_<feature>.md`) exist for the closed feature.
- [ ] If there was an analysis round, its report (`progress/intake_r<N>.md`)
      exists and no requirement was left in `draft` without the human knowing.

---

**How to use this file:** a reviewer agent (`.claude/agents/reviewer.md`) walks
every checkbox, marks `[x]` or `[ ]`, and rejects closing the session if any
box in C1-C5 is left empty. A checkbox that does not apply is marked `[-]` with
the reason next to it.
