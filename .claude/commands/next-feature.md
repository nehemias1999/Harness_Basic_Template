---
description: Ejecuta el ciclo completo del arnés sobre la siguiente feature pendiente.
---

Coge la siguiente feature `pending` de `feature_list.json` — la de **prioridad
más alta** (`critica` > `alta` > `media` > `baja`) y, a igual prioridad, la de
`id` menor — y ejecuta el ciclo completo del arnés como `leader`.

**Qué dispara:**

1. Verificador (`./init.ps1` en Windows, `./init.sh` en POSIX). Si está rojo,
   paras aquí y reportas.
2. Anota la feature elegida y el plan en `progress/current.md`.
3. Lanza un subagente `implementer` con la feature. Instrúyele para escribir su
   informe en `progress/impl_<feature>.md` y devolverte **solo la referencia**.
4. Cuando termine, lanza un subagente `reviewer`. Su informe va a
   `progress/review_<feature>.md`.
5. Si `APPROVED` → cierras la feature: `status: "done"`, entrada en
   `progress/history.md`, `progress/current.md` vacío, verificador verde.
   Si `CHANGES_REQUESTED` → relanzas al implementer pasándole la **ruta** del
   review, no su contenido.

**Archivos que toca:** `feature_list.json` (el campo `status`, y solo para
cerrar: el paso a `in_progress` lo hace el implementer al tomar la feature),
`progress/current.md`, `progress/history.md`, `progress/impl_<feature>.md`,
`progress/review_<feature>.md`, y `src/` + `tests/` (vía el implementer, nunca
tú directamente).

**Si no hay features `pending`:** dilo y para. No inventes una.

- Si además hay features en `draft`, el problema no es que falte trabajo: hay
  requisitos esperando el OK del humano. Dile cuáles y sugiérele
  `/aprobar <ids>` o `/aprobar-todos`.
- Si tampoco hay `draft`, el proyecto todavía no tiene alcance: `/requisitos`.

**`specs/` es de solo lectura en este ciclo.** Si un criterio de `acceptance`
está mal, el que está mal es el requisito: paras y lo dices, no lo reescribes.
