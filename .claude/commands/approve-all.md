---
description: Signs every requirement in draft in one go.
---

Shortcut for `/approve all`. Run:

```bash
python scripts/approve.py all
```

Before running it, **tell the human what it is about to sign**: the ids and
titles of the requirements in `draft`, taken from `specs/`. Approving
everything at once is convenient when you have just reviewed a whole round, and
an expensive mistake when one you had not read slipped in. Let them see it
before, not after.

If they also want to sign `docs/architecture.md`, that is named separately:
`/approve all architecture`.

The rest of the walkthrough — verifier, entry in `progress/history.md`, which
feature comes next — lives in `/approve`, and it is the same.
