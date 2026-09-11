# <YOUR_PROJECT>

> <PROJECT_DESCRIPTION>

This repository works with a **harness**: a set of files, scripts and roles
that let an AI agent work autonomously and **verifiably**. What matters is not
what the app does, but how the repo is structured so an agent can make progress
without constant supervision and without making up that something works.

If you have just copied this template, go to [Quick start](#quick-start).

## The three pillars

| Pillar | How it shows up in this repo |
|--------|------------------------------|
| **1. The repository IS the system** | `AGENTS.md`, `init.ps1` / `init.sh`, `specs/`, `feature_list.json`, `progress/`, `docs/` |
| **2. Multi-agent orchestration** | `.claude/agents/analyst.md`, `leader.md`, `implementer.md`, `reviewer.md`, `.claude/commands/` |
| **3. Supervision and improvement** | `CHECKPOINTS.md`, hooks in `.claude/settings.json`, `tests/` |

## Quick start

```powershell
./bootstrap.ps1 -Name "my-project" -Description "What it does." -Repo "https://github.com/me/my-project.git" -WhatIf   # dry run
./bootstrap.ps1 -Name "my-project" -Description "What it does." -Repo "https://github.com/me/my-project.git"           # for real
```

```bash
./bootstrap.sh --name "my-project" --description "What it does." --repo "https://github.com/me/my-project.git" --dry-run  # dry run
./bootstrap.sh --name "my-project" --description "What it does." --repo "https://github.com/me/my-project.git"            # for real
```

Both do exactly the same thing: they are wrappers around
`scripts/instantiate.py`, which is where the logic lives.

**The project's repository and the template's are always two different
repositories**, and `--repo` is where you say so. The workspace ends up with
two remotes: `origin` is yours, `template` is the harness. Without `--repo`
the script disconnects the inherited `origin` instead and reminds you to add
your own — because otherwise your first `git push` would go to the template's
repo. If you **cloned** this template instead of copying it, add `-ResetGit`
so you do not drag its history along.

Then, in this order:

1. **Open Claude Code at the root and hand it your requirements in plain
   language** (or use `/requirements`). They do not need to be tidy or
   complete: that is what the cycle is for. The `analyst` agent turns them into
   specs under `specs/`, one per requirement, with verifiable acceptance
   criteria and a priority — and it **asks** about what it does not know
   instead of assuming. On the first round it also drafts
   `docs/architecture.md`.
2. **Read them and iterate.** Add, change or drop whatever you want: each pass
   is a round and is recorded in every spec's change log. Nothing gets
   implemented in the meantime.
3. **When you are happy, you approve them by id**: `/approve 1 2`, or
   `/approve-all` to sign everything still in draft. The specs get signed and
   their features move to `pending`. The architecture is named separately:
   `/approve 1 architecture`.

   That is the only moment the harness considers there is work to do: a "sure,
   go ahead" in the chat approves nothing. The approval is the command with the
   ids written out, and it lands in git.
4. **Review `docs/conventions.md` and `docs/verification.md`.** They ship with
   the template's Python conventions; adjust them to taste.
5. **Run the verifier** — it should come out green.
   ```powershell
   ./init.ps1        # Windows
   ```
   ```bash
   ./init.sh         # WSL / macOS / Linux / CI
   ```
6. **`/next-feature`** to start development. It starts with the
   highest-priority feature, not the lowest `id`.

Until step 3 the verifier comes out **red on purpose**: the harness will not
let you program on a project with no approved requirements, because then the
reviewer would have nothing to judge the code against.

If you prefer to write the requirements by hand, you can: copy
`specs/_req_template.md`, fill in `docs/architecture.md` and add the features
to `feature_list.json` yourself. The harness validates the same either way.

## Reusing the template for the next project

One local copy, many projects, one after another. When a project is finished
and pushed to **its own** repository, this folder becomes the next one:

```powershell
./reset.ps1 -Name "ecommerce" -Repo "https://github.com/me/ecommerce.git" -WhatIf
./reset.ps1 -Name "ecommerce" -Repo "https://github.com/me/ecommerce.git"
```

```bash
./reset.sh --name "ecommerce" --repo "https://github.com/me/ecommerce.git" --dry-run
./reset.sh --name "ecommerce" --repo "https://github.com/me/ecommerce.git"
```

Everything git tracked in the previous project is deleted, the template's tree
is written in its place, and everything git ignored stays where it is and is
listed at the end. Then the new project is instantiated on top, with a fresh
history and `origin` pointing at its own repository. The previous project's
repository is not touched — its history lives there, and a backup bundle of
it is written next to this folder anyway.

It reads the pristine template from the `template` remote, and refuses before
deleting anything if there are uncommitted changes, stashes or commits that
are not pushed. Whatever state the project is in, `--force` gets past that —
and `--dry-run` shows you the whole list first.

Both scripts are on the agent's `deny` list: resetting deletes a project's
working copy, and that decision is yours. Details in **`docs/scripts.md`**.

## Scripts

| Script | Who runs it | When |
|--------|-------------|------|
| `init.ps1` / `init.sh` | agent, `Stop` hook, reviewer | when starting the session and before any `done` |
| `bootstrap.ps1` / `bootstrap.sh` | human | once, when instantiating the project |
| `reset.ps1` / `reset.sh` | human | when this folder is to host the next project |
| `scripts/validate_project_setup.py` | `init.*` (and by hand) | blocks start-up if the project is not configured |
| `scripts/validate_requirements.py` | `init.*` (and by hand) | blocks work on an unapproved requirement |
| `scripts/approve.py` | `/approve`, `/approve-all` | when you sign requirements |
| `scripts/validate_feature_list.py` | `init.*` (and by hand) | to check the scope |
| `scripts/harness_hook.py` | `PostToolUse` and `Stop` hooks | automatic; they block with exit 2 |
| `scripts/demo_orchestration.py` | human or agent | to see the anti-broken-telephone pattern in action |

Parameters, exit codes and what to do when each one fails: **`docs/scripts.md`**.

## Windows and POSIX

`init.ps1` and `init.sh` are **the same verifier**: same seven-section
structure, same `[OK]/[WARN]/[FAIL]` output, same exit code. Use the `.ps1` on
Windows and the `.sh` on WSL, macOS, Linux or CI. If you touch one, touch the
other — and CI checks they declare the same sections, so "if you touch one"
does not depend on anyone remembering.

Same for `bootstrap.ps1` / `bootstrap.sh` and for `reset.ps1` / `reset.sh`,
except there are no two implementations there: they call
`scripts/instantiate.py` and `scripts/reset_workspace.py`.

The hooks in `.claude/settings.json` no longer depend on the platform: they are
`python scripts/harness_hook.py`, and the script picks `init.ps1` or `init.sh`
depending on the system. The only thing you may need to change on Linux is the
interpreter name (`python` → `python3`) if your distribution does not expose
`python`.

Those hooks **block**: they exit with 2, so the turn does not close with a red
verifier or with broken tests. And a third one, `PreToolUse`, arrives before
the write and protects the layer that verifies the work (`scripts/`,
`.claude/`, `init.*`, `AGENTS.md`, `CLAUDE.md`, `CHECKPOINTS.md`): an agent
that sees red does not fix the red by editing the validator.

To maintain the harness itself you have to declare it: create
`.harness-maintenance` at the root and delete it when you are done. The file
shows up in `git status`, so the edit stops being silent and becomes a visible
decision.

## The work cycle

`CLAUDE.md` forces Claude to act as the **leader**: it orchestrates, it does
not write code.

There are two chained cycles. The first defines **what** has to be built and
you close it; the second builds it.

```
   your requirements ──>  analyst  ──>  specs/REQ-00N.md  ──>  you read them
   (plain language)                     (draft, with priority)      │
          ↑                                                         │
          └──────── you add / change / drop ──────────────────────-─┤
                                                                    │ your OK
                                       /approve 1 2 ────────────────┘
                                                    │
                                        (draft features -> pending)
                                                    ▼
leader  ──launches──>  implementer  ──report──>  leader  ──launches──>  reviewer
                       (writes code                                    (approves or
                        and tests)                                      rejects)
                                                                            │
                                        leader closes the feature  <────────┘
                                        (only if APPROVED)
```

Nobody approves their own work, in either cycle: the analyst proposes
requirements but does not approve them; the implementer leaves the feature
`in_progress` and stops; the reviewer does not edit code; the leader does not
implement. You sign the scope (`/approve 1 2`), and the close
(`status: "done"`) only comes after an `APPROVED`.

The first cycle is not only for the start: if a new requirement shows up
mid-development, it repeats the same way. The features the analyst creates are
born in `draft` and are inert, so analysing never interrupts what is being
built.

Shortcuts: `/requirements`, `/approve 1 2`, `/approve-all`, `/next-feature`,
`/close-session`, `/harness-check`.

## Where the trail lives

**No code goes through the chat** — only references like
`done -> progress/impl_<feature>.md`. That is the anti-broken-telephone rule.
The content lives on disk and stays versioned:

| File | Who writes it | What it holds |
|------|---------------|---------------|
| `specs/_intake.md` | analyst | Your requests, verbatim and dated |
| `specs/REQ-*.md` | analyst | The requirement in SDD; its `status` is the approval |
| `progress/intake_r<N>.md` | analyst | What changed in the round and which questions are open |
| `progress/current.md` | leader | The session's live plan |
| `progress/impl_<feature>.md` | implementer | Files touched + test output |
| `progress/review_<feature>.md` | reviewer | Checklist against `docs/` and `CHECKPOINTS.md` |
| `feature_list.json` | analyst → leader → implementer | `draft` → `pending` → `in_progress` → `done` |
| `progress/history.md` | leader | Append-only summary when the session closes |

Open `progress/` in your editor while Claude works: each report appears as soon
as the subagent finishes. That is how you audit, step by step, who decided what.

## Structure

```
.
├── .github/workflows/harness.yml    # CI: the harness verifies itself
├── AGENTS.md                        # Map for agents (progressive disclosure)
├── CLAUDE.md                        # Forces the `leader` role in every session
├── CHECKPOINTS.md                   # Criteria for a "correct final state"
├── README.md                        # This file
├── feature_list.json                # Executable backlog, derived from specs/
├── init.ps1                         # Verifier (Windows)
├── init.sh                          # Verifier (POSIX)
├── bootstrap.ps1                    # Instantiates a new project (Windows)
├── bootstrap.sh                     # Instantiates a new project (POSIX)
├── reset.ps1                        # Returns the folder to the template (Windows)
├── reset.sh                         # Returns the folder to the template (POSIX)
├── docs/
│   ├── architecture.md              # What "good work" means (the analyst drafts it, you approve it)
│   ├── conventions.md               # Style, names, errors
│   ├── verification.md              # How to prove it works
│   └── scripts.md                   # Script reference
├── specs/
│   ├── _req_template.md             # Skeleton of an SDD requirement
│   ├── _intake.md                   # Your raw requests, append-only
│   └── REQ-00N_<name>.md            # One requirement (status: draft | approved)
├── progress/
│   ├── current.md                   # Active session (live state)
│   ├── intake_r<N>.md               # Report of each analysis round
│   └── history.md                   # Append-only log
├── schema/
│   └── feature_list.schema.json     # Shape of a feature
├── scripts/
│   ├── validate_feature_list.py     # Validates the scope (init.ps1 and init.sh use it)
│   ├── validate_requirements.py     # Validates requirement -> feature (idem)
│   ├── approve.py                   # Signs the requirements you name
│   ├── validate_references.py       # Keeps the docs from pointing at missing files
│   ├── instantiate.py               # The bootstrap logic, shared by both platforms
│   ├── reset_workspace.py           # The reset logic, shared by both platforms
│   ├── tests/                       # The harness's own tests (init.* does not run them)
│   ├── harness_hook.py              # The hooks: tests after each edit, verifier on close
│   └── demo_orchestration.py        # Demo of the Leader-Worker pattern
├── .claude/
│   ├── agents/                      # analyst, leader, implementer, reviewer
│   ├── commands/                    # /requirements, /approve, /approve-all, /next-feature,
│   │                                #   /close-session, /harness-check
│   └── settings.json                # Hooks that automate verification
├── src/                             # Application code (empty at the start)
└── tests/                           # Automated tests (empty at the start)
```

## What this project illustrates

- **Progressive disclosure** in `AGENTS.md`: the agent does not get every rule
  at once, it gets a map to look them up on demand.
- **Nobody works on what nobody approved**: approving a requirement is a state
  in git (`status: approved` + the feature in `pending`), not a message in the
  chat. It survives a lost context window; a "sure" does not.
- **The agent asks instead of assuming**, and that is executable too: a
  requirement with unanswered open questions cannot be approved.
- **One feature at a time**, enforced by the verifier (it rejects more than one
  `in_progress` in `feature_list.json`), and by priority: critical first.
- **State on disk**, not in the chat: `progress/current.md` and `history.md`
  survive restarts and blown context windows.
- **A control nobody runs is not a control**: that is why the harness's own
  tests and the parity between `init.ps1` and `init.sh` run in CI, not when
  somebody remembers.
- **Executable verification**: the verifier runs the real tests, it does not
  take the agent's word for it. And it tells "0 tests" apart from "all green" —
  a repo with no tests is not verified, even if `unittest` exits successfully.
- **Leader-Worker-Reviewer pattern**: the leader does not implement, the
  implementer does not approve itself, the reviewer does not edit code.
- **Anti broken telephone**: subagents write their results to files and only
  return a lightweight reference.
- **Permissions are part of the design**: if a subagent needs to write its
  report, its front matter has to include `Write`. A role without the tools to
  fulfil its protocol is a broken role.
- **But `tools:` restricts by tool, not by path**, and every role needs `Bash`,
  which is a universal write primitive. "The reviewer does not edit code" has
  only been a real rule since a hook enforces it; before that it was a promise.
  When a rule matters, the question is what compels it, not where it is
  written.
