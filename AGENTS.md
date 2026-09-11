# AGENTS.md — Mapa de navegación para agentes de IA

> Este archivo es el **punto de entrada** para cualquier agente que trabaje en este
> repositorio. NO es una biblia de reglas: es un **mapa**. Lee solo lo que
> necesites cuando lo necesites (divulgación progresiva).

---

## 1. Antes de empezar (obligatorio)

1. Ejecuta el verificador y comprueba que termina sin errores:
   `./init.ps1` en Windows, `./init.sh` en WSL/macOS/Linux. Si falla, **para**
   y resuelve el entorno antes de tocar código. Si su sección 3 dice que el
   proyecto no está configurado, no hay nada que implementar todavía: reporta
   qué falta y para.
2. Lee `progress/current.md` para entender en qué estado quedó la última sesión.
3. Lee `feature_list.json` y elige **una** tarea con estado `pending`. No
   trabajes en más de una a la vez. Las `draft` **no se trabajan**: son
   requisitos que el humano todavía no aprobó. Si solo hay `draft`, no hay
   nada que implementar — dilo y para.

## 2. Mapa del repositorio

| Archivo / carpeta                  | Qué contiene                                              | Cuándo leerlo |
|------------------------------------|-----------------------------------------------------------|---------------|
| `feature_list.json`                | Lista de tareas con estado (draft / pending / in_progress / done / blocked) y prioridad | Siempre, al empezar |
| `specs/`                           | Los requisitos en formato SDD, uno por archivo. La fuente de la que salen las features | Antes de implementar, y siempre que dudes del alcance |
| `progress/current.md`              | Estado de la sesión actual                                | Siempre, al empezar |
| `progress/history.md`              | Bitácora append-only de sesiones anteriores               | Si necesitas contexto histórico |
| `docs/architecture.md`             | Qué significa "hacer un buen trabajo" en este proyecto    | Antes de implementar |
| `docs/conventions.md`              | Reglas de estilo, nombres, estructura                     | Antes de escribir código |
| `docs/verification.md`             | Cómo verificar que tu trabajo funciona                    | Antes de declarar una tarea como `done` |
| `docs/scripts.md`                  | Qué hace cada script, sus parámetros y qué hacer si falla | Si un script falla o no sabes cuál usar |
| `CHECKPOINTS.md`                   | Criterios objetivos de "estado final correcto"            | Para auto-evaluarte |
| `init.ps1` / `init.sh`             | El verificador (mismo comportamiento en ambas plataformas) | Al arrancar y antes de cerrar |
| `bootstrap.ps1` / `bootstrap.sh`   | Instancia un proyecto nuevo desde la plantilla            | Solo la primera vez, y **lo lanza un humano**: está en la lista `deny` |
| `scripts/validate_project_setup.py` | Comprueba que el proyecto está configurado (bloqueante)  | Lo llama el verificador; a mano si dudas de qué falta |
| `scripts/validate_requirements.py` | Comprueba que nadie trabaja sobre un requisito sin aprobar (bloqueante) | Lo llama el verificador; a mano si dudas de la trazabilidad |
| `schema/feature_list.schema.json`  | Formato exacto de una feature                             | Si dudas de la estructura del alcance |
| `.claude/agents/`                  | Definiciones de subagentes (analista, líder, implementador, revisor) | Si orquestas trabajo |
| `.claude/commands/`                | Slash commands del ciclo (`/requirements`, `/approve`, `/approve-all`, `/next-feature`, `/close-session`, `/harness-check`) | Para disparar el ciclo sin escribir el prompt |
| `scripts/demo_orchestration.py`    | Demo del patrón Líder-Trabajador con escritura en disco   | Para entender la regla anti-teléfono-descompuesto |
| `src/`                             | Código de la aplicación                                   | Para implementar |
| `tests/`                           | Tests automáticos                                         | Para verificar |

## 3. Reglas duras (no negociables)

- **No se trabaja lo que nadie aprobó.** Toda feature sale de un requisito de
  `specs/` y no se toca hasta que ese requisito está `aprobado`. Un "dale" en
  el chat no es una aprobación; lo es `/approve`, que queda en git.
- **Una sola feature a la vez.** No mezcles cambios de varias tareas en la misma sesión.
- **No declares una tarea `done` sin pruebas verdes.** Ejecuta el verificador y
  asegúrate de que el bloque de tests pasa al 100%. Ojo: `[WARN] 0 tests`
  significa "sin verificar", no "verde".
- **No te autoapruebas.** El implementer no cierra su propia feature: la cierra
  el líder tras un `APPROVED` del reviewer.
- **Documenta lo que haces** en `progress/current.md` mientras trabajas, no al final.
- **Deja el repositorio limpio** antes de cerrar la sesión (ver §5).
- **Si no sabes algo, busca en `docs/`** antes de inventarlo.

## 4. Cómo elegir una tarea

```
1. Abre feature_list.json
2. Filtra por status == "pending"     (draft = requisito sin aprobar: se ignora)
3. Si no queda ninguna, para: no hay trabajo aprobado
4. Ordena por prioridad: critica > alta > media > baja
5. A igual prioridad, coge la de menor "id"
```

**El cambio de estado lo hace quien trabaja, no quien coordina.** El
`implementer` pone la feature en `in_progress` al tomarla y anota el plan en
`progress/current.md`; el `leader` solo la pasa a `done`, y solo después de un
`APPROVED`. Si dudas de cuál es la siguiente, no la calcules a ojo: el
verificador la imprime en su sección 4.

El orden lo fija `rules.orden_de_trabajo` en `feature_list.json`. La prioridad
la hereda cada feature de su requisito, así que si te parece mal ordenada, lo
que hay que discutir es el requisito — no la feature.

## 5. Cierre de sesión (lifecycle)

Antes de terminar:

1. Ejecuta el verificador — todo verde.
2. Si la tarea está acabada y aprobada: marca `status: "done"` en `feature_list.json`.
3. Mueve el resumen de `progress/current.md` al final de `progress/history.md`.
4. Vacía `progress/current.md` dejando solo la plantilla.
5. No dejes archivos temporales, ni `print()` de debug, ni TODOs sin contexto.

Atajo: `/close-session` hace este recorrido paso a paso.

## 6. Si te bloqueas

- Relee la sección relevante de `docs/`.
- Si el que falla es un script del arnés, mira la tabla "cuando falla" de
  `docs/scripts.md` antes de improvisar.
- Si la herramienta no hace lo que esperas, **no inventes un workaround**:
  documenta el bloqueo en `progress/current.md`, deja la feature en `blocked`
  y para la sesión.
