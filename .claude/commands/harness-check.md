---
description: Audita el repositorio contra los checkpoints C1-C5 de CHECKPOINTS.md.
---

Audita el estado del repositorio contra `CHECKPOINTS.md` y reporta el resultado.
Es una revisión **de solo lectura**: no arregles nada, solo informa.

**Qué hacer:**

1. Ejecuta el verificador (`./init.ps1` o `./init.sh`) y guarda su salida.
2. Recorre los cinco bloques C1-C5 de `CHECKPOINTS.md`, checkbox por checkbox.
   Marca cada uno:
   - `[x]` se cumple
   - `[ ]` no se cumple → cita archivo y línea concretos
   - `[-]` no aplica todavía → di por qué (p. ej. proyecto sin código aún)
3. Comprueba además que no hay **referencias colgantes**: toda ruta mencionada
   en `CLAUDE.md`, `AGENTS.md`, `README.md` y `docs/scripts.md` existe de verdad.
4. Cierra con un veredicto de una línea: `SANO`, `SANO CON AVISOS` o
   `ROTO`, y los 3 arreglos más urgentes si no está sano.

**No toques ningún archivo.** Si quieres dejar traza, escribe el informe en
`progress/harness_check.md` y devuelve solo la referencia.
