# Current session

> This file is emptied when each session closes and moved into `history.md`.
> While you work, **keep it up to date in real time**, not at the end.

- **Feature in progress:** CP2 — la memoria de features vive en el vault (notas `features/F-*`)
- **Started:** 2026-09-18
- **Agent:** implementer (opencode)

## Plan

- Migrar la memoria del harness a un vault de Obsidian: una nota por feature en
  `features/`, con front matter y wikilinks a los requisitos de `specs/`.
- CP1 (esqueleto del vault) ya implementado y mergeado (PR #22).
- CP2: `scripts/features_io.py` + `scripts/validate_features.py`, migración de
  scripts, hooks, `init.*`, CI y `.claude/settings.json`; borrado de
  `feature_list.json` y `schema/`; reescritura de `scripts/tests/`; docs y
  agentes con las rutas nuevas.
- Un PR + merge por checkpoint; PR + merge con GitHub MCP (`gh` no está instalado).
- CP3: `.claude/agents/`, `.claude/commands/`, CLAUDE.md. CP4: narrativa en `docs/`.

## Log

- **CP1 done:** esqueleto del vault (`.obsidian/`, `_Dashboard.md`,
  `features/_project.md`, `features/_template.md`) mergeado vía PR #22
  (squash, sha `c944b4e`); `main` local sincronizado.
- **CP2 code done:** `scripts/features_io.py` (front matter plano, listas sin
  PyYAML; `parse_frontmatter`, `serialize_frontmatter`, `write_note`,
  `spec_basename`, `load_features`); `validate_feature_list.py` →
  `validate_features.py`; migrados `validate_requirements.py`, `approve.py`,
  `validate_project_setup.py`, `validate_references.py`, `harness_hook.py`,
  `instantiate.py`, `reset_workspace.py`; `init.sh`/`init.ps1` (sección 4
  "Validating features", base files con `features/_project.md` +
  `features/_template.md`); `harness.yml` (grep "features valid", probe del
  stop-hook sobre `_project.md`); `.claude/settings.json`; `bootstrap.ps1`;
  docs y agentes/commands con rutas nuevas.
- **CP2 deleted:** `feature_list.json`, `schema/feature_list.schema.json`.
- **CP2 tests:** `scripts/tests/` reescritos a notas (los 8 archivos;
  `test_validate_feature_list.py` → `test_validate_features.py`). Suite:
  **Ran 215 tests — OK**. `./init.sh` da exit 1 solo por "NOT INSTANTIATED"
  (lo esperado en el template); sección 4 `[OK] features valid (0 features)`;
  paridad de secciones init.ps1/init.sh verificada.
- Nota: `_validate_note` de `validate_features.py` tiene dos comprobaciones
  muertas (id/name del front matter contra el nombre del archivo): `load_features`
  sobreescribe ambos desde el nombre de archivo. Quedan como dead code; el
  nombre de archivo es la autoridad. Se documentó en los tests.
- **CP2 pendiente:** commit → push → PR → merge; luego CP3 y CP4.

## Next step

- Commit de CP2: `git add` de los cambios, mensaje "feat(obsidian): project
  scope as feature notes (migrate feature_list.json to features/)"; push con
  credential helper one-off:
  `git -c credential.helper='!f() { echo "username=nehemias1999"; echo "password=$GITHUB_PERSONAL_ACCESS_TOKEN"; }; f' push -u origin <branch>`.
- PR vía GitHub MCP (branch `feat/obsidian-memory-cp2-...`), merge squash,
  sync `main`. Luego CP3 y CP4, cada uno con PR + merge.