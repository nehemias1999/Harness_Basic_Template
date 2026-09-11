---
description: Runs the full harness cycle on the next pending feature.
---

Take the next `pending` feature from `feature_list.json` — the one with the
**highest priority** (`critical` > `high` > `medium` > `low`) and, at equal
priority, the lowest `id` — and run the full harness cycle as `leader`.

**What it triggers:**

1. The verifier (`./init.ps1` on Windows, `./init.sh` on POSIX). If it is red,
   you stop here and report.
2. Record the chosen feature and the plan in `progress/current.md`.
3. Launch an `implementer` subagent with the feature. Instruct it to write its
   report to `progress/impl_<feature>.md` and return **only the reference**.
4. When it finishes, launch a `reviewer` subagent. Its report goes to
   `progress/review_<feature>.md`.
5. If `APPROVED` → you close the feature: `status: "done"`, an entry in
   `progress/history.md`, an empty `progress/current.md`, a green verifier.
   If `CHANGES_REQUESTED` → you relaunch the implementer passing it the **path**
   of the review, not its content.

**Files it touches:** `feature_list.json` (the `status` field, and only to
close: moving to `in_progress` is done by the implementer when it takes the
feature), `progress/current.md`, `progress/history.md`,
`progress/impl_<feature>.md`, `progress/review_<feature>.md`, and `src/` +
`tests/` (through the implementer, never you directly).

**If there are no `pending` features:** say so and stop. Do not invent one.

- If there are also features in `draft`, the problem is not a lack of work:
  there are requirements waiting for the human's OK. Tell them which ones and
  suggest `/approve <ids>` or `/approve-all`.
- If there are no `draft` ones either, the project has no scope yet:
  `/requirements`.

**`specs/` is read-only in this cycle.** If an `acceptance` criterion is wrong,
what is wrong is the requirement: you stop and say so, you do not rewrite it.
