# Current session

> This file is emptied when each session closes and moved into `history.md`.
> While you work, **keep it up to date in real time**, not at the end.

- **Feature in progress:** CP3 + CP4 — narrativa del vault (cerradas y mergeadas)
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
- **CP2 merged:** PR #23 (squash, sha `4cce237`, "feat(obsidian): feature notes
  as the vault memory"); `main` local sincronizado; rama borrada; apunte de
  memoria pusheado (`ef846d9`). Queda CP3 (narrativa agents/commands/CLAUDE.md)
  y CP4 (narrativa en `docs/`, incl. `docs/obsidian.md` y `docs/feature-notes.md`).
- **Vault Obsidian creado:** symlink imposible en el mount `fuse.rclone`
  (EIO: solo con `--vfs-links`). Decisión: vault **espejo** real creado en
  `/home/nsalazar/Documents/GoogleDrive/Profesional/Obsidian/Harness_Basic_Template`
  con `.obsidian/`, `_Dashboard.md`, `features/`, `specs/`, `docs/`, `progress/`
  (copiados del repo). Registrado en `~/.config/obsidian/obsidian.json` como
  vault propio (id `86ece00003b579bb`); el vault principal (Drive) también lo
  ve como subcarpeta. **El repo sigue siendo la fuente de verdad**; el espejo
  puede quedar desactualizado — refrescar copiando los directorios.
- **CP4 done:** `docs/obsidian.md` (el repo ES el vault: abrirlo, front matter
  como API, autoridad del verifier, espejo de Drive) y `docs/feature-notes.md`
  (anatomía campo a campo de la nota de feature + máquina de estados),
  registradas en `DOCUMENTS` de `validate_references.py` (20 docs) y en el
  mapa de AGENTS.md. PR #24 (squash, sha `ded90a9`), `main` sincronizado.
- **CP3 done:** narrativa del vault en CLAUDE.md (protocolo de arranque: el
  repo es un vault de Obsidian; refs a `docs/obsidian.md` y
  `docs/feature-notes.md`), `leader.md` (misma referencia en su arranque) y
  `analyst.md` (apunta a `docs/feature-notes.md` al derivar features).
  PR #25 (squash, sha `64ece66`), `main` sincronizado; ramas borradas.
- **E2E final (verde):** clon del repo en `/tmp/opencode/e2e_check`,
  `bootstrap.sh --name e2e_check` → spec REQ-001 (draft) → `approve.py 1`
  (firma + fingerprint `12712eb8db97abc5`, feature 1 → pending) →
  `approve.py architecture` (placeholder llenado) → verifier "Environment
  ready" → `hello.py` + `tests/test_greeting.py` (1 test OK) → feature 1
  `status: done` + `progress/impl_greeting.md` + `progress/review_greeting.md`
  (`**Verdict:** APPROVED`) → verifier final todo `[OK]`. Temp borrado.
- **Espejo del vault refrescado** con los docs, CLAUDE.md, agentes y
  `progress/current.md`.

## Next step

- Commit de memoria con este estado y push a `main`; refrescar el espejo del
  vault. El proyecto queda con el ciclo completo terminado: todos los
  checkpoints CP1→CP4 mergeados (#22, #23, #24, #25).