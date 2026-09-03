# <TU_PROYECTO>

> <DESCRIPCION_PROYECTO>

Este repositorio trabaja con un **arnés** (harness): un conjunto de archivos,
scripts y roles que permiten a un agente de IA trabajar de forma autónoma y
**verificable**. Lo importante no es qué hace la app, sino cómo está estructurado
el repo para que un agente pueda avanzar sin supervisión constante y sin
inventarse que algo funciona.

Si acabas de copiar esta plantilla, ve a [Arranque rápido](#arranque-rápido).

## Los tres pilares

| Pilar | Manifestación en este repo |
|-------|----------------------------|
| **1. El repositorio ES el sistema** | `AGENTS.md`, `init.ps1` / `init.sh`, `feature_list.json`, `progress/`, `docs/` |
| **2. Orquestación multi-agente** | `.claude/agents/leader.md`, `implementer.md`, `reviewer.md`, `.claude/commands/` |
| **3. Supervisión y mejora** | `CHECKPOINTS.md`, hooks en `.claude/settings.json`, `tests/` |

## Arranque rápido

```powershell
./bootstrap.ps1 -Name "mi-proyecto" -Description "Qué hace." -WhatIf   # ensayo
./bootstrap.ps1 -Name "mi-proyecto" -Description "Qué hace."           # de verdad
```

Si **clonaste** esta plantilla en vez de copiarla, añade `-ResetGit` para no
arrastrar su historial. En cualquiera de los dos casos el script deja el
repositorio git del proyecto listo y, si hacía falta, desconecta el `origin`
heredado — sin eso tu primer `git push` iría al repo de la plantilla.

Después, en este orden:

1. **Rellena `docs/architecture.md`.** Es el documento contra el que el reviewer
   evalúa el código: capas, principios y flujo de datos de *tu* proyecto. Mientras
   tenga placeholders `<...>`, el arnés no tiene criterio de calidad.
2. **Revisa `docs/conventions.md` y `docs/verification.md`.** Vienen con las
   convenciones Python del template; ajústalas a tu gusto.
3. **Añade tus primeras features a `feature_list.json`**, copiando el bloque
   `_example`. El campo `acceptance` es lo que el reviewer usa para aprobar o
   rechazar: escríbelo como criterios verificables, no como deseos.
4. **Ejecuta el verificador** — debe quedar verde. Hasta que completes los pasos
   1-3 saldrá en **rojo a propósito**: el arnés no te deja trabajar sobre un
   proyecto sin configurar, porque el reviewer no tendría criterio con el que
   juzgar el código.
   ```powershell
   ./init.ps1        # Windows
   ```
   ```bash
   ./init.sh         # WSL / macOS / Linux / CI
   ```
5. **Abre Claude Code en la raíz** y pide: «implementa la siguiente feature
   pendiente» (o usa `/next-feature`).

## Scripts

| Script | Quién lo ejecuta | Cuándo |
|--------|------------------|--------|
| `init.ps1` / `init.sh` | agente, hook `Stop`, reviewer | al arrancar la sesión y antes de todo `done` |
| `bootstrap.ps1` | humano | una vez, al instanciar el proyecto |
| `scripts/validate_project_setup.py` | `init.*` (y a mano) | bloquea el arranque si el proyecto no está configurado |
| `scripts/validate_feature_list.py` | `init.*` (y a mano) | para comprobar el alcance |
| `scripts/harness_test_hook.ps1` | hook `PostToolUse` | automático, tras cada Edit/Write |
| `scripts/demo_orchestration.py` | humano o agente | para ver el patrón anti-teléfono-descompuesto en acción |

Parámetros, exit codes y qué hacer cuando cada uno falla: **`docs/scripts.md`**.

## Windows y POSIX

`init.ps1` e `init.sh` son **el mismo verificador**: misma estructura de cinco
secciones, misma salida `[OK]/[WARN]/[FAIL]`, mismo exit code. Usa el `.ps1` en
Windows y el `.sh` en WSL, macOS, Linux o CI. Si tocas uno, toca el otro.

Los hooks de `.claude/settings.json` están escritos en PowerShell porque la
plantilla es canónica en Windows. Para usarla en Linux, cambia en ese archivo
`powershell -File ./init.ps1` por `./init.sh` y `python` por `python3`.

## El ciclo de trabajo

`CLAUDE.md` fuerza a Claude a actuar como **leader**: orquesta, no escribe código.

```
leader  ──lanza──>  implementer  ──informe──>  leader  ──lanza──>  reviewer
                    (escribe código                                (aprueba o
                     y tests)                                       rechaza)
                                                                       │
                                        leader cierra la feature  <────┘
                                        (solo si APPROVED)
```

Nadie se autoaprueba: el implementer deja la feature en `in_progress` y para; el
reviewer no edita código; el leader no implementa. El cierre (`status: "done"`)
solo llega tras un `APPROVED`.

Atajos: `/next-feature`, `/close-session`, `/harness-check`.

## Dónde queda la traza

Por el chat **no pasa código** — solo referencias del tipo
`done -> progress/impl_<feature>.md`. Esa es la regla
anti-teléfono-descompuesto. El contenido vive en disco y queda versionado:

| Archivo | Quién lo escribe | Qué contiene |
|---------|------------------|--------------|
| `progress/current.md` | leader | Plan vivo de la sesión |
| `progress/impl_<feature>.md` | implementer | Archivos tocados + salida de los tests |
| `progress/review_<feature>.md` | reviewer | Checklist contra `docs/` y `CHECKPOINTS.md` |
| `feature_list.json` | implementer → leader | `pending` → `in_progress` → `done` |
| `progress/history.md` | leader | Resumen append-only al cerrar la sesión |

Abre `progress/` en tu editor mientras Claude trabaja: cada informe aparece en
cuanto el subagente termina. Así auditas paso a paso quién decidió qué.

## Estructura

```
.
├── AGENTS.md                        # Mapa para agentes (divulgación progresiva)
├── CLAUDE.md                        # Fuerza el rol `leader` en cada sesión
├── CHECKPOINTS.md                   # Criterios de "estado final correcto"
├── README.md                        # Este archivo
├── feature_list.json                # Alcance: una feature a la vez
├── init.ps1                         # Verificador (Windows)
├── init.sh                          # Verificador (POSIX)
├── bootstrap.ps1                    # Instancia un proyecto nuevo
├── docs/
│   ├── architecture.md              # Qué significa "buen trabajo"  ← RELLENAR
│   ├── conventions.md               # Estilo, nombres, errores
│   ├── verification.md              # Cómo demostrar que funciona
│   └── scripts.md                   # Referencia de los scripts
├── progress/
│   ├── current.md                   # Sesión activa (estado vivo)
│   └── history.md                   # Bitácora append-only
├── schema/
│   └── feature_list.schema.json     # Formato de una feature
├── scripts/
│   ├── validate_feature_list.py     # Valida el alcance (lo usan init.ps1 e init.sh)
│   ├── harness_test_hook.ps1        # Tests tras cada edición (hook PostToolUse)
│   └── demo_orchestration.py        # Demo del patrón Líder-Trabajador
├── .claude/
│   ├── agents/                      # leader, implementer, reviewer
│   ├── commands/                    # /next-feature, /close-session, /harness-check
│   └── settings.json                # Hooks que automatizan la verificación
├── src/                             # Código de la aplicación (vacío al empezar)
└── tests/                           # Tests automáticos (vacío al empezar)
```

## Aprendizajes que ilustra este proyecto

- **Divulgación progresiva** en `AGENTS.md`: el agente no recibe todas las
  reglas de golpe, recibe un mapa para buscarlas bajo demanda.
- **Una feature a la vez**, validado por el verificador (rechaza más de un
  `in_progress` en `feature_list.json`).
- **Estado en disco**, no en chat: `progress/current.md` y `history.md`
  sobreviven a reinicios y context windows reventadas.
- **Verificación ejecutable**: el verificador corre los tests reales, no se fía
  de lo que diga el agente. Y distingue "0 tests" de "todo verde" — un repo sin
  tests no está verificado, aunque `unittest` salga con éxito.
- **Patrón Líder-Trabajador-Revisor**: el líder no implementa, el implementador
  no se autoaprueba, el revisor no edita código.
- **Anti teléfono-descompuesto**: los subagentes escriben sus resultados en
  archivos y solo devuelven una referencia ligera.
- **Los permisos son parte del diseño**: si un subagente necesita escribir su
  informe, su frontmatter tiene que incluir `Write`. Un rol sin las herramientas
  para cumplir su protocolo es un rol roto.
