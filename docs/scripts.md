# Scripts del arnés

> La caja de herramientas del repositorio. Cada script lleva además su propia
> cabecera de documentación (`Get-Help ./init.ps1` en PowerShell, o las primeras
> líneas del archivo); aquí está el panorama y los detalles que no caben en una
> cabecera.

| Script | Quién lo ejecuta | Cuándo |
|--------|------------------|--------|
| `init.ps1` / `init.sh` | agente, hook `Stop`, reviewer | al arrancar la sesión y antes de todo `done` |
| `bootstrap.ps1` / `bootstrap.sh` | humano | una vez, al instanciar un proyecto nuevo desde la plantilla |
| `scripts/validate_project_setup.py` | `init.*` (y a mano) | bloquea el arranque si el proyecto no está configurado |
| `scripts/validate_feature_list.py` | `init.*` (y a mano) | siempre que haya que comprobar el alcance |
| `scripts/validate_requirements.py` | `init.*` (y a mano) | bloquea si se está trabajando sobre un requisito sin aprobar |
| `scripts/harness_hook.py` | hooks `PostToolUse` y `Stop` | automático; bloquean con exit 2 |
| `scripts/approve.py` | `/approve` y `/approve-all` | cuando el humano firma requisitos |
| `scripts/validate_referencias.py` | `/harness-check` y el CI | para que la documentación no mande a archivos que no existen |
| `scripts/instanciar.py` | `bootstrap.ps1` y `bootstrap.sh` | la lógica de instanciación, compartida por las dos plataformas |
| `scripts/demo_orchestration.py` | humano o agente | para entender o demostrar el patrón anti-teléfono-descompuesto |
| `.github/workflows/harness.yml` | GitHub Actions | en cada push y cada PR |

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
| `docs/architecture.md tiene placeholders sin rellenar` | pídeselo al `analyst` (`/requirements`); es el criterio del reviewer, sin él no hay revisión posible |
| `sigue en estado "draft" (nadie aprobó ese requisito)` | el humano lo aprueba con `/approve <id>`, o se devuelve la feature a `draft` |
| `"rules.…" vale … y el arnés trabaja con …` | alguien aflojó una regla del arnés editando `feature_list.json`: devuélvela a su valor |
| `ni un solo test en tests/` | una feature `done` sin pruebas: escribe los tests o reabre la feature |
| `aprobado_el … tiene que ser una fecha` | pon la fecha real de aprobación en formato `AAAA-MM-DD` |
| `el frontmatter repite …` | hay dos veces la misma clave en el spec: deja una |
| `apunta a specs/... que no existe` | corrige el campo `spec` de la feature, o recupera el archivo |
| `está aprobado pero ninguna feature lo referencia` | deriva sus features (`/requirements`) o vuelve el spec a `draft` |
| `y ningún requisito aprobado` | hay código sin alcance aprobado: define y aprueba los requisitos antes de seguir |
| `Hay N features en in_progress` | cierra o revierte las features de más: una a la vez |
| `No se pudieron descubrir los tests` | hay un error de import en `tests/`; ejecuta el discover a mano para verlo |
| `Hay tests rotos` | arréglalos antes de seguir; no marques nada `done` |

---

## `bootstrap.ps1` / `bootstrap.sh` — instanciar un proyecto

Convierte la plantilla en tu proyecto. Se ejecuta **una vez**, a mano, justo
después de copiar el repo.

```powershell
./bootstrap.ps1 -Name "mi-proyecto" -WhatIf                       # ensayo en seco
./bootstrap.ps1 -Name "mi-proyecto" -Description "Qué hace."      # de verdad
./bootstrap.ps1 -Name "otro" -Force                               # insiste sobre un proyecto vivo
```

```bash
./bootstrap.sh --name "mi-proyecto" --dry-run                     # ensayo en seco
./bootstrap.sh --name "mi-proyecto" --description "Qué hace."     # de verdad
```

| Windows | POSIX | Efecto |
|---------|-------|--------|
| `-Name` | `--name` | obligatorio; nombre del proyecto |
| `-Description` | `--description` | una línea; si se omite, deja el placeholder |
| `-Force` | `--force` | instancia aunque ya sea un proyecto, y reinicia `history.md` |
| `-ResetGit` | `--reset-git` | borra el `.git` heredado y empieza un historial nuevo |
| `-NoGit` | `--no-git` | no toca git en absoluto |
| `-WhatIf` | `--dry-run` | lista los cambios sin aplicarlos |

**Los dos son wrappers de `scripts/instanciar.py`**, que es donde vive la
lógica. Son ~200 líneas de decisiones sobre qué borrar y qué conservar:
mantenerlas duplicadas en PowerShell y en bash garantizaba que un día dijeran
cosas distintas, que es el mismo motivo por el que los validadores son módulos
Python compartidos. Los wrappers solo traducen argumentos y buscan el
intérprete.

Qué toca: `feature_list.json` (nombre, descripción, **`features: []`**), los
placeholders de `README.md` y de `docs/architecture.md`, `conventions.md` y
`verification.md`, `progress/current.md`, `progress/history.md`, borra los
informes residuales (`progress/explore_*.md`, `impl_*.md`, `review_*.md`,
`intake_*.md`) y **borra todos los requisitos de `specs/REQ-*.md`**, aprobados
incluidos.

La lista de archivos con placeholders es explícita a propósito: este archivo y
`CHECKPOINTS.md` *hablan* de los placeholders, así que sustituirlos aquí
destrozaría su propia documentación.

**No es idempotente y no es inofensivo**: vacía el alcance y borra los
requisitos. Por eso se planta si el repositorio ya es un proyecto instanciado
—tiene nombre propio o requisitos en `specs/`— y hay que pasarle `-Force` para
insistir. Ese es el guardarraíl que importa; el `ShouldProcess` del script no
pregunta nada con la configuración por defecto de PowerShell.

`progress/history.md` tiene además su propia protección: si tiene entradas
reales, avisa y no lo borra salvo `-Force`.

Y no está en la lista de permisos del agente, está en `deny`: instanciar un
proyecto es un acto humano.

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

## Permisos: `deny` gana sobre `allow`

`.claude/settings.json` ya no pre-aprueba `bootstrap.ps1`: está en `deny`.
Instanciar un proyecto es un acto humano —lo dicen `AGENTS.md` y este mismo
documento— y el script vacía `features`, borra los requisitos de `specs/` y
puede borrar `.git` entero. Tenerlo en `allow` significaba que un agente podía
ejecutarlo sin una sola confirmación. Si necesitás correrlo, corrélo vos.

Los patrones de `allow` son ahora **exactos**, sin comodines de sufijo. Un
patrón como `PowerShell(./init.ps1*)` pre-aprobaba también
`./init.ps1; Remove-Item -Recurse -Force .git`, porque el comodín cubre todo lo
que venga detrás. Y `Bash(python scripts/*)` pre-aprobaba ejecutar **cualquier
archivo que el propio agente acabara de escribir** en `scripts/`. El precio de
la precisión es alguna confirmación de más; vale la pena.

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

Comprueba `feature_list.json`: campos obligatorios, tipos, ids y **nombres**
únicos, estados y prioridades válidos, `acceptance` no vacío y **como mucho una
feature `in_progress`** (la regla de "una feature a la vez" del arnés, hecha
ejecutable). Los nombres tienen que ser únicos porque los informes del
implementer y del reviewer se llaman por el `name` de la feature: dos iguales se
pisan el informe.

También hace ejecutable el cierre de una feature. Para que una feature pueda
estar en `done` tienen que existir sus dos informes —`progress/impl_<name>.md` y
`progress/review_<name>.md`— y el del reviewer tiene que decir `APPROVED`; y
`tests/` tiene que tener al menos un archivo de test (`require_tests_to_close`).
Hasta ahora el ciclo decía "nadie se autoaprueba" pero **ningún código miraba
nunca un veredicto**: bastaba con escribir `done` en el JSON. Esto no vuelve
infalsificable el review —lo escribe un agente— pero obliga a que el artefacto
exista y quede en git, que es lo que permite auditarlo después.

Y cuando todo está en orden imprime **cuál es la siguiente feature** según el
orden de trabajo, para que ese orden deje de depender de que cada agente
interprete bien la regla.

**Las reglas del arnés no se leen del JSON, se comprueban contra él.** `rules`
describe cómo funciona el arnés, y ese archivo lo puede editar cualquier agente:
leer de ahí el vocabulario de estados o el interruptor de "una feature a la vez"
convertía la regla en una sugerencia — bastaba con ampliar `valid_status` o poner
`one_feature_at_a_time: false` para que la feature dejara de ser vigilada. Si el
JSON no coincide con las constantes del código, es un `[FAIL]` que lo dice.

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

**La huella de lo aprobado.** Al firmar un requisito, `/approve`
guarda en `aprobado_hash` una huella de su contenido, y el validador la
recalcula en cada corrida. Sin eso, "aprobado" solo significaba que alguien
escribió la palabra: editarle los criterios después no dejaba ni rastro, y el
reviewer terminaba juzgando el código contra un texto que el humano nunca leyó.
Quedan fuera de la huella §7 (features derivadas) y §8 (bitácora), que cambian
legítimamente después. Para calcularla a mano:

```bash
python scripts/validate_requirements.py --huella specs/REQ-001_x.md
```

**Bloquea (`[FAIL]`)** cuando: una feature fuera de `draft` cuelga de un
requisito sin aprobar; un spec aprobado no tiene `aprobado_hash` o su contenido
cambió después de aprobarse; hay **código** en `src/` (recursivo, cualquier lenguaje) y
ningún requisito aprobado; una feature no tiene `spec` o apunta a un archivo que
no existe; un spec aprobado conserva preguntas abiertas, no tiene fecha de
aprobación o la fecha no es `AAAA-MM-DD`, o no lo referencia ninguna feature; una
feature tiene prioridad más alta que su requisito; el frontmatter repite claves;
o el nombre, el `id`, el `estado` o la `prioridad` de un spec están mal.

"Fuera de `draft`" se evalúa **por complemento**: cualquier estado que no sea
`draft` cuenta como trabajo empezado. Con una lista blanca de estados, inventar
uno nuevo bastaba para que la feature escapara del gate sin que ningún validador
la mirase.

**Solo avisa (`[WARN]`)** cuando: todavía no hay requisitos; hay requisitos en
`draft` esperando el OK del humano; una aprobación quedó a medias; de un spec
`descartado` todavía cuelgan features en `draft`; o hay una feature
`in_progress` de menos prioridad que algo encolado — el arnés avisa del
adelantamiento, pero **no interrumpe trabajo a medio escribir**: eso lo decide
el humano.

**Los archivos que empiezan por `_`** (`_plantilla_req.md`, `_entrada.md`) no
son requisitos y se ignoran. Por eso la plantilla puede conservar sus
`<placeholders>`.

Exit codes: `0` la trazabilidad es coherente · `1` hay trabajo sin aprobar o la
trazabilidad está rota.

**Los tests del arnés** —de este validador y de sus dos hermanos— están en
`scripts/tests/`, no en `tests/`, y **no los ejecuta el verificador**: si estuvieran en `tests/`, un proyecto recién
instanciado saldría verde con tests que no son suyos y el arnés dejaría de
distinguir "sin verificar" de "verificado". Los corre `/harness-check`, o tú:
`python -m unittest discover -s scripts/tests -v`.

---

## `scripts/approve.py` — firmar requisitos

El paso mecánico de la aprobación. El humano dice **qué** aprobar; el script se
ocupa de las cuatro cosas que hay que tocar a la vez.

```bash
python scripts/approve.py 1 2             # REQ-001 y REQ-002
python scripts/approve.py REQ-003         # da igual cómo escribas el id
python scripts/approve.py all             # todos los que estén en draft
python scripts/approve.py 1 architecture  # y además firma docs/architecture.md
python scripts/approve.py all --dry-run
```

Por cada requisito nombrado: `estado: draft` → `aprobado`, la fecha de hoy en
`aprobado_el` y `actualizado`, la huella del contenido en `aprobado_hash`, la
fila de la bitácora (§8), y sus features de `draft` a `pending`.

**Por qué es un script y no la prosa de un `.md`.** Son cuatro archivos que hay
que dejar coherentes entre sí, y a medio camino el repositorio queda en un
estado que el verificador marca en rojo. Ese es exactamente el tipo de trabajo
en el que un agente se saltea un paso, y el que más fácil se saltea es justo el
que hace verificable la aprobación: la huella.

**Es todo o nada.** Si algo de lo que nombraste no se puede firmar —tiene
preguntas sin responder, ya estaba aprobado, o `docs/architecture.md` conserva
huecos— no se escribe nada. Firmar la mitad deja un estado que nadie pidió.

**`architecture` se nombra aparte** a propósito: es el criterio contra el que el
reviewer juzga *todo* el código, y aprobarlo de rebote junto a un requisito
sería el descuido que el arnés intenta evitar.

**No está en la lista de permisos, y es a propósito.** Cuando el agente lo
ejecuta, Claude Code te muestra el comando exacto —`python scripts/approve.py
1 2`— y espera tu confirmación. Ese aviso es la última oportunidad de ver *qué*
se está firmando antes de que se firme, y sale gratis.

Exit codes: `0` firmado (o simulado) · `1` no se firmó nada, y el motivo está
impreso.

---

## Actualizar un proyecto hecho con una plantilla vieja

Un proyecto instanciado antes de la capa de requisitos sale en rojo apenas
actualiza el arnés, y con razón: le falta la mitad del contrato. Qué hay que
hacer, una vez:

1. En `feature_list.json`, `rules` pasa a:
   ```json
   "one_feature_at_a_time": true,
   "require_tests_to_close": true,
   "orden_de_trabajo": "prioridad_luego_id",
   "valid_status": ["draft", "pending", "in_progress", "done", "blocked"]
   ```
2. Cada feature necesita `spec` y `prioridad`. Si el trabajo ya está hecho y no
   hay requisito escrito, escribí uno retroactivo con `/requirements` que cubra
   lo que existe: es más honesto que inventar un puntero, y deja el "por qué"
   documentado antes de que se pierda.
3. Las features `done` necesitan sus informes en `progress/`. Si son de antes y
   no existen, la salida menos mala es dejar constancia de eso mismo en el
   informe: "cerrada antes de que el arnés exigiera review".
4. `./init.ps1` o `./init.sh` te va diciendo qué falta, de a un error por causa.

---

## `scripts/harness_hook.py` — los hooks, y por qué bloquean

Los dos hooks de `.claude/settings.json` viven aquí:

```bash
python scripts/harness_hook.py stop                  # antes de cerrar el turno
python scripts/harness_hook.py post-edit             # tras cada Edit/Write
python scripts/harness_hook.py post-edit --tests-dir tests
```

Exit codes: `0` todo en orden (o no hay nada que verificar todavía) · **`2`
bloquea**.

**El 2 es el punto entero de este archivo.** Un hook que sale con 1 no bloquea
nada: Claude Code muestra la salida y la sesión sigue igual. Los hooks del arnés
salían con 1, así que durante un tiempo el repositorio afirmaba que no se podían
saltar mientras la sesión cerraba tranquilamente con el verificador en rojo. Con
exit 2 el turno no cierra, y el motivo —que va por **stderr**, no por stdout— se
le devuelve al modelo como algo que tiene que resolver.

`stop` corre el verificador entero; `post-edit` cuenta los tests y, si hay,
los ejecuta. Cuenta antes de ejecutar porque `unittest discover` sobre una
carpeta vacía sale con error ("NO TESTS RAN") y un proyecto recién instanciado
vería un fallo en cada edición.

**El bucle.** Claude Code vuelve a llamar al hook `stop` después de que el
agente reacciona. Si bloqueara siempre, la sesión no cerraría nunca: por eso se
respeta `stop_hook_active`, que avisa de que ya venimos de un bloqueo. Y ojo:
`stop` **no se dispara si interrumpes con Ctrl+C**.

### `pre-tool-use` — lo único que llega a tiempo

`stop` y `post-edit` llegan cuando la escritura ya ocurrió. `PreToolUse` llega
antes, y es donde el arnés protege **la capa que lo verifica**: `scripts/`,
`.claude/`, `schema/`, `init.*`, `bootstrap.ps1`, `AGENTS.md`, `CLAUDE.md` y
`CHECKPOINTS.md`.

El motivo es concreto: un agente que ve rojo tiene a mano una forma trivial de
ponerlo en verde, que es editar el validador. Pedírselo por favor en un `.md` no
alcanza, porque es exactamente el archivo que puede reescribir.

También mira los comandos de shell, porque el matcher `Edit|Write` no ve un
`echo x > scripts/validador.py`. Es una heurística corta —busca señales de
escritura (`>`, `rm`, `mv`, `sed -i`, `Remove-Item`…) sobre rutas protegidas— y
se queda deliberadamente corta: perseguir todas las formas de escribir desde
`Bash` daría falsos positivos constantes. Sigue siendo una red, no una jaula.

**Cómo mantener el propio arnés.** La puerta existe, pero hay que abrirla a
sabiendas: creá `.harness-mantenimiento` en la raíz (o exportá
`HARNESS_MANTENIMIENTO=1`) y borralo al terminar. La diferencia con no tener
protección es que el archivo aparece en `git status`: la edición deja de ser
silenciosa y pasa a ser una decisión visible.

Es Python y no PowerShell para que funcione igual en Windows y en POSIX: la
versión anterior era PowerShell puro y en WSL o Linux no corría en absoluto.
Internamente elige `init.ps1` o `init.sh` según el sistema.

---

## `.github/workflows/harness.yml` — el arnés verificándose

Tres jobs en cada push y cada PR:

- **POSIX**: los tests del arnés, `init.sh`, los validadores por separado, y
  una comprobación de que los hooks **siguen saliendo con 2**. Si eso se
  rompiera, los hooks volverían a ser decorativos y nadie se enteraría hasta
  que una sesión cerrara con el verificador en rojo.
- **Windows**: los tests e `init.ps1`, porque el `.ps1` es el canónico de la
  plantilla y hasta ahora nadie lo corría más que a mano.
- **Paridad**: comprueba que `init.ps1` e `init.sh` declaran exactamente las
  mismas secciones. `docs/scripts.md` dice "si cambias uno, cambia el otro";
  esto lo convierte en algo comprobable en vez de una buena intención.

El verificador **tiene que salir con 1** en este repositorio: es la plantilla
sin instanciar y su sección 3 lo bloquea a propósito. El CI comprueba que falle
por esa razón y no por otra, y que las secciones que no dependen de la
instanciación estén en verde.

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
