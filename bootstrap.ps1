<#
.SYNOPSIS
    Instancia un proyecto nuevo a partir de esta plantilla de arnés (Windows).

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
      6. Deja el repositorio git listo y desconecta el `origin` heredado.

    Lo ejecuta un humano UNA vez. **No está en la lista de permisos del
    agente**: instanciar vacía el alcance y borra los requisitos, y esa
    decisión es tuya. Sobre un repositorio que ya es un proyecto se planta y
    exige `-Force`.

    Este script es un wrapper de `scripts/instanciar.py`, igual que
    `bootstrap.sh`. La lógica vive allí por el mismo motivo que la de los
    validadores: duplicar 200 líneas de decisiones sobre qué borrar en dos
    dialectos garantiza que un día digan cosas distintas.

    Lo que NO hace: definir el alcance por ti. El borrador de
    `docs/architecture.md` y los requisitos los redacta el agente `analyst`
    (`/requisitos`), pero **aprobarlos es tuyo** y hasta que lo hagas el
    verificador no se pone verde.

.PARAMETER Name
    Nombre del proyecto nuevo (obligatorio).

.PARAMETER Description
    Una línea describiendo el proyecto. Si se omite, deja el placeholder.

.PARAMETER Force
    Instancia aunque el repositorio ya sea un proyecto, y reinicia
    `progress/history.md` aunque tenga entradas.

.PARAMETER ResetGit
    Borra el `.git` heredado de la plantilla y empieza un historial nuevo.
    Úsalo cuando hayas CLONADO el template: sin esto te quedas con sus commits.

.PARAMETER NoGit
    No toca git en absoluto. Para cuando gestionas el repositorio a mano.

.PARAMETER WhatIf
    Lista los cambios sin aplicarlos.

.EXAMPLE
    ./bootstrap.ps1 -Name "mi-proyecto" -WhatIf

.EXAMPLE
    ./bootstrap.ps1 -Name "mi-proyecto" -ResetGit

.EXAMPLE
    ./bootstrap.ps1 -Name "mi-proyecto" -Description "Pipeline de ingesta diaria."

.OUTPUTS
    Líneas [OK] / [WARN] por cada cambio aplicado, y una checklist final.

.NOTES
    Exit codes: 0 instanciado · 1 faltan archivos, o ya era un proyecto.
    Después de ejecutarlo, valida con ./init.ps1.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [string]$Description = "",

    [switch]$Force,

    [switch]$ResetGit,

    [switch]$NoGit,

    [switch]$WhatIf
)

Set-Location -Path $PSScriptRoot

# Mismo sondeo que init.ps1: hay que descartar los stubs que existen en el PATH
# pero no ejecutan nada (el alias `python3` de la Microsoft Store, por ejemplo).
$Py = $null
foreach ($candidate in @("python", "py", "python3")) {
    if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
    $probe = & $candidate -c "print('PYOK')" 2>$null
    if ($LASTEXITCODE -eq 0 -and ([string]$probe).Trim() -eq "PYOK") { $Py = $candidate; break }
}

if (-not $Py) {
    Write-Host "[FAIL]  No se encontró un Python ejecutable: el arnés lo necesita (ver docs/scripts.md)" -ForegroundColor Red
    exit 1
}

$Argumentos = @("scripts/instanciar.py", "--name", $Name)
if ($Description) { $Argumentos += @("--description", $Description) }
if ($Force)       { $Argumentos += "--force" }
if ($ResetGit)    { $Argumentos += "--reset-git" }
if ($NoGit)       { $Argumentos += "--no-git" }
if ($WhatIf)      { $Argumentos += "--dry-run" }

& $Py @Argumentos
exit $LASTEXITCODE
