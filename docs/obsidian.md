# Obsidian — this repository is the vault

> Where the memory of the project lives, how to open it, and what the harness
> still has to do with it even though you are in an editor.

## The one sentence

**The repository itself is the Obsidian vault.** The notes under `features/`
are the task list, the notes under `specs/` are requirements, `progress/`
holds the session log, and every note is a plain Markdown file with YAML
front matter that the harness reads and validates.

There is no second database, no export step, no sync daemon to keep a
`feature_list.json` in agreement with the notes. The file on disk **is** the
state — that is the whole point. `scripts/features_io.py` parses those notes
directly, and `scripts/validate_features.py` refuses a note that does not
match the shape documented in `features/_template.md`.

## Opening the vault

Do **not** use Obsidian's "Create new vault". Use **Open folder as vault**
and point it at the repository root:

1. Obsidian → **Open another vault** → **Open folder as vault**.
2. Select this repository's folder.
3. Done. A fresh clone has a `.obsidian/` already, so the recommended
   configuration (Dataview for the dashboard) comes with the vault.

The vault's front door is [`_Dashboard.md`](../../_Dashboard.md): it uses
Dataview queries to render features and requirements by status. It is a
**view**, not the truth — the truth is the front matter of each note, and the
verifier (`./init.sh` / `./init.ps1`) is the court of last resort.

## Sections of the vault

| Folder | Kind of note | Editable by the agent that |
|--------|--------------|---------------------------|
| `features/`         | One note per feature (`F-<id>_<name>.md`) | the `implementer` (its status), the `leader` (to close) |
| `features/_project.md` | The project's name and description  | only at instantiation |
| `features/_template.md` | The exact shape of a feature note  | the `analyst`, to copy |
| `specs/`            | One note per requirement (`REQ-00N_<name>.md`) | the `analyst`, until approved |
| `docs/`             | The contracts (architecture, scripts, ...) | the `analyst` (draft arch), nobody to close |
| `progress/`         | Session state and reports               | the `leader`, `implementer`, `reviewer` |
| `_Dashboard.md`     | Obsidian views over the state           | nobody |

## Front matter is the API

The harness only reads these keys from a note's front matter. Keep them flat
`key: value` except `acceptance` and `tags`, which are lists of `- "item"`
lines. The feature note shape is documented in detail in
`docs/feature-notes.md`; the spec shape in `specs/_req_template.md`.

Two of the values are **wikilinks**:

- the feature's `spec: "[[REQ-00N_name]]"` → the requirement it was derived
  from. With the graph view open, the edge appears between the two notes;
- in `features/_template.md` and in reports, [[REQ-00N_name]] appears in
  line, and Obsidian resolves it to the spec.

The `status` key is the harness's state machine: `draft` → `pending` →
`in_progress` → `done` (+ `blocked`). See `docs/feature-notes.md` for who is
allowed to move it at each step.

## The verifier is still the boss

Obsidian is a comfortable place to *read* and *edit* notes, but the validity
of a note is checked **by the harness, not by the editor**: a note you
hand-edit has no effect until the verifier accepts it. In particular:

- **Never promote a feature to `pending` or `done` by hand.** The move to
  `done` only counts with an `APPROVED` review in `progress/`; the move to
  `pending` only with `/approve`, which signs the requirement first.
- **Never touch a feature that is not in `draft`** if you are an `analyst`.
- If you edited a note and `./init.sh` goes red, the note did not match the
  contract. The `[FAIL]` line names the note and the field.

Editing statuses by hand is not "cheating": the harness is a gate, not a
threat model. It exists so that a lost context window cannot silently rewrite
the truth. As long as the verifier is green, the vault and the harness agree.

## If you have the vault on Google Drive too

This repository keeps a **mirror copy** under
`GoogleDrive/Profesional/Obsidian/Harness_Basic_Template/` so the project
appears inside your main Obsidian vault (rclone mount does not support
symlinks, so a mirror folder was chosen instead). That mirror is a **copy**:
the repository remains the source of truth. If you see it stale, refresh it
by copying the directories again from the repo root:

```bash
VAULT=/path/to/GoogleDrive/Profesional/Obsidian/Harness_Basic_Template
cp -r .obsidian features specs docs progress _Dashboard.md "$VAULT/"
```

The mirror is a convenience for browsing, not something the harness reads.

## See also

- `docs/feature-notes.md` — the anatomy of a feature note, field by field.
- `docs/scripts.md` — what each harness script does and when it fails.