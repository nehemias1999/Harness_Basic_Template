# AGENTS.md — Navigation map for AI agents

> This file is the **entry point** for any agent working in this repository.
> It is NOT a bible of rules: it is a **map**. Read only what you need, when you
> need it (progressive disclosure).

---

## 1. Before you start (mandatory)

1. Run the verifier and check it finishes without errors: `./init.ps1` on
   Windows, `./init.sh` on WSL/macOS/Linux. If it fails, **stop** and sort the
   environment out before touching any code. If its section 3 says the project
   is not configured, there is nothing to implement yet: report what is missing
   and stop.
2. Read `progress/current.md` to understand what state the last session left.
3. Read `feature_list.json` and pick **one** task with status `pending`. Do not
   work on more than one at a time. `draft` ones are **not worked on**: they are
   requirements the human has not approved yet. If there are only `draft` ones,
   there is nothing to implement — say so and stop.

## 2. Map of the repository

| File / folder                      | What it holds                                             | When to read it |
|------------------------------------|-----------------------------------------------------------|-----------------|
| `feature_list.json`                | The task list with status (draft / pending / in_progress / done / blocked) and priority | Always, at the start |
| `specs/`                           | The requirements in SDD format, one per file. The source the features come from | Before implementing, and whenever the scope is unclear |
| `progress/current.md`              | State of the current session                              | Always, at the start |
| `progress/history.md`              | Append-only log of previous sessions                      | If you need historical context |
| `docs/architecture.md`             | What "good work" means in this project                    | Before implementing |
| `docs/conventions.md`              | Style, naming and structure rules                         | Before writing code |
| `docs/verification.md`             | How to verify your work actually works                    | Before declaring a task `done` |
| `docs/scripts.md`                  | What each script does, its parameters and what to do when it fails | If a script fails or you do not know which one to use |
| `CHECKPOINTS.md`                   | Objective criteria for "correct final state"              | To assess yourself |
| `init.ps1` / `init.sh`             | The verifier (same behaviour on both platforms)           | On start-up and before closing |
| `bootstrap.ps1` / `bootstrap.sh`   | Instantiates a new project from the template              | Only the first time, and **a human runs it**: it is on the `deny` list |
| `reset.ps1` / `reset.sh`           | Returns the folder to the template to start another project | When one project ends and the next begins, and **a human runs it**: it is on the `deny` list |
| `scripts/validate_project_setup.py` | Checks the project is configured (blocking)              | The verifier calls it; by hand if you are unsure what is missing |
| `scripts/validate_requirements.py` | Checks nobody is working on an unapproved requirement (blocking) | The verifier calls it; by hand if traceability is unclear |
| `schema/feature_list.schema.json`  | The exact shape of a feature                              | If you are unsure about the scope's structure |
| `.claude/agents/`                  | Subagent definitions (analyst, leader, implementer, reviewer) | If you are orchestrating work |
| `.claude/commands/`                | The cycle's slash commands (`/requirements`, `/approve`, `/approve-all`, `/next-feature`, `/close-session`, `/harness-check`) | To trigger the cycle without writing the prompt |
| `scripts/demo_orchestration.py`    | Demo of the Leader-Worker pattern with results on disk    | To understand the anti-broken-telephone rule |
| `src/`                             | Application code                                          | To implement |
| `tests/`                           | Automated tests                                           | To verify |

## 3. Hard rules (non-negotiable)

- **Nobody works on what nobody approved.** Every feature comes from a
  requirement in `specs/` and is not touched until that requirement is
  `approved`. A "sure, go ahead" in the chat is not an approval; `/approve` is,
  and it lands in git.
- **One feature at a time.** Do not mix changes from several tasks in the same
  session.
- **Do not declare a task `done` without green tests.** Run the verifier and
  make sure the test block passes 100%. Careful: `[WARN] 0 tests` means
  "unverified", not "green".
- **You do not approve your own work.** The implementer does not close its own
  feature: the leader does, after the reviewer's `APPROVED`.
- **Document what you do** in `progress/current.md` while you work, not at the
  end.
- **Leave the repository clean** before closing the session (see §5).
- **If you do not know something, look it up in `docs/`** before inventing it.

## 4. How to pick a task

```
1. Open feature_list.json
2. Filter by status == "pending"     (draft = unapproved requirement: ignored)
3. If none is left, stop: there is no approved work
4. Sort by priority: critical > high > medium > low
5. At equal priority, take the lowest "id"
```

**The status change is made by whoever works, not by whoever coordinates.** The
`implementer` moves the feature to `in_progress` when it takes it and writes the
plan in `progress/current.md`; the `leader` only moves it to `done`, and only
after an `APPROVED`. If you are unsure which one is next, do not work it out by
eye: the verifier prints it in section 4.

The order is set by `rules.work_order` in `feature_list.json`. Each feature
inherits its priority from its requirement, so if the ordering looks wrong, the
thing to discuss is the requirement — not the feature.

## 5. Closing the session (lifecycle)

Before finishing:

1. Run the verifier — everything green.
2. If the task is finished and approved: set `status: "done"` in
   `feature_list.json`.
3. Move the summary from `progress/current.md` to the end of
   `progress/history.md`.
4. Empty `progress/current.md`, leaving only the template.
5. Leave no temporary files, no debug `print()` calls and no context-free TODOs.

Shortcut: `/close-session` walks this path step by step.

## 6. If you get stuck

- Re-read the relevant section of `docs/`.
- If what fails is a harness script, look at the "when it fails" table in
  `docs/scripts.md` before improvising.
- If a tool does not do what you expect, **do not invent a workaround**:
  document the blocker in `progress/current.md`, leave the feature `blocked`
  and end the session.
