---
description: Signs the requirements you name by id, and moves their features to pending.
argument-hint: 1 2 [architecture]
---

The human named what to approve: **`$ARGUMENTS`**. Turn that into verifiable
state by running:

```bash
python scripts/approve.py $ARGUMENTS
```

That is all you have to do. The script takes care of the four things that have
to be touched at once — `status: approved`, the date, the content fingerprint
and moving its features from `draft` to `pending` — plus the change-log row. Do
not do it by hand: halfway through, the repository is incoherent, and this is
exactly the kind of mechanical work where an agent skips a step.

**What it accepts:**

| What the human writes | What gets signed |
|---|---|
| `1 2` · `001 002` · `REQ-001` | those requirements |
| `all` | every requirement in `draft` |
| `architecture` | additionally, `docs/architecture.md` |

(`todos` and `arquitectura` work too: the script is forgiving about the form,
just as it is with ids. English is canonical, like the commands.)

`architecture` goes separately on purpose: it is the criterion the reviewer
judges **all** the code against, and approving it as a side effect of a
requirement would be the oversight the harness is trying to prevent. If the
human did not name it, do not add it yourself.

**Once the script finishes:**

1. Run the verifier. It should be green except for the `[WARN]` about 0 tests.
2. Record in `progress/history.md` what was approved.
3. Tell them which feature comes first by priority — the verifier prints it in
   its section 4 — and if that displaces one that is `in_progress`, give them
   both ways out: finish it, or move it to `blocked` with a reason. **The
   decision to interrupt is theirs.**

**If the script refuses**, do not look for a way around it: repeat the reason
verbatim. It refuses for three reasons, and all three are good ones — the
requirement has unanswered questions, it was already approved, or
`docs/architecture.md` still has holes. None of them is fixed by editing the
spec by hand.

**A "sure, go ahead" in the chat approves nothing.** What approves is this
command, with the ids written out, and it lands in git.
