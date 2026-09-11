---
description: Opens or continues a requirements analysis round with the analyst agent.
---

Turn the requirements the human just gave you into reviewable SDD specs. You
act as `leader`: you do not analyse, you launch the `analyst`.

It is valid at any point in the project, not just at the start. If there is a
feature `in_progress`, **do not touch it**: the analyst only creates features in
`draft`, which are inert, so analysing and developing coexist without stepping
on each other.

**What it triggers:**

1. The verifier (`./init.ps1` on Windows, `./init.sh` on POSIX). If it is red
   for anything other than the architecture being a draft, you stop and report.
2. Record the round in `progress/current.md` — **one line**, without deleting
   whatever the active session has there.
3. Launch an `analyst` subagent passing it the human's requirements
   **verbatim**, not your summary of them. Instruct it to write into `specs/`
   and `progress/intake_r<N>.md`, and to return the reference plus its
   `## For your review` block.
4. **Relay that block literally**, without adding or summarising, and tell them
   which files to open. Do not narrate what the spec says: if the human asks,
   read the file and quote it.

   The open questions are the part that **cannot** stay on disk: the analyst
   does not talk to the human, so if you do not relay them, nobody asks them.
   Pass them through as they are, numbered, before anything else.
5. Wait. If they add, change or drop something → back to step 3 with one more
   round. If they give the OK, they name the approval by id themselves:
   `/approve 1 2`, or `/approve-all`. You do not run it on your own.

**Files it touches:** `specs/REQ-*.md`, `specs/_intake.md`,
`docs/architecture.md` (draft), `feature_list.json` (draft features only),
`progress/intake_r<N>.md`, `progress/current.md`. Never `src/` or `tests/`.

**A "sure, go ahead" in the chat approves nothing.** The approval is
`/approve <ids>` or `/approve-all`, which leave it written in git.
