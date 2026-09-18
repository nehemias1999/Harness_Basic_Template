---
project: <YOUR_PROJECT>
description:
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

# Alcance del proyecto

`project` y `description` son los datos que antes vivían en
`feature_list.json`. `scripts/instantiate.py` (bootstrap) los rellena al crear
el proyecto. Las reglas del harness (`one_feature_at_a_time`,
`require_tests_to_close`, `work_order`, statuses válidos) son constantes del
código, no configuración: no se eligen desde aquí.

## Estado de las features

El estado de cada feature vive en el front matter de su nota en `features/`:

| status       | significado                                        |
|--------------|----------------------------------------------------|
| `draft`      | en análisis, nadie lo toca hasta que se apruebe    |
| `pending`    | requisito aprobado, listo para desarrollar         |
| `in_progress`| siendo implementado (solo uno a la vez)            |
| `done`       | cerrado con tests en verde y revisión `APPROVED`   |
| `blocked`    | parado por un bloqueo real, con motivo en la nota  |

El verifier valida el contenido, no el nombre: `draft` → `pending` lo hace
`approve.py` al firmar el requisito; `pending` → `in_progress` lo hace el
implementer al tomarla; `in_progress` → `done` lo hace el leader solo tras un
`APPROVED` del reviewer.