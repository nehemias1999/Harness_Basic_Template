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
         `impl_*.md`, `review_*.md`) si quedara alguno.

    Lo ejecuta un humano UNA vez, justo después de copiar la plantilla. Es
    idempotente: volver a ejecutarlo con otro nombre solo reescribe el nombre.

    Lo que NO hace: escribir `docs/architecture.md` por ti. Ese archivo define
    qué significa "hacer un buen trabajo" en tu proyecto y es lo primero que
    tienes que rellenar a mano; el script te lo recuerda al terminar.

.PARAMETER Name
    Nombre del proyecto nuevo (obligatorio).

.PARAMETER Description
    Una línea describiendo el proyecto. Si se omite, deja el placeholder.

.PARAMETER Force
    No pide confirmación al sobrescribir el historial de `progress/`.

.EXAMPLE
    ./bootstrap.ps1 -Name "mi-proyecto" -WhatIf

.EXAMPLE
    ./bootstrap.ps1 -Name "mi-proyecto" -Description "Pipeline de ingesta diaria."

.OUTPUTS
    Líneas [OK] / [WARN] por cada cambio aplicado, y una checklist final.

.NOTES
    Exit codes: 0 instanciado · 1 faltan archivos de la plantilla.
    Después de ejecutarlo, valida con ./init.ps1 (debe quedar verde).
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Name,

    [string]$Description = "",

    [switch]$Force
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
    $rewrite = "import json,sys;p='feature_list.json';d=json.load(open(p,encoding='utf-8'));d['project']=sys.argv[1];d['description']=sys.argv[2] or d.get('description','');d['features']=[];open(p,'w',encoding='utf-8',newline=chr(10)).write(json.dumps(d,indent=2,ensure_ascii=False)+chr(10))"
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
    Where-Object { $_.Name -match "^(explore|impl|review)_.*\.md$" }

foreach ($report in $reports) {
    if ($PSCmdlet.ShouldProcess("progress/$($report.Name)", "borrar informe de una sesión anterior")) {
        Remove-Item -LiteralPath $report.FullName -Force
        Write-Ok "progress/$($report.Name) -> borrado"
    }
}

# Checklist final -----------------------------------------------------------
Write-Host ""
Write-Host "-- Siguiente paso (a mano) ----------------------------"
Write-Host "  1. Rellena docs/architecture.md: capas, principios y flujo de datos."
Write-Host "  2. Revisa docs/conventions.md y docs/verification.md."
Write-Host "  3. Añade tus primeras features a feature_list.json (usa el bloque _example)."
Write-Host "  4. Ejecuta ./init.ps1 — debe quedar verde."
Write-Host "  5. Pide a Claude Code: <<implementa la siguiente feature pendiente>>."
Write-Host ""
Write-Ok "Proyecto '$Name' instanciado."

exit 0
