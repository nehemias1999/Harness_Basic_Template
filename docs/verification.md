# Verification — How to prove the work actually works

> Golden rule: **the agent does not say "it works", it proves it**.
> Every feature ends with runnable evidence, not with assertions.

## Levels of verification

### Level 0 — The requirement was approved (mandatory)

Before proving that something works you have to be able to prove that it
**had to be built**. The proof is not a sentence in the chat: it is
`status: approved` in the spec under `specs/` and the feature in `pending` or
beyond. Section 5 of the verifier checks it
(`scripts/validate_requirements.py`), and without that nothing below counts:
code that passes every test for something nobody asked for is still wasted
work.

### Level 1 — Unit tests (mandatory)

Every public function in `src/` has at least one test in `tests/` that:

1. Covers the happy path.
2. Covers at least one error path if the function can fail.

```bash
python -m unittest discover -s tests -v
```

### Level 2 — Interface integration test (mandatory for UI/CLI features)

Features that add commands or endpoints are verified by running the real code
against a temporary directory, not against the developer's own state:

```python
import os
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    env = {**os.environ, "<STATE_VAR>": os.path.join(tmp, "state.json")}
    out = subprocess.check_output(
        [sys.executable, "-m", "src.<module>", "<command>", "<arg>"],
        env=env, text=True,
    )
    assert "<expected fragment>" in out
```

`sys.executable` rather than a literal `python3`: that way the test uses the
same interpreter on Windows and on Linux.

### Level 3 — Manual smoke test (optional but recommended)

Before closing the session, run an end-to-end flow against a temporary file
and delete it afterwards.

```powershell
# Windows / PowerShell
$env:<STATE_VAR> = "$env:TEMP\smoke_state.json"
python -m src.<module> <command> <arg>
Remove-Item $env:<STATE_VAR>
```

```bash
# POSIX
<STATE_VAR>="${TMPDIR:-/tmp}/smoke_state.json" python -m src.<module> <command> <arg>
rm "${TMPDIR:-/tmp}/smoke_state.json"
```

## Antipatterns (do not do this)

- ❌ "I added the command, it should work." → a runnable test is missing.
- ❌ A test that only checks the function does not raise. → it has to check the
  concrete result.
- ❌ Mocking the filesystem. → use a real `tempfile.TemporaryDirectory()`.
- ❌ Absolute or user-specific paths in tests. → always temporary ones.
- ❌ Marking the feature `done` without a passing verifier.

## Final check before closing

```powershell
./init.ps1          # Windows — must end with [OK] Environment ready
```

```bash
./init.sh           # POSIX / WSL / CI — same result
```

If the verifier is red, do **not** mark anything as `done`. Record the blocker
in `progress/current.md` and leave the feature `blocked` in
`feature_list.json`.

Watch out for one case the verifier distinguishes on purpose: **0 tests is a
`[WARN]`, not an `[OK]`**. A repo with no tests is not green, it is
unverified. See `docs/scripts.md`.
