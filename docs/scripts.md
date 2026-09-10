# Scripts del arnés

> La caja de herramientas del repositorio. Cada script lleva además su propia
> cabecera de documentación (`Get-Help ./init.ps1` en PowerShell, o las primeras
> líneas del archivo); aquí está el panorama y los detalles que no caben en una
> cabecera.

| Script | Quién lo ejecuta | Cuándo |
|--------|------------------|--------|
| `init.ps1` / `init.sh` | agente, hook `Stop`, reviewer | al arrancar la sesión y antes de todo `done` |
| `bootstrap.ps1` | humano | una vez, al instanciar un proyecto nuevo desde la plantilla |
| `scripts/validate_project_setup.py` | `init.*` (y a mano) | bloquea el arranque si el proyecto no está configurado |
| `scripts/validate_feature_list.py` | `init.*` (y a mano) | siempre que haya que comprobar el alcance |
| `scripts/validate_requirements.py` | `init.*` (y a mano) | bloquea si se está trabajando sobre un requisito sin aprobar |
| `scripts/harness_test_hook.ps1` | hook `PostToolUse` | automático, tras cada Edit/Write |
| `scripts/demo_orchestration.py` | humano o agente | para entender o demostrar el patrón anti-teléfono-descompuesto |

---

## `init.ps1` / `init.sh` — el verificador

Son **el mismo verificador en dos plataformas**: misma estructura de 7 secciones,
misma salida `[OK]/[WARN]/[FAIL]`, mismo exit code. Usa `init.ps1` en Windows y
`init.sh` en WSL, macOS, Linux o CI. Si cambias uno, cambia el otro.

```
1. Entorno            intérprete de Python detectado y >= 3.9
2. Archivos base      los 8 archivos sin los que el arnés no funciona
3. Configuración      delega en scripts/validate_project_setup.py  (bloqueante)
4. feature_list.json  delega en scripts/validate_feature_list.py
5. Requisitos         delega en scripts/validate_requirements.py   (bloqueante)
6. Tests              descubre y ejecuta tests/
7. Resumen            veredicto + exit code
```

La 5 va **después** de la 4 a propósito: si `feature_list.json` está roto de
forma, el lector ve primero el error de forma y no una cascada de errores de
trazabilidad derivados de él.

**Parámetros:** `init.sh` no tiene ninguno. `init.ps1` acepta `-Quiet` para
resumir la salida de los tests.

**Exit codes:** `0` entorno listo · `1` hay algo que resolver.
Los `[WARN]` **no** bloquean; los `[FAIL]` sí.

**Detalles que importan:**

- **Detección de intérprete.** Prueba `python`, `py` y `python3`, y descarta los
  que existen en el PATH pero no ejecutan nada — en Windows el alias `python3` de
  la Microsoft Store es un stub que solo imprime un aviso de instalación. Por eso
  el script no se fía de `command -v` / `Get-Command`: lanza una sonda real.
- **La plantilla sin instanciar sale en rojo, y es correcto.** La sección 3
  bloquea el arranque mientras el proyecto no esté configurado. Un repo recién
  copiado te dice qué ejecutar (`bootstrap.ps1`) en vez de dejarte trabajar sobre
  un arnés vacío. No es un fallo del template: es el template haciendo su trabajo.
- **0 tests es `[WARN]`, no `[OK]`.** `unittest discover` sobre una carpeta vacía
  termina con éxito, así que un repo recién instanciado parecería verde sin haber
  verificado nada. El verificador cuenta los tests antes de ejecutarlos y
  distingue tres casos: *0 tests* (aviso), *tests en verde* (ok), *tests rotos*
  (fallo). Cuando tu proyecto ya tiene código, un `[WARN]` aquí es una señal de
  alarma, no ruido.

**Cuando falla:**

| Línea | Qué hacer |
|-------|-----------|
| `No se encontró un Python ejecutable` | instala Python >= 3.9 o arregla el PATH |
| `Falta archivo base: X` | el arnés está incompleto: recupera `X` (ver `CHECKPOINTS.md` C1) |
| `Este repositorio es la plantilla del arnés SIN INSTANCIAR` | ejecuta `./bootstrap.ps1 -Name "..."` |
| `docs/architecture.md tiene placeholders sin rellenar` | pídeselo al `analyst` (`/requisitos`); es el criterio del reviewer, sin él no hay revisión posible |
| `sigue en estado "draft" (nadie aprobó ese requisito)` | ejecuta `/aprobar-requisitos`, o devuelve la feature a `draft` |
| `apunta a specs/... que no existe` | corrige el campo `spec` de la feature, o recupera el archivo |
| `está aprobado pero ninguna feature lo referencia` | deriva sus features (`/requisitos`) o vuelve el spec a `draft` |
| `y ningún requisito aprobado` | hay código sin alcance aprobado: define y aprueba los requisitos antes de seguir |
| `Hay N features en in_progress` | cierra o revierte las features de más: una a la vez |
| `No se pudieron descubrir los tests` | hay un error de import en `tests/`; ejecuta el discover a mano para verlo |
| `Hay tests rotos` | arréglalos antes de seguir; no marques nada `done` |

---

## `bootstrap.ps1` — instanciar un proyecto

Convierte la plantilla en tu proyecto. Se ejecuta **una vez**, a mano, justo
después de copiar el repo.

```powershell
./bootstrap.ps1 -Name "mi-proyecto" -WhatIf                       # ensayo en seco
./bootstrap.ps1 -Name "mi-proyecto" -Description "Qué hace."      # de verdad
./bootstrap.ps1 -Name "otro" -Force                               # reinicia también el historial
```

| Parámetro | Efecto |
|-----------|--------|
| `-Name` | obligatorio; nombre del proyecto |
| `-Description` | una línea; si se omite, deja el placeholder |
| `-Force` | reinicia `progress/history.md` aunque tenga entradas |
| `-ResetGit` | borra el `.git` heredado y empieza un historial nuevo |
| `-NoGit` | no toca git en absoluto |
| `-WhatIf` | lista los cambios sin aplicarlos |

Qué toca: `feature_list.json` (nombre, descripción, `features: []`), los
placeholders de `README.md` y de `docs/architecture.md`, `conventions.md` y
`verification.md`, `progress/current.md`, `progress/history.md`, y borra informes
residuales (`progress/explore_*.md`, `impl_*.md`, `review_*.md`).

La lista de archivos con placeholders es explícita a propósito: este archivo y
`CHECKPOINTS.md` *hablan* de los placeholders, así que sustituirlos aquí
destrozaría su propia documentación.

Es idempotente: reejecutarlo con otro nombre solo reescribe el nombre. Protege el
historial: si `progress/history.md` tiene entradas reales, avisa y no lo borra
salvo `-Force`.

### Lo que hace con git

El reviewer identifica los archivos tocados en una sesión comparando contra el
historial. Un proyecto sin repositorio lo deja trabajando a ciegas, con lo único
que le queda: el informe del propio implementer, que es justo a quien tiene que
auditar. Así que el script deja el repositorio en condiciones:

| Situación de partida | Qué hace |
|---|---|
| Copiaste la plantilla (no hay `.git`) | `git init` + commit base `chore: instancia el arnés para <proyecto>` |
| **Clonaste** la plantilla (hay `.git` con `origin` al template) | **desconecta `origin`** y avisa de que conservas el historial de la plantilla |
| Clonaste y pasas `-ResetGit` | borra el `.git` heredado y arranca un historial limpio |
| Repo propio con otro `origin` | lo deja como está |
| `-NoGit` | nada, con un `[WARN]` |

Lo de desconectar el `origin` no es cosmético: si clonas el template y no lo
tocas, **tu primer `git push` manda el proyecto nuevo al repositorio de la
plantilla**. Cuando lo desconecta, la checklist final añade un paso 6 con el
`git remote add origin <url>` que te toca.

Si git no tiene identidad configurada, pone una local provisional
(`harness@localhost`) para poder cerrar el commit base, y lo avisa. Cámbiala por
la tuya antes de empezar a trabajar en serio.

**Qué NO hace:** rellenar `docs/architecture.md`. Ese archivo define qué es "un
buen trabajo" en tu proyecto y es la referencia del reviewer — escribirlo es
trabajo tuyo, y el script te lo recuerda en su checklist final.

Después de ejecutarlo, `./init.ps1` debe quedar verde (con `[WARN]` en tests,
porque todavía no hay código).

---

## `scripts/validate_project_setup.py` — no arrancar a medias

Bloquea la sesión mientras falte lo imprescindible para que el arnés tenga
sentido. La razón es concreta: el reviewer aprueba o rechaza comparando el código
contra `docs/architecture.md`, así que **con ese archivo sin rellenar el reviewer
no tiene criterio** y da por bueno cualquier código que pase los tests. Un arnés
a medio configurar es peor que no tener arnés, porque parece que verifica.

```bash
python scripts/validate_project_setup.py          # el repo actual
python scripts/validate_project_setup.py ../otro
```

**Bloquea (`[FAIL]`)** cuando:

- `feature_list.json` sigue con el placeholder de `project`.
- `docs/architecture.md` conserva placeholders `<...>` o su nota de plantilla.
- `README.md` conserva `<TU_PROYECTO>` o `<DESCRIPCION_PROYECTO>`.

**Solo avisa (`[WARN]`)** cuando falta `description`, no hay features todavía o
`src/` está vacío: son estados normales al principio de un proyecto.

**Caso especial:** si *nada* está configurado, el repo es la plantilla recién
copiada. En vez de escupir todos los fallos, imprime el comando de `bootstrap.ps1`
y para. Ese es el estado en el que vive este template en GitHub: **su verificador
sale en rojo a propósito**.

Exit codes: `0` configurado · `1` falta configuración imprescindible.

---

## `scripts/validate_feature_list.py` — validar el alcance

Comprueba `feature_list.json`: campos obligatorios, ids únicos, estados válidos,
`acceptance` no vacío y **como mucho una feature `in_progress`** (la regla de "una
feature a la vez" del arnés, hecha ejecutable).

```bash
python scripts/validate_feature_list.py                  # feature_list.json
python scripts/validate_feature_list.py otro_archivo.json
```

Exit codes: `0` válido · `1` inválido. Imprime una línea `[FAIL]` por problema.

Existe como módulo aparte a propósito: `init.ps1` e `init.sh` lo invocan los dos,
así que las reglas del alcance no se pueden desincronizar entre Windows y POSIX.
El formato completo está descrito en `schema/feature_list.schema.json`.

---

## `scripts/validate_requirements.py` — no trabajar lo que nadie aprobó

El otro gate del arnés. `validate_project_setup.py` exige que exista **criterio
de calidad**; este exige que exista **alcance aprobado**.

La razón de que sea un script y no una instrucción en un `.md`: la aprobación
de un requisito tiene que sobrevivir a una ventana de contexto perdida. Por eso
no vive en el chat, vive en dos archivos versionados — `estado: aprobado` en el
frontmatter del spec y el `status` de sus features en `feature_list.json` — y
este módulo comprueba que los dos concuerdan.

```bash
python scripts/validate_requirements.py           # el repo actual
python scripts/validate_requirements.py ../otro
```

**Bloquea (`[FAIL]`)** cuando: una feature fuera de `draft` cuelga de un
requisito sin aprobar; hay módulos en `src/` y ningún requisito aprobado; una
feature no tiene `spec` o apunta a un archivo que no existe; un spec aprobado
conserva preguntas abiertas, no tiene fecha de aprobación o no lo referencia
ninguna feature; una feature tiene prioridad más alta que su requisito; o el
nombre, el `id`, el `estado` o la `prioridad` de un spec están mal.

**Solo avisa (`[WARN]`)** cuando: todavía no hay requisitos; hay requisitos en
`draft` esperando el OK del humano; una aprobación quedó a medias; o hay una
feature `in_progress` de menos prioridad que algo encolado — el arnés avisa del
adelantamiento, pero **no interrumpe trabajo a medio escribir**: eso lo decide
el humano.

**Los archivos que empiezan por `_`** (`_plantilla_req.md`, `_entrada.md`) no
son requisitos y se ignoran. Por eso la plantilla puede conservar sus
`<placeholders>`.

Exit codes: `0` la trazabilidad es coherente · `1` hay trabajo sin aprobar o la
trazabilidad está rota.

**Sus propios tests** están en `scripts/tests/`, no en `tests/`, y **no los
ejecuta el verificador**: si estuvieran en `tests/`, un proyecto recién
instanciado saldría verde con tests que no son suyos y el arnés dejaría de
distinguir "sin verificar" de "verificado". Los corre `/harness-check`, o tú:
`python -m unittest discover -s scripts/tests -v`.

---

## `scripts/harness_test_hook.ps1` — feedback tras cada edición

Lo invoca el hook `PostToolUse` de `.claude/settings.json`: cada vez que un
agente escribe o edita un archivo, Claude Code ejecuta este script y le devuelve
el resultado de los tests. No es opcional para el agente — lo dispara el arnés,
no él.

```powershell
./scripts/harness_test_hook.ps1              # a mano, para probarlo
./scripts/harness_test_hook.ps1 -TestsDir tests
```

Exit codes: `0` tests verdes **o** sin tests todavía · `1` tests rotos.

Está en un archivo aparte y no en un one-liner dentro de `settings.json` por un
motivo concreto: `unittest discover` sobre una carpeta sin tests sale con **exit
code 1** ("NO TESTS RAN"), así que en un proyecto recién instanciado el hook
fallaría en cada edición y el agente vería un error en cada paso. El script
cuenta primero y solo falla cuando hay tests y están rotos.

Es feedback rápido, **no** la verificación oficial: esa sigue siendo `init.ps1`,
que además comprueba archivos base y alcance.

---

## `scripts/demo_orchestration.py` — el patrón, sin IA

Demuestra la **regla anti-teléfono-descompuesto**: analiza cada módulo de `src/`,
escribe el informe completo en `progress/explore_<modulo>.md` y devuelve por
stdout **solo la referencia**:

```
done -> progress/explore_storage.md
done -> progress/explore_cli.md
```

Eso es exactamente lo que hace un subagente real: el contenido vive en disco y
por el canal de comunicación viaja una línea. Este script es la versión
determinista y sin modelo del mismo patrón, útil para verlo funcionar sin gastar
una sesión de agente.

```bash
python scripts/demo_orchestration.py
python scripts/demo_orchestration.py --src src --out progress --dry-run
```

| Parámetro | Efecto |
|-----------|--------|
| `--src DIR` | carpeta a analizar (por defecto `src`) |
| `--out DIR` | dónde escribir los informes (por defecto `progress`) |
| `--dry-run` | lista las rutas sin escribir nada |

Exit codes: `0` terminó bien (también si no había módulos: avisa y sale 0) ·
`1` la carpeta de `--src` no existe.

No forma parte de la verificación: ni `init.*` ni ningún hook lo llaman. Con
`src/` vacía no escribe nada — es el estado normal de la plantilla recién
instanciada.
