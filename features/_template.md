---
id: 1
name: short_snake_case
title: Readable feature title
description: What it does and why, in 1-2 sentences.
spec: "[[REQ-001_requirement_name]]"
priority: high
status: draft
acceptance:
  - "an acceptance criterion, verifiable and concrete"
  - "another acceptance criterion"
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
tags:
  - feature
---

# F-001 — Readable feature title

<!-- Feature template. The analyst agent derives each feature from one
     criterion of section 5 of its requirement (specs/REQ-00N_*.md).

     The front matter is the ONLY thing the validators read: keep it flat
     `key: value` except `acceptance` and `tags`, which are lists written as
     indented `- "item"` lines. `spec` is a wikilink to the requirement note;
     with Dataview installed it draws the edge in the graph.

     `status` is the state machine of the harness: draft (inert) -> pending
     (requirement approved, /approve moves it) -> in_progress (the implementer
     takes it) -> done (only after a reviewer's APPROVED) | blocked.

     `id` and `name` must match the file name: F-<id>_<name>.md.
     `priority` is inherited from the requirement; it may be lowered, never
     raised. `created`/`updated` are YYYY-MM-DD.

     This file starts with `_` so the validators ignore it: that is why it can
     keep its <placeholders>. Copy it to produce a real feature note. -->

Feature `<name>`, derivada del requisito [[REQ-001_requirement_name]]. Nace en
`draft` y es **inerte** hasta que su requisito está aprobado.

## Estado

- **status:** `draft`
- **prioridad:** `high` (hereda del requisito; puede bajarse, nunca subirse)
- **spec:** [[REQ-001_requirement_name]]

## Aceptación

Nos llega de la sección 5 del requisito, una a una. Cada criterio tiene que
poder convertirse en una prueba; si no, el criterio está mal escrito.

1. <criterion>
2. <criterion>

## Informes

Cuando se desarrolle y revise, enlazan aquí los informes del ciclo:

- [[impl_<name>]] — el implementer
- [[review_<name>]] — el reviewer

## Historial

| fecha | cambio | quién |
|-------|--------|-------|
| <YYYY-MM-DD> | creada | analyst |