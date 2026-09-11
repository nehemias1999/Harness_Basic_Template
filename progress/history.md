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
