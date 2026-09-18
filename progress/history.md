# Session history

> **Append-only** log. When each session closes, the summary that lived in
> `progress/current.md` is added at the end. A previous entry is never edited
> or deleted: this file is the project's memory between context windows.

Format of each entry:

```markdown
## <YYYY-MM-DD> — feature <id> <name>

- **Agent:** <who worked on it>
- **Result:** done | blocked
- **Files touched:** <list>
- **Verification:** <summarised init output>
- **Notes:** <decisions or blockers relevant to the next session>
```

---

_No sessions recorded yet._

## 2026-09-18 — Obsidian vault migration (CP1-CP4)

- **Agent:** implementer (opencode)
- **Result:** done
- **Files touched:** `.obsidian/`, `_Dashboard.md`, `features/`, `specs/`,
  `docs/` (`obsidian.md`, `feature-notes.md`, ...), `scripts/` (all moved to
  feature-note storage; `features_io.py` added, `validate_feature_list.py` →
  `validate_features.py`), `scripts/tests/` (8 files, 215 tests),
  `progress/`, `AGENTS.md`, `CLAUDE.md`, `.claude/agents/` (leader, analyst, ...),
  `.claude/commands/`, `init.sh`, `init.ps1`, `bootstrap.ps1`,
  `.github/workflows/harness.yml`, deleted `feature_list.json` and `schema/`.
- **Verification:** 215 tests OK; `./init.sh` red only for the expected
  "NOT INSTANTIATED" (template, section 3); `validate_references.py`: 20
  documents, no dangling references; parametrized validators + `approve.py`
  green; full e2e (bootstrap → approve → architecture approve → feature
  done) green in a temp clone.
- **Notes:**
  - The repository IS the Obsidian vault; state lives in feature-note front
    matter, not in any JSON. `_Dashboard.md` is a view, not the truth.
  - No official Obsidian integration point of the template: the vault is a
    folder with `.obsidian/`. Opening the folder as a vault is a user action.
  - Google Drive mirror vault created (rclone mount cannot symlink): refresh
    by re-copying directories. The repo remains the source of truth.
  - GitHub work per checkpoint done via PR + squash merge through the MCP
    server, because `gh` is not installed; push requires
    `GITHUB_PERSONAL_ACCESS_TOKEN` and a one-off credential helper.
  - Next-session reminder: `validate_features._validate_note` has two dead
    checks (front-matter id/name vs file name); `load_features` overwrites
    them. Known, documented, left as dead code.
