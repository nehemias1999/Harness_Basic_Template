# Harness scripts

> The repository's toolbox. Every script also carries its own documentation
> header (`Get-Help ./init.ps1` in PowerShell, or the first lines of the file);
> here is the overview and the details that do not fit in a header.

| Script | Who runs it | When |
|--------|-------------|------|
| `init.ps1` / `init.sh` | agent, `Stop` hook, reviewer | when starting the session and before any `done` |
| `bootstrap.ps1` / `bootstrap.sh` | human | once, when instantiating a new project from the template |
| `reset.ps1` / `reset.sh` | human | when the current project is finished and the folder is to host the next one |
| `scripts/validate_project_setup.py` | `init.*` (and by hand) | blocks start-up if the project is not configured |
| `scripts/validate_feature_list.py` | `init.*` (and by hand) | whenever the scope needs checking |
| `scripts/validate_requirements.py` | `init.*` (and by hand) | blocks work on an unapproved requirement |
| `scripts/harness_hook.py` | `PostToolUse` and `Stop` hooks | automatic; they block with exit 2 |
| `scripts/approve.py` | `/approve` and `/approve-all` | when the human signs requirements |
| `scripts/validate_references.py` | `/harness-check` and CI | to keep the docs from pointing at missing files |
| `scripts/instantiate.py` | `bootstrap.ps1` and `bootstrap.sh` | the instantiation logic, shared by both platforms |
| `scripts/reset_workspace.py` | `reset.ps1` and `reset.sh` | the reset logic, shared by both platforms |
| `scripts/demo_orchestration.py` | human or agent | to understand or demonstrate the anti-broken-telephone pattern |
| `.github/workflows/harness.yml` | GitHub Actions | on every push and every PR |

---

## `init.ps1` / `init.sh` — the verifier

They are **the same verifier on two platforms**: same 7-section structure, same
`[OK]/[WARN]/[FAIL]` output, same exit code. Use `init.ps1` on Windows and
`init.sh` on WSL, macOS, Linux or CI. If you change one, change the other.

```
1. Environment        Python interpreter found and >= 3.9
2. Base files         the files without which the harness does not work
3. Configuration      delegates to scripts/validate_project_setup.py  (blocking)
4. feature_list.json  delegates to scripts/validate_feature_list.py
5. Requirements       delegates to scripts/validate_requirements.py   (blocking)
6. Tests              discovers and runs tests/
7. Summary            verdict + exit code
```

Section 5 comes **after** 4 on purpose: if `feature_list.json` is malformed,
the reader sees the shape error first rather than a cascade of traceability
errors derived from it.

**Parameters:** both accept `--quiet` / `-Quiet` to shorten the test output.

**Exit codes:** `0` environment ready · `1` something to fix. `[WARN]`s do
**not** block; `[FAIL]`s do.

**Details that matter:**

- **Interpreter detection.** It tries `python`, `py` and `python3`, and
  discards the ones that exist on PATH but run nothing — on Windows the
  Microsoft Store's `python3` alias is a stub that only prints an install
  notice. That is why the script does not trust `command -v` / `Get-Command`:
  it fires a real probe.
- **The uninstantiated template comes out red, and that is correct.** Section 3
  blocks start-up while the project is not configured. A freshly copied repo
  tells you what to run (`bootstrap.ps1`) instead of letting you work on an
  empty harness. It is not a template bug: it is the template doing its job.
- **0 tests is a `[WARN]`, not an `[OK]`.** `unittest discover` over an empty
  folder finishes successfully, so a freshly instantiated repo would look green
  without having verified anything. The verifier counts the tests before
  running them and tells three cases apart: *0 tests* (warning), *green tests*
  (ok), *broken tests* (failure). Once your project has code, a `[WARN]` here
  is an alarm, not noise.

**When it fails:**

| Line | What to do |
|------|------------|
| `No runnable Python found` | install Python >= 3.9 or fix the PATH |
| `Base file missing: X` | the harness is incomplete: restore `X` (see `CHECKPOINTS.md` C1) |
| `This repository is the harness template, NOT INSTANTIATED` | run `./bootstrap.ps1 -Name "..."` |
| `docs/architecture.md has unfilled placeholders` | ask the `analyst` for it (`/requirements`); it is the reviewer's criterion, without it no review is possible |
| `is still "draft" (nobody approved that requirement)` | the human approves it with `/approve <id>`, or the feature goes back to `draft` |
| `"rules.…" says … and the harness works with …` | somebody loosened a harness rule by editing `feature_list.json`: put it back |
| `not a single test in tests/` | a `done` feature with no proof: write the tests or reopen the feature |
| `approved_on … has to be a YYYY-MM-DD date` | put the real approval date in |
| `the front matter repeats …` | the same key appears twice in the spec: keep one |
| `points at specs/... which does not exist` | fix the feature's `spec` field, or restore the file |
| `is approved but no feature references it` | derive its features (`/requirements`) or send the spec back to `draft` |
| `and no approved requirement` | there is code with no approved scope: define and approve the requirements before going on |
| `There are N features in_progress` | close or revert the extra ones: one at a time |
| `Could not discover the tests` | there is an import error in `tests/`; run the discover by hand to see it |
| `There are broken tests` | fix them before going on; do not mark anything `done` |

---

## `bootstrap.ps1` / `bootstrap.sh` — instantiating a project

Turns the template into your project. It runs **once**, by hand, right after
copying the repo.

```powershell
./bootstrap.ps1 -Name "my-project" -WhatIf                          # dry run
./bootstrap.ps1 -Name "my-project" -Description "What it does."     # for real
./bootstrap.ps1 -Name "other" -Force                                # insist on a live project
```

```bash
./bootstrap.sh --name "my-project" --dry-run                        # dry run
./bootstrap.sh --name "my-project" --description "What it does."    # for real
```

| Windows | POSIX | Effect |
|---------|-------|--------|
| `-Name` | `--name` | required; the project's name |
| `-Description` | `--description` | one line; if omitted, the placeholder stays |
| `-Repo` | `--repo` | URL of **your project's** repository; it becomes `origin` |
| `-TemplateRepo` | `--template-repo` | URL of the harness; only if it cannot be worked out from `origin` |
| `-Force` | `--force` | instantiate even if it is already a project, and reset `history.md` |
| `-ResetGit` | `--reset-git` | delete the inherited `.git` and start a new history |
| `-NoGit` | `--no-git` | do not touch git at all |
| `-WhatIf` | `--dry-run` | list the changes without applying them |

**Both are wrappers around `scripts/instantiate.py`**, which is where the logic
lives. They are ~200 lines of decisions about what to delete and what to keep:
keeping them duplicated in PowerShell and bash guaranteed that one day they
would say different things, which is the same reason the validators are shared
Python modules. The wrappers only translate arguments and find the interpreter.

What it touches: `feature_list.json` (name, description, **`features: []`**),
the placeholders in `README.md` and in `docs/architecture.md`, `conventions.md`
and `verification.md`, `progress/current.md`, `progress/history.md`, it deletes
the leftover reports (`progress/explore_*.md`, `impl_*.md`, `review_*.md`,
`intake_*.md`) and it **deletes every requirement in `specs/REQ-*.md`**,
approved ones included.

The list of files with placeholders is explicit on purpose: this file and
`CHECKPOINTS.md` *talk about* the placeholders, so replacing them here would
wreck their own documentation.

**It is not idempotent and it is not harmless**: it empties the scope and
deletes the requirements. That is why it refuses if the repository is already
an instantiated project — it has its own name or requirements in `specs/` — and
you have to pass `-Force` to insist. That is the guardrail that matters; the
script's `ShouldProcess` asks nothing with PowerShell's default configuration.

`progress/history.md` also has its own protection: if it has real entries, it
warns and does not delete it unless `-Force`.

And it is not on the agent's allow list, it is on `deny`: instantiating a
project is a human act.

### What it does with git

The reviewer identifies the files touched in a session by comparing against
history. A project with no repository leaves it working blind, with the only
thing it has left: the implementer's own report, which is exactly who it has to
audit. So the script leaves the repository in shape:

It leaves the workspace with **two remotes**, and the distinction is the whole
model:

| Remote | Points at | What it is for |
|---|---|---|
| `origin` | **your project's** repository | where your work is pushed |
| `template` | the harness's repository | where `reset.*` reads the pristine template from |

| Starting situation | What it does |
|---|---|
| You copied the template (no `.git`) | `git init` + base commit `chore: instantiate the harness for <project>` |
| You **cloned** the template and pass `-Repo` | `template` = the URL `origin` had; `origin` = yours |
| You cloned and pass **no** `-Repo` | `template` = the URL `origin` had, and **`origin` is disconnected** |
| You cloned and pass `-ResetGit` | also deletes the inherited `.git` and starts a clean history |
| `-Repo` equal to the template's URL | it refuses, before writing anything |
| `-NoGit` | nothing, with a `[WARN]` |

Disconnecting the `origin` is not cosmetic: if you clone the template and leave
it alone, **your first `git push` sends the new project to the template's
repository**. When it disconnects it, the closing checklist adds a step 6 with
the `git remote add origin <url>` that is on you — or pass `-Repo` and skip it.

The template's URL is not guessed from its name: it is *whatever `origin` was
when you ran bootstrap*, because that is where you cloned from. A fork with
another name works, and a project of yours legitimately named after the
harness is not mistaken for it.

If git has no identity configured, it sets a provisional local one
(`harness@localhost`) so the base commit can be made, and says so. Change it
for your own before starting real work.

**What it does NOT do:** fill in `docs/architecture.md`. That file defines what
"good work" means in your project and is the reviewer's reference — writing it
is your job, and the script reminds you in its closing checklist.

After running it, `./init.ps1` should come out green (with a `[WARN]` on tests,
because there is no code yet).

---

## `reset.ps1` / `reset.sh` — reusing the template for the next project

One local copy of the harness, many projects, one after another. When the notes
app is finished and pushed to its own repository, this turns the same folder
into the ecommerce project.

```powershell
./reset.ps1 -Name "ecommerce" -Repo "https://github.com/me/ecommerce.git" -WhatIf
./reset.ps1 -Name "ecommerce" -Repo "https://github.com/me/ecommerce.git" -Description "Online store."
```

```bash
./reset.sh --name "ecommerce" --repo "https://github.com/me/ecommerce.git" --dry-run
./reset.sh --name "ecommerce" --repo "https://github.com/me/ecommerce.git"
```

**The rule, in three sentences.** Everything git tracked in the previous
project is deleted. Everything in the template's tree is written in its place.
Everything git ignored stays where it is, and is listed at the end so you can
see what came across.

| Windows | POSIX | Effect |
|---------|-------|--------|
| `-Name` | `--name` | required; the new project's name |
| `-Description` | `--description` | one line describing it |
| `-Repo` | `--repo` | URL of the new project's repository; it becomes `origin` |
| `-TemplateRepo` | `--template-repo` | URL of the harness; only if there is no `template` remote yet |
| `-From` | `--from` | a local copy of the template, to work offline |
| `-Force` | `--force` | reset even with uncommitted changes, unpushed commits or stashes |
| `-CleanIgnored` | `--clean-ignored` | also delete the files git ignores (`.venv/`, `.env`, …) |
| `-NoBundle` | `--no-bundle` | do not write the backup bundle of the previous history |
| `-WhatIf` | `--dry-run` | list everything it would delete and keep, and write nothing |

### The order of operations is the safety design

1. **Work out where the template lives**: `--from` → `--template-repo` → the
   `template` remote → today's `origin`.
2. **Preconditions.** It refuses if there are uncommitted changes, stash
   entries, commits that are not on `origin`, or no `origin` of its own.
   `--force` gets past these. It **never** gets past `--repo` being the
   template's own URL: that would push the new project into the harness's
   repository.
3. **Clone the template into a temporary folder**, outside the repository, and
   check that what arrived really is the harness (`feature_list.json` with the
   placeholder project, plus `scripts/instantiate.py`, `init.sh`, `AGENTS.md`).
   **Nothing here is deleted until that copy exists and checks out**, so a
   wrong URL or a network failure leaves the current project exactly as it was.
4. **Back up.** A `git bundle` with every ref — the stash and the uncommitted
   tree included — is written next to the folder before `.git` goes.
5. **Delete, restore, new history**, and then `scripts/instantiate.py` is
   called on the now-pristine tree: the reset does not reimplement placeholder
   substitution, it restores and delegates.
6. **Report what survived.** The previous project's `.env` sitting inside the
   new one is a real footgun, and silence about it is worse than deleting it.

A side effect worth knowing: every new project starts on the **current**
harness, not the one you cloned months ago.

`.harness-maintenance` is the one ignored file that does not survive. It
disarms the `PreToolUse` hook; carrying it over would start the next project
with the harness's own protection off and nothing in `git status` to say so.
For the same reason it does not block the reset either.

### Recovering after a reset

```bash
git clone "../workspace-pre-reset-20260910-143012.bundle" recovered
```

The bundle holds every branch, every tag, and `refs/harness/pre-reset-wip`
with whatever was uncommitted.

### Bringing harness improvements into a live project

The `template` remote is also useful without resetting anything. To pull in
fixes to the harness itself while a project is running:

```bash
git fetch template
git checkout template/main -- scripts/ docs/scripts.md init.sh init.ps1
./init.sh
```

Pick the paths deliberately: `feature_list.json`, `specs/` and `progress/`
belong to your project and must not come from the template.

---

## Permissions: `deny` beats `allow`

`.claude/settings.json` no longer pre-approves `bootstrap.ps1`: it is on
`deny`, and `reset.ps1` / `reset.sh` are there with it. Instantiating or
resetting a project is a human act — `AGENTS.md` and this very document say
so — and between them these scripts empty `features`, delete the requirements
in `specs/`, delete the whole working copy and delete `.git`. Having them on
`allow` meant an agent could run them without a single confirmation. If you
need to run one, run it yourself: in Claude Code's terminal, prefix it with
`!`.

The `allow` patterns are now **exact**, with no trailing wildcards. A pattern
like `PowerShell(./init.ps1*)` also pre-approved
`./init.ps1; Remove-Item -Recurse -Force .git`, because the wildcard covers
everything that follows. And `Bash(python scripts/*)` pre-approved running
**any file the agent had just written** into `scripts/`. The price of precision
is the odd extra confirmation; it is worth it.

---

## `scripts/validate_project_setup.py` — do not start half-configured

It blocks the session while anything essential for the harness to make sense is
missing. The reason is concrete: the reviewer approves or rejects by comparing
the code against `docs/architecture.md`, so **with that file unfilled the
reviewer has no criteria** and takes any code that passes the tests as good. A
half-configured harness is worse than no harness, because it looks like it
verifies.

```bash
python scripts/validate_project_setup.py          # the current repo
python scripts/validate_project_setup.py ../other
```

**It blocks (`[FAIL]`)** when:

- `feature_list.json` still carries the `project` placeholder.
- `docs/architecture.md` keeps `<...>` placeholders or its template note, and
  there is already a feature outside `draft`.
- `README.md` keeps `<YOUR_PROJECT>` or `<PROJECT_DESCRIPTION>`.

**It only warns (`[WARN]`)** when `description` is missing, there are no
features yet, or `src/` is empty: those are normal states at the start of a
project.

**Special case:** if *nothing* is configured, the repo is the freshly copied
template. Instead of spitting out every failure, it prints the `bootstrap.ps1`
command and stops. That is the state this template lives in on GitHub: **its
verifier comes out red on purpose**.

Exit codes: `0` configured · `1` essential configuration missing.

---

## `scripts/validate_feature_list.py` — validating the scope

It checks `feature_list.json`: required fields, types, unique ids and **names**,
valid statuses and priorities, non-empty `acceptance`, and **at most one
`in_progress` feature** (the harness's "one feature at a time" rule, made
executable). Names have to be unique because the implementer's and the
reviewer's reports are named after the feature's `name`: two identical ones
overwrite each other's report.

It also makes closing a feature executable. For a feature to sit in `done`,
both of its reports have to exist — `progress/impl_<name>.md` and
`progress/review_<name>.md` — and the reviewer's has to say `APPROVED`; and
`tests/` has to hold at least one test file (`require_tests_to_close`). Until
now the cycle said "nobody approves their own work" but **no code ever looked
at a verdict**: writing `done` in the JSON was enough. This does not make the
review unforgeable — an agent writes it — but it forces the artefact to exist
and to land in git, which is what makes it auditable afterwards.

And when everything is in order it prints **which feature comes next** by the
work order, so that order stops depending on each agent reading the rule
correctly.

**The harness rules are not read from the JSON, they are checked against it.**
`rules` describes how the harness works, and any agent can edit that file:
reading the status vocabulary or the "one feature at a time" switch from there
turned the rule into a suggestion — widening `valid_status` or setting
`one_feature_at_a_time: false` was enough for the feature to stop being
watched. If the JSON does not match the code's constants, that is a `[FAIL]`
that says so.

```bash
python scripts/validate_feature_list.py                  # feature_list.json
python scripts/validate_feature_list.py other_file.json
```

Exit codes: `0` valid · `1` invalid. It prints one `[FAIL]` line per problem.

It exists as a separate module on purpose: `init.ps1` and `init.sh` both invoke
it, so the scope rules cannot drift apart between Windows and POSIX. The full
format is described in `schema/feature_list.schema.json`.

---

## `scripts/validate_requirements.py` — do not work on what nobody approved

The harness's other gate. `validate_project_setup.py` demands that **quality
criteria** exist; this one demands that **approved scope** exists.

Why it is a script and not an instruction in a `.md`: approving a requirement
has to survive a lost context window. So it does not live in the chat, it lives
in two versioned files — `status: approved` in the spec's front matter and the
`status` of its features in `feature_list.json` — and this module checks the
two agree.

```bash
python scripts/validate_requirements.py           # the current repo
python scripts/validate_requirements.py ../other
```

**The fingerprint of what was approved.** When signing a requirement,
`/approve` stores a fingerprint of its content in `approved_hash`, and the
validator recomputes it on every run. Without that, "approved" only meant
somebody typed the word: editing its criteria afterwards left no trace at all,
and the reviewer ended up judging the code against a text the human never read.
§7 (derived features) and §8 (change log) stay out of the fingerprint, because
they change legitimately afterwards. To compute it by hand:

```bash
python scripts/validate_requirements.py --fingerprint specs/REQ-001_x.md
```

**It blocks (`[FAIL]`)** when: a feature outside `draft` hangs off an
unapproved requirement; an approved spec has no `approved_hash` or its content
changed after being approved; there is **code** in `src/` (recursively, any
language) and no approved requirement; a feature has no `spec` or points at a
file that does not exist; an approved spec keeps open questions, has no
approval date or a date that is not `YYYY-MM-DD`, or has no feature
referencing it; a feature has a higher priority than its requirement; the front
matter repeats keys; or a spec's name, `id`, `status` or `priority` is wrong.

"Outside `draft`" is evaluated **by complement**: any status that is not
`draft` counts as work started. With an allowlist of statuses, inventing a new
one was enough for the feature to escape the gate without any validator looking
at it.

**It only warns (`[WARN]`)** when: there are no requirements yet; there are
requirements in `draft` waiting for the human's OK; an approval was left
half-finished; features in `draft` still hang off a `discarded` spec; or a
feature is `in_progress` with lower priority than something queued — the
harness flags the overtake, but **it does not interrupt half-written work**:
the human decides that.

**Files starting with `_`** (`_req_template.md`, `_intake.md`) are not
requirements and are ignored. That is why the template can keep its
`<placeholders>`.

Exit codes: `0` traceability is coherent · `1` there is unapproved work or
traceability is broken.

**The harness's tests** — for this validator and its siblings — live in
`scripts/tests/`, not in `tests/`, and **the verifier does not run them**: if
they were in `tests/`, a freshly instantiated project would come out green with
tests that are not its own and the harness would stop telling "unverified"
apart from "verified". `/harness-check` runs them, or you do:
`python -m unittest discover -s scripts/tests -v`.

---

## `scripts/approve.py` — signing requirements

The mechanical half of approval. The human says **what** to approve; the script
takes care of the four things that have to be touched at once.

```bash
python scripts/approve.py 1 2             # REQ-001 and REQ-002
python scripts/approve.py REQ-003         # spell the id however you like
python scripts/approve.py all             # every requirement in draft
python scripts/approve.py 1 architecture  # and also sign docs/architecture.md
python scripts/approve.py all --dry-run
```

Per named requirement: `status: draft` → `approved`, today's date in
`approved_on` and `updated`, the content fingerprint in `approved_hash`, the
change-log row (§8), and its features from `draft` to `pending`.

**Why it is a script and not a `.md`'s prose.** These are four files that have
to be left coherent with each other, and halfway through the repository is in a
state the verifier flags red. That is exactly the kind of work where an agent
skips a step, and the easiest one to skip is precisely the one that makes the
approval verifiable: the fingerprint.

**It is all or nothing.** If something you named cannot be signed — it has
unanswered questions, it was already approved, or `docs/architecture.md` still
has holes — nothing is written. Signing half of it leaves a state nobody asked
for.

**`architecture` is named separately** on purpose: it is the criterion the
reviewer judges *all* the code against, and approving it as a side effect of a
requirement would be the oversight the harness is trying to prevent.

**It is not on the allow list, and that is deliberate.** When the agent runs
it, Claude Code shows you the exact command — `python scripts/approve.py 1 2` —
and waits for your confirmation. That prompt is the last chance to see *what*
is being signed before it is signed, and it costs nothing.

Exit codes: `0` signed (or simulated) · `1` nothing was signed, and the reason
is printed.

---

## `scripts/validate_references.py` — a map that does not lie

`CHECKPOINTS.md` C1 has always asked that every path mentioned in the
documentation really exists. Until recently that was prose. A dangling
reference is especially expensive here because the documents are the map agents
navigate by: an agent that looks for a script because `AGENTS.md`
mentions it, and does not find it, improvises.

```bash
python scripts/validate_references.py .
```

It looks at the backtick-quoted paths in the reference documents and at the
`spec` field of every feature. Only mentions **with a folder** count: a bare
name — `storage.py` in a naming-conventions table — is an example, and chasing
those filled the output with noise until nobody read it.

`/harness-check` and CI run it. **Not** the verifier: a broken reference is
documentation debt, not a reason to stop a working session.

Exit codes: `0` no dangling references · `1` at least one.

---

## Updating a project built from an older template

A project instantiated before the requirements layer comes out red as soon as
it updates the harness, and rightly so: half the contract is missing. What to
do, once:

1. In `feature_list.json`, `rules` becomes:
   ```json
   "one_feature_at_a_time": true,
   "require_tests_to_close": true,
   "work_order": "priority_then_id",
   "valid_status": ["draft", "pending", "in_progress", "done", "blocked"]
   ```
2. Every feature needs `spec` and `priority`. If the work is already done and
   there is no written requirement, write a retroactive one with
   `/requirements` covering what exists: it is more honest than inventing a
   pointer, and it documents the "why" before it is lost.
3. `done` features need their reports in `progress/`. If they predate this and
   do not exist, the least bad way out is to record exactly that in the report:
   "closed before the harness required a review".
4. `./init.ps1` or `./init.sh` walks you through what is missing, one error per
   cause.

---

## `scripts/harness_hook.py` — the hooks, and why they block

The hooks in `.claude/settings.json` live here:

```bash
python scripts/harness_hook.py stop                  # before closing the turn
python scripts/harness_hook.py post-edit             # after every Edit/Write
python scripts/harness_hook.py post-edit --tests-dir tests
python scripts/harness_hook.py pre-tool-use          # before writing
```

Exit codes: `0` all good (or there is nothing to verify yet) · **`2` blocks**.

**The 2 is this file's whole point.** A hook that exits 1 blocks nothing:
Claude Code shows the output and the session carries on. The harness hooks used
to exit 1, so for a while the repository claimed they could not be skipped
while the session closed happily with the verifier red. With exit 2 the turn
does not close, and the reason — which goes to **stderr**, not stdout — is fed
back to the model as something it has to resolve.

`stop` runs the whole verifier; `post-edit` counts the tests and, if there are
any, runs them. It counts before running because `unittest discover` over an
empty folder exits with an error ("NO TESTS RAN") and a freshly instantiated
project would see a failure on every edit.

**The loop.** Claude Code calls the `stop` hook again after the agent reacts.
If it always blocked, the session would never close: hence `stop_hook_active`,
which says we are already coming from a block. And note: `stop` **does not fire
if you interrupt with Ctrl+C**.

### `pre-tool-use` — the only one that arrives in time

`stop` and `post-edit` arrive once the write already happened. `PreToolUse`
arrives before, and that is where the harness protects **the layer that does
the verifying**: `scripts/`, `.claude/`, `schema/`, `init.*`, `bootstrap.*`,
`AGENTS.md`, `CLAUDE.md` and `CHECKPOINTS.md`.

The reason is concrete: an agent that sees red has a trivial way to turn it
green, which is editing the validator. Asking nicely in a `.md` is not enough,
because that is exactly the file it can rewrite.

It also looks at shell commands, because the `Edit|Write` matcher does not see
an `echo x > scripts/validator.py`. It is a short heuristic — it looks for write
signals (`>`, `rm`, `mv`, `sed -i`, `Remove-Item`…) over protected paths — and
deliberately stays short: chasing every way of writing from `Bash` would mean
constant false positives. It is still a net, not a cage.

**How to maintain the harness itself.** The door exists, but you have to open
it knowingly: create `.harness-maintenance` at the root (or export
`HARNESS_MAINTENANCE=1`) and delete it when you are done. The difference from
having no protection is that the file shows up in `git status`: the edit stops
being silent and becomes a visible decision.

It is Python and not PowerShell so it works the same on Windows and POSIX: the
previous version was pure PowerShell and under WSL or Linux it did not run at
all. Internally it picks `init.ps1` or `init.sh` depending on the system.

---

## `.github/workflows/harness.yml` — the harness verifying itself

Three jobs on every push and every PR:

- **POSIX**: the harness's tests, `init.sh`, the validators separately, and a
  check that the hooks **still exit with 2**. If that broke, the hooks would go
  back to being decorative and nobody would notice until a session closed with
  the verifier red.
- **Windows**: the tests and `init.ps1`, because the `.ps1` is the template's
  canonical one and until now nobody ran it except by hand.
- **Parity**: checks that `init.ps1` and `init.sh` declare exactly the same
  sections. `docs/scripts.md` says "if you change one, change the other"; this
  turns that into something checkable instead of a good intention.

The verifier **has to exit 1** in this repository: it is the uninstantiated
template and its section 3 blocks on purpose. CI checks it fails for that
reason and not another, and that the sections that do not depend on
instantiation are green.

---

## `scripts/demo_orchestration.py` — the pattern, without AI

It demonstrates the **anti-broken-telephone rule**: it analyses each module in
`src/`, writes the full report to `progress/explore_<module>.md` and returns
**only the reference** on stdout:

```
done -> progress/explore_storage.md
done -> progress/explore_cli.md
```

That is exactly what a real subagent does: the content lives on disk and a
single line travels through the communication channel. This script is the
deterministic, model-free version of the same pattern, useful to watch it work
without spending an agent session.

```bash
python scripts/demo_orchestration.py
python scripts/demo_orchestration.py --src src --out progress --dry-run
```

| Parameter | Effect |
|-----------|--------|
| `--src DIR` | folder to analyse (default `src`) |
| `--out DIR` | where to write the reports (default `progress`) |
| `--dry-run` | lists the paths without writing anything |

Exit codes: `0` finished fine (also when there were no modules: it warns and
exits 0) · `1` the `--src` folder does not exist.

It is not part of verification: neither `init.*` nor any hook calls it. With an
empty `src/` it writes nothing — which is the normal state of a freshly
instantiated template.
