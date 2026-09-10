---
description: Firma todos los requisitos en draft de una vez.
---

Atajo de `/aprobar todos`. Ejecutá:

```bash
python scripts/aprobar.py todos
```

Antes de correrlo, **decile al humano qué va a firmar**: los ids y títulos de
los requisitos en `draft`, sacados de `specs/`. Aprobar todo junto es cómodo
cuando venís de una ronda que revisaste entera, y es un error caro cuando se te
coló uno que no habías leído. Que lo vea antes, no después.

Si quiere firmar además `docs/architecture.md`, eso se nombra aparte:
`/aprobar todos arquitectura`.

El resto del recorrido —verificador, entrada en `progress/history.md`, cuál es
la siguiente feature— está en `/aprobar`, y es el mismo.
