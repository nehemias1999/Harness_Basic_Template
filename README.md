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
| **1. El repositorio ES el sistema** | `AGENTS.md`, `init.ps1` / `init.sh`, `specs/`, `feature_list.json`, `progress/`, `docs/` |
| **2. Orquestación multi-agente** | `.claude/agents/analyst.md`, `leader.md`, `implementer.md`, `reviewer.md`, `.claude/commands/` |
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

1. **Abre Claude Code en la raíz y pásale tus requisitos en lenguaje normal**
   (o usa `/requisitos`). No hace falta que estén ordenados ni completos: para
   eso está el ciclo. El agente `analyst` los deja como specs en `specs/`, uno
   por requisito, con criterios de aceptación verificables y una prioridad — y
   te **pregunta** lo que no sabe en vez de asumirlo. En la primera ronda
   redacta además un borrador de `docs/architecture.md`.
2. **Léelos e itera.** Agrega, modifica o saca lo que quieras: cada vuelta es
   una ronda y queda registrada en la bitácora de cada spec. Nada se
   implementa mientras tanto.
3. **Cuando estés conforme: `/aprobar-requisitos`.** Ahí los specs quedan
   firmados, sus features pasan a `pending` y se aprueba la arquitectura. Ese
   es el único momento en que el arnés considera que hay trabajo que hacer:
   un "dale" en el chat no aprueba nada, la aprobación queda en git.
4. **Revisa `docs/conventions.md` y `docs/verification.md`.** Vienen con las
   convenciones Python del template; ajústalas a tu gusto.
5. **Ejecuta el verificador** — debe quedar verde.
   ```powershell
   ./init.ps1        # Windows
   ```
   ```bash
   ./init.sh         # WSL / macOS / Linux / CI
   ```
6. **`/next-feature`** para arrancar el desarrollo. Empieza por la feature de
   mayor prioridad, no por la de menor `id`.

Hasta el paso 3 el verificador sale en **rojo a propósito**: el arnés no te
deja programar sobre un proyecto sin requisitos aprobados, porque entonces el
reviewer no tendría contra qué juzgar el código.

Si prefieres escribir los requisitos a mano, puedes: copia
`specs/_plantilla_req.md`, rellena `docs/architecture.md` y añade las features
a `feature_list.json` tú mismo. El arnés valida lo mismo en los dos casos.

## Scripts

| Script | Quién lo ejecuta | Cuándo |
|--------|------------------|--------|
| `init.ps1` / `init.sh` | agente, hook `Stop`, reviewer | al arrancar la sesión y antes de todo `done` |
| `bootstrap.ps1` | humano | una vez, al instanciar el proyecto |
| `scripts/validate_project_setup.py` | `init.*` (y a mano) | bloquea el arranque si el proyecto no está configurado |
| `scripts/validate_requirements.py` | `init.*` (y a mano) | bloquea si se trabaja sobre un requisito sin aprobar |
| `scripts/validate_feature_list.py` | `init.*` (y a mano) | para comprobar el alcance |
| `scripts/harness_test_hook.ps1` | hook `PostToolUse` | automático, tras cada Edit/Write |
| `scripts/demo_orchestration.py` | humano o agente | para ver el patrón anti-teléfono-descompuesto en acción |

Parámetros, exit codes y qué hacer cuando cada uno falla: **`docs/scripts.md`**.

## Windows y POSIX

`init.ps1` e `init.sh` son **el mismo verificador**: misma estructura de siete
secciones, misma salida `[OK]/[WARN]/[FAIL]`, mismo exit code. Usa el `.ps1` en
Windows y el `.sh` en WSL, macOS, Linux o CI. Si tocas uno, toca el otro.

Los hooks de `.claude/settings.json` están escritos en PowerShell porque la
plantilla es canónica en Windows. Para usarla en Linux, cambia en ese archivo
`powershell -File ./init.ps1` por `./init.sh` y `python` por `python3`.

## El ciclo de trabajo

`CLAUDE.md` fuerza a Claude a actuar como **leader**: orquesta, no escribe código.

Son dos ciclos encadenados. El primero define **qué** hay que hacer y lo cierras
vos; el segundo lo construye.

```
   tus requisitos ──>  analyst  ──>  specs/REQ-00N.md  ──>  los lees
   (lenguaje humano)                 (draft, con prioridad)      │
          ↑                                                      │
          └──────── agregás / modificás / sacás ─────────────────┤
                                                                 │ tu OK
                                          /aprobar-requisitos ───┘
                                                    │
                                        (features draft -> pending)
                                                    ▼
leader  ──lanza──>  implementer  ──informe──>  leader  ──lanza──>  reviewer
                    (escribe código                                (aprueba o
                     y tests)                                       rechaza)
                                                                       │
                                        leader cierra la feature  <────┘
                                        (solo si APPROVED)
```

Nadie se autoaprueba, en ninguno de los dos ciclos: el analyst propone
requisitos pero no los aprueba; el implementer deja la feature en
`in_progress` y para; el reviewer no edita código; el leader no implementa. El
alcance lo firmas tú (`/aprobar-requisitos`), y el cierre (`status: "done"`)
solo llega tras un `APPROVED`.

El primer ciclo no es solo del arranque: si a mitad del desarrollo aparece un
requisito nuevo, se repite igual. Las features que crea el analyst nacen en
`draft` y son inertes, así que analizar nunca interrumpe lo que se está
implementando.

Atajos: `/requisitos`, `/aprobar-requisitos`, `/next-feature`,
`/close-session`, `/harness-check`.

## Dónde queda la traza

Por el chat **no pasa código** — solo referencias del tipo
`done -> progress/impl_<feature>.md`. Esa es la regla
anti-teléfono-descompuesto. El contenido vive en disco y queda versionado:

| Archivo | Quién lo escribe | Qué contiene |
|---------|------------------|--------------|
| `specs/_entrada.md` | analyst | Tus pedidos, textuales y fechados |
| `specs/REQ-*.md` | analyst | El requisito en SDD; su `estado` es la aprobación |
| `progress/intake_r<N>.md` | analyst | Qué cambió en la ronda y qué preguntas quedaron |
| `progress/current.md` | leader | Plan vivo de la sesión |
| `progress/impl_<feature>.md` | implementer | Archivos tocados + salida de los tests |
| `progress/review_<feature>.md` | reviewer | Checklist contra `docs/` y `CHECKPOINTS.md` |
| `feature_list.json` | analyst → leader → implementer | `draft` → `pending` → `in_progress` → `done` |
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
├── feature_list.json                # Backlog ejecutable, derivado de specs/
├── init.ps1                         # Verificador (Windows)
├── init.sh                          # Verificador (POSIX)
├── bootstrap.ps1                    # Instancia un proyecto nuevo
├── docs/
│   ├── architecture.md              # Qué significa "buen trabajo" (lo redacta el analyst, lo apruebas tú)
│   ├── conventions.md               # Estilo, nombres, errores
│   ├── verification.md              # Cómo demostrar que funciona
│   └── scripts.md                   # Referencia de los scripts
├── specs/
│   ├── _plantilla_req.md            # Esqueleto de un requisito en SDD
│   ├── _entrada.md                  # Tus pedidos en crudo, append-only
│   └── REQ-00N_<nombre>.md          # Un requisito (estado: draft | aprobado)
├── progress/
│   ├── current.md                   # Sesión activa (estado vivo)
│   ├── intake_r<N>.md               # Informe de cada ronda de análisis
│   └── history.md                   # Bitácora append-only
├── schema/
│   └── feature_list.schema.json     # Formato de una feature
├── scripts/
│   ├── validate_feature_list.py     # Valida el alcance (lo usan init.ps1 e init.sh)
│   ├── validate_requirements.py     # Valida requisito -> feature (íd.)
│   ├── tests/                       # Tests del propio arnés (no los corre init.*)
│   ├── harness_test_hook.ps1        # Tests tras cada edición (hook PostToolUse)
│   └── demo_orchestration.py        # Demo del patrón Líder-Trabajador
├── .claude/
│   ├── agents/                      # analyst, leader, implementer, reviewer
│   ├── commands/                    # /requisitos, /aprobar-requisitos, /next-feature,
│   │                                #   /close-session, /harness-check
│   └── settings.json                # Hooks que automatizan la verificación
├── src/                             # Código de la aplicación (vacío al empezar)
└── tests/                           # Tests automáticos (vacío al empezar)
```

## Aprendizajes que ilustra este proyecto

- **Divulgación progresiva** en `AGENTS.md`: el agente no recibe todas las
  reglas de golpe, recibe un mapa para buscarlas bajo demanda.
- **No se trabaja lo que nadie aprobó**: la aprobación de un requisito es un
  estado en git (`estado: aprobado` + la feature en `pending`), no un mensaje
  en el chat. Sobrevive a una ventana de contexto perdida; un "dale" no.
- **El agente pregunta en vez de asumir**, y eso también es ejecutable: un
  requisito con preguntas abiertas sin responder no se puede aprobar.
- **Una feature a la vez**, validado por el verificador (rechaza más de un
  `in_progress` en `feature_list.json`), y por prioridad: primero lo crítico.
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
