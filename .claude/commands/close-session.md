---
description: Cierra la sesión siguiendo el lifecycle de AGENTS.md §5.
---

Cierra la sesión actual siguiendo el lifecycle de `AGENTS.md §5`. Recórrelo en
orden y reporta cada paso:

1. **Verificador verde.** Ejecuta `./init.ps1` (Windows) o `./init.sh` (POSIX).
   Si está rojo, **no cierres**: informa de qué falla y para.
2. **Estado de la feature.** Comprueba el veredicto en
   `progress/review_<feature>.md`:
   - `APPROVED` → `status: "done"` en `feature_list.json`.
   - `CHANGES_REQUESTED` o sin review → déjala en `in_progress`, o en `blocked`
     si hay un bloqueo real, y dilo explícitamente.
3. **Historial.** Añade al final de `progress/history.md` una entrada con el
   formato que documenta ese archivo (fecha, feature, agente, resultado,
   archivos tocados, verificación, notas).
4. **Reset.** Vacía `progress/current.md` dejando solo la plantilla.
5. **Ronda de análisis a medias.** Si hay requisitos en `draft`, dilo antes de
   cerrar, con sus ids: el humano decide entre aprobarlos (`/aprobar 1 2`) o dejarlos
   para la próxima sesión. Un `draft` sobrevive perfectamente al cierre — lo
   que no puede pasar es que se cierre en silencio y nadie se acuerde de que
   había algo esperando su OK.
6. **Limpieza.** Revisa `git status`: sin `*.tmp`, sin `__pycache__` fuera del
   `.gitignore`, sin `print()` de debug ni TODOs sin contexto.
7. **Resumen final** en 3-5 líneas: qué se cerró, qué queda pendiente y cuál es
   el primer paso de la próxima sesión.

**Archivos que toca:** `feature_list.json`, `progress/current.md`,
`progress/history.md`. Nunca `src/`, `tests/` ni `specs/`.
