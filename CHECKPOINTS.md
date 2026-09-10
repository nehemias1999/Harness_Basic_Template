# CHECKPOINTS — Evaluación del estado final

> En sistemas multi-agente no se evalúa el camino, se evalúa el destino.
> Estos son los checkpoints objetivos que un juez (humano o IA) puede usar
> para decidir si el proyecto está sano.

## C1 — El arnés está completo

- [ ] Existen los archivos base del arnés. Los comprueba la sección 2 del
      verificador: `AGENTS.md`, `CLAUDE.md`, `CHECKPOINTS.md`, `README.md`,
      `feature_list.json`, `progress/current.md`, `progress/history.md`,
      `specs/_plantilla_req.md` y los cuatro `docs/`.
- [ ] Existen los 4 docs: `docs/architecture.md`, `docs/conventions.md`,
      `docs/verification.md`, `docs/scripts.md`.
- [ ] El verificador termina con exit code 0. (En la plantilla sin instanciar
      sale 1 a propósito: la sección 3 exige configurar el proyecto primero.)
- [ ] Toda ruta mencionada en `CLAUDE.md`, `AGENTS.md` y `README.md` existe
      (sin referencias colgantes).
- [ ] Existe `specs/` con al menos un requisito, o el proyecto todavía no
      arrancó el análisis (entonces tampoco hay código).

## C2 — El estado es coherente

- [ ] Como mucho una feature en `in_progress` en `feature_list.json`.
- [ ] Toda feature `done` tiene tests asociados que pasan, y sus dos informes
      (`impl_` y `review_`) con veredicto `APPROVED`. Lo comprueba la sección 4
      del verificador.
- [ ] `progress/current.md` está vacío o describe la sesión activa
      (no contiene basura de sesiones anteriores).
- [ ] `feature_list.json` ya no tiene el placeholder `<TU_PROYECTO>`.
- [ ] Ninguna feature fuera de `draft` cuelga de un requisito sin aprobar.
- [ ] Todo requisito `aprobado` tiene al menos una feature que lo referencia,
      y toda feature apunta a un `spec` que existe.
- [ ] Ningún requisito aprobado cambió después de aprobarse (`aprobado_hash`).

## C3 — El código respeta la arquitectura

- [ ] `src/` solo contiene los módulos previstos en `docs/architecture.md`.
      (Que `architecture.md` esté escrito **y aprobado** lo comprueba el
      verificador en su sección 3 en cuanto hay una feature fuera de `draft`;
      si estás leyendo esto con el verificador verde y código en `src/`, está
      hecho.)
- [ ] No hay dependencias externas: no existe `requirements.txt` con contenido,
      ni imports fuera de la stdlib (salvo excepción documentada en una feature).
- [ ] No hay `print()` sueltos para debug, ni TODOs sin contexto.
- [ ] Los errores salen por `stderr` con exit code != 0, no por `print()`.

## C4 — La verificación es real

- [ ] Si `src/` tiene módulos, `tests/` tiene al menos un test por módulo.
      (En un proyecto recién instanciado este checkbox no aplica todavía.)
- [ ] La sección 6 del verificador muestra `[OK]`, no `[WARN]`: 0 tests
      significa "sin verificar", no "verde". Mientras no haya ninguna feature
      cerrada es un aviso; en cuanto una está en `done`, la sección 4 lo
      convierte en `[FAIL]`.
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
- [ ] Si hubo ronda de análisis, existe su informe (`progress/intake_r<N>.md`)
      y no quedaron requisitos en `draft` sin que el humano lo sepa.

---

**Cómo usar este archivo:** un agente revisor (`.claude/agents/reviewer.md`)
recorre cada checkbox, marca `[x]` o `[ ]`, y rechaza el cierre de sesión
si quedan boxes vacíos en C1-C5. Un checkbox que no aplica se marca `[-]` con
la razón al lado.
