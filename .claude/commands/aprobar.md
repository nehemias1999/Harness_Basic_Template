---
description: Firma los requisitos que le nombres por id, y pasa sus features a pending.
argument-hint: 1 2 [arquitectura]
---

El humano nombró qué aprobar: **`$ARGUMENTS`**. Convertí eso en estado
verificable ejecutando:

```bash
python scripts/aprobar.py $ARGUMENTS
```

Eso es todo lo que tenés que hacer. El script se ocupa de las cuatro cosas que
hay que tocar a la vez —`estado: aprobado`, la fecha, la huella del contenido y
el paso de sus features de `draft` a `pending`— y de la fila de la bitácora. No
lo hagas a mano: a medio camino el repositorio queda incoherente, y es
exactamente el tipo de trabajo mecánico en el que un agente se saltea un paso.

**Qué acepta:**

| Lo que escribe el humano | Qué firma |
|---|---|
| `1 2` · `001 002` · `REQ-001` | esos requisitos |
| `todos` | todos los que estén en `draft` |
| `arquitectura` | además, `docs/architecture.md` |

`arquitectura` va aparte a propósito: es el criterio contra el que el reviewer
juzga **todo** el código, y aprobarlo de rebote junto a un requisito sería el
descuido que el arnés intenta evitar. Si el humano no lo nombró, no lo agregues
vos.

**Después de que el script termine:**

1. Ejecutá el verificador. Tiene que quedar verde salvo el `[WARN]` de 0 tests.
2. Anotá en `progress/history.md` qué se aprobó.
3. Decile cuál es la primera feature según prioridad —la imprime el propio
   verificador en su sección 4— y si eso desplaza a una que esté `in_progress`,
   dale las dos salidas: terminarla, o pasarla a `blocked` con motivo. **La
   decisión de interrumpir es suya.**

**Si el script se niega**, no busques la vuelta: repetí el motivo tal cual. Se
niega por tres razones, y las tres son buenas — el requisito tiene preguntas
sin responder, ya estaba aprobado, o `docs/architecture.md` todavía tiene
huecos. Ninguna se arregla editando el spec a mano.

**Un "dale" en el chat no aprueba nada.** Lo que aprueba es este comando, con
los ids escritos, y queda en git.
