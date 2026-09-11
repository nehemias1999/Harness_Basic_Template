---
description: Closes the session following the lifecycle in AGENTS.md §5.
---

Close the current session following the lifecycle in `AGENTS.md §5`. Walk it in
order and report each step:

1. **Green verifier.** Run `./init.ps1` (Windows) or `./init.sh` (POSIX). If it
   is red, **do not close**: report what fails and stop.
2. **Feature status.** Check the verdict in `progress/review_<feature>.md`:
   - `APPROVED` → `status: "done"` in `feature_list.json`.
   - `CHANGES_REQUESTED` or no review → leave it `in_progress`, or `blocked` if
     there is a real blocker, and say so explicitly.
3. **History.** Append an entry to `progress/history.md` in the format that
   file documents (date, feature, agent, result, files touched, verification,
   notes).
4. **Reset.** Empty `progress/current.md`, leaving only the template.
5. **Half-finished analysis round.** If there are requirements in `draft`, say
   so before closing, with their ids: the human decides between approving them
   (`/approve 1 2`) or leaving them for the next session. A `draft` survives
   the close perfectly well — what must not happen is closing in silence and
   nobody remembering something was waiting for their OK.
6. **Cleanliness.** Check `git status`: no `*.tmp`, no `__pycache__` outside
   the `.gitignore`, no debug `print()` calls and no context-free TODOs.
7. **Final summary** in 3-5 lines: what was closed, what is left, and the first
   step of the next session.

**Files it touches:** `feature_list.json`, `progress/current.md`,
`progress/history.md`. Never `src/`, `tests/` or `specs/`.
