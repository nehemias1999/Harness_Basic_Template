---
description: Abre o continúa una ronda de análisis de requisitos con el agente analyst.
---

Convierte los requisitos que acaba de dar el humano en specs SDD revisables.
Actúas como `leader`: no analizas tú, lanzas al `analyst`.

Vale en cualquier momento del proyecto, no solo al empezar. Si hay una feature
`in_progress`, **no la toques**: el analyst solo crea features en `draft`, que
son inertes, así que analizar y desarrollar conviven sin pisarse.

**Qué dispara:**

1. Verificador (`./init.ps1` en Windows, `./init.sh` en POSIX). Si está rojo
   por algo que no sea la arquitectura en borrador, paras aquí y reportas.
2. Anotas la ronda en `progress/current.md` — **una línea**, sin borrar lo que
   haya de la sesión activa.
3. Lanzas un subagente `analyst` pasándole los requisitos **textuales** del
   humano, no tu resumen de ellos. Instrúyele para escribir en `specs/` y en
   `progress/intake_r<N>.md`, y devolverte la referencia más su bloque
   `## Para tu revisión`.
4. **Relayas ese bloque literalmente**, sin añadir ni resumir, y le dices qué
   archivos abrir. No cuentes tú lo que dice el spec: si el humano pregunta,
   lees el archivo y citas.

   Las preguntas abiertas son la parte que **no** puede quedarse en el disco:
   el analyst no habla con el humano, así que si no las relayás vos, nadie las
   hace. Pásalas tal cual, numeradas, antes de cualquier otra cosa.
5. Esperas. Si agrega, modifica o saca algo → vuelves al paso 3 con una ronda
   más. Si da el OK → `/aprobar-requisitos`.

**Archivos que toca:** `specs/REQ-*.md`, `specs/_entrada.md`,
`docs/architecture.md` (borrador), `feature_list.json` (solo features en
`draft`), `progress/intake_r<N>.md`, `progress/current.md`. Nunca `src/` ni
`tests/`.

**Un "dale" en el chat no aprueba nada.** La aprobación es
`/aprobar-requisitos`, que la deja escrita en git.
