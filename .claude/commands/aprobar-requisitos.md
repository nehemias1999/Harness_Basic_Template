---
description: Aprueba los requisitos en draft: los firma y promueve sus features a pending.
---

El humano dio el OK. Convierte ese OK en estado verificable. Hazlo **entero**:
a mitad de camino el verificador queda en amarillo o en rojo a propósito.

**Antes de tocar nada:** confirma **qué** requisitos aprueba — todos los
`draft`, o una lista. Si no está claro, pregunta. No asumas "todos".

**Pasos, en orden:**

1. Comprueba que ninguno de esos specs tiene preguntas abiertas sin responder
   (`- [ ]` en la sección 6). Si queda alguna, **no apruebas**: se la devuelves
   al `analyst` o se la preguntas al humano.
2. Por cada REQ aprobado, en su frontmatter: `estado: draft` → `estado: aprobado`,
   `aprobado_el:` con la fecha de hoy, y `actualizado:` igual. Añade la fila de
   la bitácora (§8): "aprobado por \<humano\>".
3. Por cada feature de esos REQ en `status: "draft"` → `"pending"`. Ninguna
   otra feature se toca, ningún otro campo se toca.
4. Si esta ronda incluía `docs/architecture.md`: borra su nota inicial
   ("Este archivo es una plantilla... — BORRADOR sin aprobar") **entera**. Ese
   borrado es el acto de aprobación de la arquitectura y queda en git con fecha
   y autor. Si quedó algún `<...>` en el archivo, **no lo inventes**: se lo
   devuelves al `analyst` y no apruebas.
5. Entrada en `progress/history.md` con los REQ aprobados y las features
   promovidas.
6. Verificador. Tiene que quedar verde salvo el `[WARN]` de 0 tests. Si la
   sección 5 falla, **el estado quedó a medias**: lee el mensaje y termina el
   paso que falte antes de decir nada.
7. Dile al humano cuántas features quedaron `pending` y **cuál es la primera**
   según el orden de trabajo (prioridad más alta, y a igual prioridad el `id`
   menor). Si eso desplaza a una feature `in_progress` de menor prioridad,
   dilo con las dos salidas — terminarla, o pasarla a `blocked` con motivo — y
   **deja que decida él**. No interrumpas trabajo a medio escribir por tu
   cuenta.

El siguiente paso es `/next-feature`.

**Lo que NO haces:** escribir código, cambiar `acceptance`, aprobar un REQ que
el humano no nombró, ni promover una feature cuyo spec siga en `draft`.
