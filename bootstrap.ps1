<#
.SYNOPSIS
    Instancia un proyecto nuevo a partir de esta plantilla de arnés.

.DESCRIPTION
    Rellena los placeholders del template y deja el repositorio en estado
    "proyecto recién empezado":

      1. `feature_list.json` -> escribe project/description y vacía `features`.
      2. Sustituye `<TU_PROYECTO>` y `<DESCRIPCION_PROYECTO>` en README.md y
         en docs/architecture.md, conventions.md y verification.md.
      3. Resetea `progress/current.md` y `progress/history.md` a su plantilla.
      4. Borra informes de sesiones anteriores (`progress/explore_*.md`,
         `impl_*.md`, `review_*.md`, `intake_*.md`) si quedara alguno.
      5. Crea `specs/` y borra los requisitos del proyecto anterior
         (`specs/REQ-*.md`), que ya no tienen features a las que apuntar.

    Lo ejecuta un humano UNA vez, justo después de copiar la plantilla. Es
    idempotente: volver a ejecutarlo con otro nombre solo reescribe el nombre.

    Lo que NO hace: definir el alcance por ti. El borrador de
    `docs/architecture.md` y los requisitos los redacta el agente `analyst`
    (`/requisitos`), pero **aprobarlos es tuyo** y hasta que lo hagas el
    verificador no se pone verde. El script te lo recuerda al terminar.

.PARAMETER Name
    Nombre del proyecto nuevo (obligatorio).

.PARAMETER Description
    Una línea describiendo el proyecto. Si se omite, deja el placeholder.

.PARAMETER Force
    No pide confirmación al sobrescribir el historial de `progress/`.

.PARAMETER ResetGit
    Borra el `.git` heredado de la plantilla y empieza un historial nuevo.
    Úsalo cuando hayas CLONADO el template: sin esto te quedas con sus commits.

.PARAMETER NoGit
    No toca git en absoluto. Para cuando gestionas el repositorio a mano.

.EXAMPLE
    ./bootstrap.ps1 -Name "mi-proyecto" -WhatIf

.EXAMPLE
    ./bootstrap.ps1 -Name "mi-proyecto" -ResetGit

.EXAMPLE
    ./bootstrap.ps1 -Name "mi-proyecto" -Description "Pipeline de ingesta diaria."

.OUTPUTS
    Líneas [OK] / [WARN] por cada cambio aplicado, y una checklist final.

.NOTES
    Exit codes: 0 instanciado · 1 faltan archivos de la plantilla.
    Después de ejecutarlo, valida con ./init.ps1 (debe quedar verde).

    Sobre git: el reviewer identifica los archivos tocados en una sesión
    comparando contra el historial, así que un proyecto sin repo lo deja
    trabajando a ciegas. Este script deja el repositorio listo (ver sección 5).
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Name,

    [string]$Description = "",

    [switch]$Force,

    [switch]$ResetGit,

    [switch]$NoGit
)

Set-Location -Path $PSScriptRoot

function Write-Ok   { param([string]$Message) Write-Host "[OK]    $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "[WARN]  $Message" -ForegroundColor Yellow }
function Write-Fail { param([string]$Message) Write-Host "[FAIL]  $Message" -ForegroundColor Red }

$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Set-Utf8File {
    param([string]$Path, [string]$Content)
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot $Path), $Content, $Utf8)
}

$Required = @("feature_list.json", "README.md", "progress/current.md", "progress/history.md")
$missing = $Required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }
if ($missing) {
    foreach ($file in $missing) { Write-Fail "Falta un archivo de la plantilla: $file" }
    exit 1
}

Write-Host "-- Instanciando proyecto '$Name' ----------------------"

# 1. feature_list.json -------------------------------------------------------
# Se reescribe con Python, no con ConvertTo-Json: PowerShell serializa con una
# indentación extraña y escapa los `<` de los placeholders como <, y este
# archivo lo leen humanos y agentes en cada sesión.
$py = $null
foreach ($candidate in @("python", "py", "python3")) {
    if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
    $probe = & $candidate -c "print('PYOK')" 2>$null
    if ($LASTEXITCODE -eq 0 -and ([string]$probe).Trim() -eq "PYOK") { $py = $candidate; break }
}

if (-not $py) {
    Write-Fail "No se encontró un Python ejecutable: el arnés lo necesita (ver docs/scripts.md)"
    exit 1
}

if ($PSCmdlet.ShouldProcess("feature_list.json", "escribir project/description y vaciar features")) {
    # sys.argv[2] puede no llegar: PowerShell 5.1 descarta los argumentos vacíos
    # al invocar un ejecutable nativo, así que -Description sin valor no viaja.
    $rewrite = "import json,sys;p='feature_list.json';d=json.load(open(p,encoding='utf-8'));d['project']=sys.argv[1];d['description']=(sys.argv[2] if len(sys.argv)>2 else '') or d.get('description','');d['features']=[];open(p,'w',encoding='utf-8',newline=chr(10)).write(json.dumps(d,indent=2,ensure_ascii=False)+chr(10))"
    & $py -c $rewrite $Name $Description
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "No se pudo reescribir feature_list.json"
        exit 1
    }
    Write-Ok "feature_list.json -> project '$Name', 0 features"
}

# 2. Placeholders en la documentación ---------------------------------------
# Lista explícita a propósito: `docs/scripts.md` y `CHECKPOINTS.md` *hablan* de
# los placeholders, así que sustituirlos ahí destrozaría su documentación.
$placeholderFiles = @(
    "README.md",
    "docs/architecture.md",
    "docs/conventions.md",
    "docs/verification.md"
) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Get-Item

foreach ($file in $placeholderFiles) {
    $relative = (Resolve-Path -LiteralPath $file.FullName -Relative) -replace "^\.\\", "" -replace "\\", "/"
    $content = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
    $updated = $content.Replace("<TU_PROYECTO>", $Name)
    if ($Description) { $updated = $updated.Replace("<DESCRIPCION_PROYECTO>", $Description) }
    if ($updated -eq $content) { continue }
    if ($PSCmdlet.ShouldProcess($relative, "sustituir placeholders")) {
        [System.IO.File]::WriteAllText($file.FullName, $updated, $Utf8)
        Write-Ok "$relative -> placeholders sustituidos"
    }
}

# 3. Reset de progress/ ------------------------------------------------------
$currentTemplate = @"
# Sesión actual

> Este archivo se vacía al cerrar cada sesión y se mueve a ``history.md``.
> Mientras trabajas, **mantenlo actualizado en tiempo real**, no al final.

- **Feature en curso:** _ninguna_
- **Inicio:** _—_
- **Agente:** _—_

## Plan

_Describe en 3-5 bullets qué vas a hacer antes de tocar código._

## Bitácora

_Anota aquí cada paso significativo: archivos creados, decisiones, bloqueos._

- ...

## Próximo paso

_Si la sesión se interrumpe, lo primero que debe hacer la siguiente sesión._
"@

$historyTemplate = @"
# Historial de sesiones

> Bitácora **append-only**. Al cerrar cada sesión se añade al final el resumen
> que vivía en ``progress/current.md``. Nunca se edita ni se borra una entrada
> anterior: este archivo es la memoria del proyecto entre context windows.

Formato de cada entrada:

``````markdown
## <YYYY-MM-DD> — feature <id> <name>

- **Agente:** <quién trabajó>
- **Resultado:** done | blocked
- **Archivos tocados:** <lista>
- **Verificación:** <salida resumida de init>
- **Notas:** <decisiones o bloqueos relevantes para la siguiente sesión>
``````

---

_Sin sesiones registradas todavía._
"@

$historyContent = Get-Content -LiteralPath "progress/history.md" -Raw -Encoding UTF8
$hasHistory = $historyContent -notmatch "Sin sesiones registradas todavía"

if ($hasHistory -and -not $Force) {
    Write-Warn "progress/history.md tiene entradas de sesiones anteriores. Usa -Force para reiniciarlo."
} elseif ($PSCmdlet.ShouldProcess("progress/history.md", "reiniciar a la plantilla")) {
    Set-Utf8File "progress/history.md" ($historyTemplate + "`n")
    Write-Ok "progress/history.md -> reiniciado"
}

if ($PSCmdlet.ShouldProcess("progress/current.md", "reiniciar a la plantilla")) {
    Set-Utf8File "progress/current.md" ($currentTemplate + "`n")
    Write-Ok "progress/current.md -> reiniciado"
}

# 4. Informes residuales ----------------------------------------------------
$reports = Get-ChildItem -Path "progress" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "^(explore|impl|review|intake)_.*\.md$" }

foreach ($report in $reports) {
    if ($PSCmdlet.ShouldProcess("progress/$($report.Name)", "borrar informe de una sesión anterior")) {
        Remove-Item -LiteralPath $report.FullName -Force
        Write-Ok "progress/$($report.Name) -> borrado"
    }
}

# 4bis. Requisitos ---------------------------------------------------------
# Los requisitos son del proyecto anterior. Si se quedan, el paso 1 vacía
# `features` y quedan specs aprobados sin ninguna feature que los referencie:
# la sección 5 del verificador sale en rojo apenas termina el bootstrap.
if (-not (Test-Path -LiteralPath "specs" -PathType Container)) {
    if ($PSCmdlet.ShouldProcess("specs/", "crear la carpeta de requisitos")) {
        New-Item -ItemType Directory -Path "specs" | Out-Null
        Write-Ok "specs/ -> creada"
    }
}

$oldSpecs = Get-ChildItem -Path "specs" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "^REQ-\d{3}_.*\.md$" }

foreach ($spec in $oldSpecs) {
    if ($PSCmdlet.ShouldProcess("specs/$($spec.Name)", "borrar requisito del proyecto anterior")) {
        Remove-Item -LiteralPath $spec.FullName -Force
        Write-Ok "specs/$($spec.Name) -> borrado"
    }
}

# 5. Repositorio git -------------------------------------------------------
# Dos motivos para tocar esto aquí:
#  - El reviewer identifica los archivos tocados en la sesión comparando contra
#    el historial. Sin repo trabaja a ciegas.
#  - Si clonaste el template, `origin` sigue apuntando a la plantilla y tu primer
#    push mandaría el proyecto nuevo al repo del template.
$gitNote = $null

if ($NoGit) {
    Write-Warn "git: omitido por -NoGit (recuerda que el reviewer compara contra el historial)"
} elseif (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warn "git no está instalado: el reviewer no podrá comparar contra el historial"
} else {
    $hasGit = Test-Path -LiteralPath ".git"

    if ($hasGit -and $ResetGit) {
        if ($PSCmdlet.ShouldProcess(".git", "borrar el historial heredado de la plantilla")) {
            Remove-Item -LiteralPath ".git" -Recurse -Force
            Write-Ok ".git heredado de la plantilla -> borrado"
            $hasGit = $false
        }
    }

    if (-not $hasGit) {
        if ($PSCmdlet.ShouldProcess("el directorio actual", "inicializar un repositorio git")) {
            git init --quiet
            git add -A
            # Identidad solo si el entorno no la tiene: no sobrescribimos la del usuario.
            if (-not (git config user.email)) {
                git config user.email "harness@localhost"
                git config user.name "Harness bootstrap"
                Write-Warn "git: no había identidad configurada, se puso una local provisional"
            }
            git commit --quiet -m "chore: instancia el arnés para $Name"
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "git: repositorio inicializado con el commit base del arnés"
            } else {
                Write-Warn "git: el commit base falló; hazlo a mano antes de trabajar"
            }
        }
    } else {
        # Repo preexistente: lo que importa es que `origin` no apunte al template.
        $origin = (git remote get-url origin 2>$null)
        if ($origin -and $origin -match "Harness_Basic_Template") {
            if ($PSCmdlet.ShouldProcess("remote origin", "desconectar el remote de la plantilla")) {
                git remote remove origin
                Write-Ok "git: remote 'origin' apuntaba a la PLANTILLA -> desconectado"
                $gitNote = "Añade el remote de tu proyecto: git remote add origin <url>"
            }
        } elseif ($origin) {
            Write-Ok "git: remote 'origin' -> $origin (no es la plantilla, se deja como está)"
        } else {
            Write-Ok "git: repositorio existente sin remote, nada que desconectar"
        }

        if ((git log --oneline -1 2>$null) -and -not $ResetGit) {
            Write-Warn "git: conservas el historial de la plantilla. Usa -ResetGit si querías empezar de cero."
        }
    }
}

# Checklist final -----------------------------------------------------------
Write-Host ""
Write-Host "-- Siguiente paso (a mano) ----------------------------"
Write-Host "  1. Abre Claude Code en la raíz y pásale tus requisitos en lenguaje normal"
Write-Host "     (o usa /requisitos). El analyst los deja en specs/ y redacta un"
Write-Host "     borrador de docs/architecture.md."
Write-Host "  2. Léelos y pídele los cambios que hagan falta: cada vuelta es una ronda."
Write-Host "  3. Cuando estés conforme: /aprobar-requisitos. Ahí las features pasan a"
Write-Host "     pending y se aprueba la arquitectura."
Write-Host "  4. Ejecuta ./init.ps1 — debe quedar verde."
Write-Host "  5. /next-feature para arrancar el desarrollo."
if ($gitNote) {
    Write-Host "  6. $gitNote"
}
Write-Host ""
Write-Ok "Proyecto '$Name' instanciado."

exit 0
