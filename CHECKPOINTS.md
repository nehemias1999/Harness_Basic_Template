# CHECKPOINTS — Evaluación del estado final

> En sistemas multi-agente no se evalúa el camino, se evalúa el destino.
> Estos son los checkpoints objetivos que un juez (humano o IA) puede usar
> para decidir si el proyecto está sano.

## C1 — El arnés está completo

- [ ] Existen los 4 archivos base: `AGENTS.md`, el verificador (`init.ps1` y/o
      `init.sh`), `feature_list.json`, `progress/current.md`.
- [ ] Existen los 4 docs: `docs/architecture.md`, `docs/conventions.md`,
      `docs/verification.md`, `docs/scripts.md`.
- [ ] El verificador termina con exit code 0.
- [ ] Toda ruta mencionada en `CLAUDE.md`, `AGENTS.md` y `README.md` existe
      (sin referencias colgantes).

## C2 — El estado es coherente

- [ ] Como mucho una feature en `in_progress` en `feature_list.json`.
- [ ] Toda feature `done` tiene tests asociados que pasan.
- [ ] `progress/current.md` está vacío o describe la sesión activa
      (no contiene basura de sesiones anteriores).
- [ ] `feature_list.json` ya no tiene el placeholder `<TU_PROYECTO>`.

## C3 — El código respeta la arquitectura

- [ ] `src/` solo contiene los módulos previstos en `docs/architecture.md`, y
      `docs/architecture.md` está rellenado (sin placeholders `<...>`).
- [ ] No hay dependencias externas: no existe `requirements.txt` con contenido,
      ni imports fuera de la stdlib (salvo excepción documentada en una feature).
- [ ] No hay `print()` sueltos para debug, ni TODOs sin contexto.
- [ ] Los errores salen por `stderr` con exit code != 0, no por `print()`.

## C4 — La verificación es real

- [ ] Si `src/` tiene módulos, `tests/` tiene al menos un test por módulo.
      (En un proyecto recién instanciado este checkbox no aplica todavía.)
- [ ] La sección 4 del verificador muestra `[OK]`, no `[WARN]`: 0 tests
      significa "sin verificar", no "verde".
- [ ] Los tests que tocan disco usan `tempfile.TemporaryDirectory()`, no mocks
      del filesystem ni rutas del usuario.
- [ ] `python -m unittest discover -s tests -v` muestra > 0 tests y todos verdes.

## C5 — La sesión se cerró bien

- [ ] No hay archivos sin trackear sospechosos (`*.tmp`, `__pycache__`
      fuera del `.gitignore`).
- [ ] `progress/history.md` tiene una entrada por la última sesión.
- [ ] La última feature trabajada está reflejada en su estado correcto.
- [ ] Existe el informe del implementer (`progress/impl_<feature>.md`) y el del
      reviewer (`progress/review_<feature>.md`) de la feature cerrada.

---

**Cómo usar este archivo:** un agente revisor (`.claude/agents/reviewer.md`)
recorre cada checkbox, marca `[x]` o `[ ]`, y rechaza el cierre de sesión
si quedan boxes vacíos en C1-C5. Un checkbox que no aplica se marca `[-]` con
la razón al lado.
