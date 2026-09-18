---
tags:
  - dashboard
title: Panel de mando del proyecto
---

# Panel de mando

> Este repositorio **es el vault** de Obsidian del proyecto. El estado vive en el
> front matter de las notas de `features/`; el harness lo valida con
> `./init.sh`. Cambia `status:` de una nota para actualizar el estado. Ver
> `docs/obsidian.md`.

## Features por estado

```dataview
TABLE status AS Estado, priority AS Prioridad, spec AS Requisito, file.ctime AS Creado
FROM "features"
WHERE file.name != "_project" AND file.name != "_template"
SORT id ASC
```

## Requisitos

```dataview
TABLE status AS Estado, priority AS Prioridad, round AS Ronda
FROM "specs"
WHERE file.name != "_req_template" AND file.name != "_intake"
SORT file.name ASC
```

## Próximas features a desarrollar

```dataview
TABLE priority AS Prioridad, spec AS Requisito
FROM "features"
WHERE status = "pending"
SORT priority ASC, id ASC
LIMIT 5
```

## Features en curso o bloqueadas

```dataview
TABLE priority AS Prioridad, spec AS Requisito
FROM "features"
WHERE status = "in_progress" OR status = "blocked"
SORT status ASC, id ASC
```

> El orden "real" de trabajo lo imprime siempre el verifier (`./init.sh`,
> sección 4): `critical > high > medium > low` y, a igual prioridad, el `id` más
> bajo. El dashboard es una vista humana, no un juicio.