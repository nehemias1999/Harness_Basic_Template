---
description: Ejecuta el ciclo completo del arnés sobre la siguiente feature pendiente.
---

Coge la siguiente feature `pending` de `feature_list.json` (la de menor `id`) y
ejecuta el ciclo completo del arnés como `leader`.

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

**Archivos que toca:** `feature_list.json` (campo `status`),
`progress/current.md`, `progress/history.md`, `progress/impl_<feature>.md`,
`progress/review_<feature>.md`, y `src/` + `tests/` (vía el implementer, nunca
tú directamente).

**Si no hay features `pending`:** dilo y para. No inventes una.
