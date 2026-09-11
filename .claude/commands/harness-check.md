---
description: Audits the repository against checkpoints C1-C5 in CHECKPOINTS.md.
---

Audit the state of the repository against `CHECKPOINTS.md` and report the
result. This is a **read-only** review: do not fix anything, only report.

**What to do:**

1. Run the verifier (`./init.ps1` or `./init.sh`) and keep its output.
2. Walk the five C1-C5 blocks of `CHECKPOINTS.md`, checkbox by checkbox. Mark
   each one:
   - `[x]` satisfied
   - `[ ]` not satisfied → cite the concrete file and line
   - `[-]` does not apply yet → say why (for example, no code in the project yet)
3. Check there are no **dangling references**, with the script that does it for
   you: `python scripts/validate_references.py .`. It walks the paths mentioned
   in the reference documentation and the `spec` pointers in
   `feature_list.json`.
4. Run the harness's own tests and report the result:
   `python -m unittest discover -s scripts/tests -v`. The verifier does not run
   them on purpose (see `docs/scripts.md`), so if nobody looks at them here,
   nobody looks at them at all.
5. Close with a one-line verdict: `HEALTHY`, `HEALTHY WITH WARNINGS` or
   `BROKEN`, plus the 3 most urgent fixes if it is not healthy.

**Do not touch any file.** If you want to leave a trace, write the report to
`progress/harness_check.md` and return only the reference.
