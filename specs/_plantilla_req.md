---
id: REQ-00N
titulo: <Una línea, en lenguaje de negocio>
estado: draft
prioridad: media
creado: <YYYY-MM-DD>
actualizado: <YYYY-MM-DD>
aprobado_el:
aprobado_hash:
ronda: 1
---

<!-- Plantilla de requisito. La escribe el agente `analyst`, la lee un humano.
     Objetivo de tamaño: menos de 80 líneas. Si no entra, son dos requisitos.

     El frontmatter es lo ÚNICO que lee scripts/validate_requirements.py:
     mantenlo con claves planas `clave: valor`, sin listas ni anidamiento.

     Estados: draft (en análisis) · aprobado (firmado por el humano) ·
     descartado (el humano lo sacó; el archivo se queda como historia).
     Prioridad: critica · alta · media · baja. La heredan sus features.

     `aprobado_el` y `aprobado_hash` los escribe scripts/aprobar.py cuando el
     humano firma (`/aprobar <id>`). No los rellenes a mano.
     La huella es del contenido de este archivo (sin §7 ni §8, que cambian
     después): si alguien edita los criterios de un requisito ya aprobado, el
     verificador lo dice en vez de dejar al reviewer juzgando contra algo que
     nadie leyó.

     Este archivo empieza por `_`, así que el validador lo ignora: por eso
     puede conservar sus <placeholders>. -->

# REQ-00N — <titulo>

## 1. Origen (palabras del humano, textuales)

> <pega aquí lo que pidió el humano, sin reescribirlo ni "mejorarlo">

Entrada completa: `specs/_entrada.md#<fecha>`.

## 2. Problema y objetivo

<2-4 frases: qué duele hoy y qué se quiere conseguir. No la solución.>

## 3. Alcance

**Incluye:** <lista corta>

**No incluye:** <lista corta — esto es lo que evita que el alcance crezca solo>

## 4. Comportamiento esperado

- **Camino feliz:** dado <contexto>, cuando <acción>, entonces <resultado>.
- **Errores:** cuando <caso>, <qué hace el sistema> (mensaje y exit code).

## 5. Criterios de aceptación

<Numerados y verificables. De aquí sale, uno a uno, el `acceptance` de las
features. Si un criterio no se puede convertir en un test, está mal escrito:
"rápido" no es un criterio, "responde en menos de 200 ms sobre 10.000 notas" sí.>

1. <criterio>
2. <criterio>

## 6. Supuestos y preguntas abiertas

<Todo lo que no te dijeron y hace falta. Nada de esto se resuelve inventando.
Mientras quede una casilla `- [ ]` sin marcar, el requisito NO se puede aprobar:
lo bloquea scripts/validate_requirements.py.>

- **Supuesto (sin confirmar):** <lo que asumimos y nadie confirmó todavía>
- [ ] **P1:** <pregunta que bloquea o cambia un criterio>

## 7. Features derivadas

<Informativo, para el humano. La verdad está en feature_list.json: el puntero va
de la feature al spec, no al revés, y este cuadro NO se valida.>

| feature `name` | id | prioridad | qué criterios cubre |
|----------------|----|-----------|---------------------|
| <nombre_snake_case> | <id> | <heredada, o menor con motivo> | 1, 2 |

## 8. Bitácora de revisiones

| ronda | fecha | qué cambió | a pedido de |
|-------|-------|-----------|-------------|
| 1 | <YYYY-MM-DD> | versión inicial | <humano> |
