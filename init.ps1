<#
.SYNOPSIS
    Verificación e inicialización del entorno (Windows / PowerShell).

.DESCRIPTION
    Comprueba que el repositorio está en un estado sano antes de trabajar y
    antes de declarar cualquier feature como `done`.

    Lo ejecuta el agente al COMENZAR una sesión, el hook `Stop` (a través de
    scripts/harness_hook.py) al cerrarla y
    el reviewer antes de emitir su veredicto. Si falla, la sesión no avanza.

    Equivalente POSIX: ./init.sh (misma salida y mismo exit code).

.PARAMETER Quiet
    Omite el listado detallado de tests; deja solo los encabezados y el resumen.

.EXAMPLE
    ./init.ps1

.EXAMPLE
    pwsh -File ./init.ps1 -Quiet

.OUTPUTS
    Bloques numerados con líneas [OK] / [WARN] / [FAIL].

.NOTES
    Exit codes: 0 entorno listo (los [WARN] no bloquean) · 1 hay algo que resolver.
#>
[CmdletBinding()]
param(
    [switch]$Quiet
)

Set-Location -Path $PSScriptRoot

function Write-Ok   { param([string]$Message) Write-Host "[OK]    $Message"   -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "[WARN]  $Message"   -ForegroundColor Yellow }
function Write-Fail { param([string]$Message) Write-Host "[FAIL]  $Message"   -ForegroundColor Red }

$ExitCode = 0

Write-Host "-- 1. Verificando entorno -----------------------------"

# Intérprete de Python: acepta cualquiera de los nombres habituales y descarta
# los stubs que no ejecutan nada (el alias `python3` de la Microsoft Store existe
# en el PATH pero solo imprime un aviso de instalación).
$Py = $null
$PyVersion = $null
$PyOk = $false

foreach ($candidate in @("python", "py", "python3")) {
    if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
    # Las cadenas Python van con comillas simples: PowerShell 5.1 se come las
    # comillas dobles al pasar argumentos a un ejecutable nativo.
    $probe = & $candidate -c "import sys;v=sys.version_info;print('PYOK', str(v[0])+'.'+str(v[1])+'.'+str(v[2]), int(v >= (3, 9)))" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $probe) { continue }
    $parts = ([string]$probe).Trim().Split(" ")
    if ($parts[0] -ne "PYOK") { continue }
    $Py = $candidate
    $PyVersion = $parts[1]
    $PyOk = ($parts[2] -eq "1")
    break
}

if (-not $Py) {
    Write-Fail "No se encontró un Python ejecutable (probé python, py, python3)"
    exit 1
}
Write-Ok "Python -> $Py $PyVersion"

if (-not $PyOk) {
    Write-Fail "Se requiere Python >= 3.9 (encontrado $PyVersion)"
    exit 1
}
Write-Ok "Versión de Python compatible"

Write-Host ""
Write-Host "-- 2. Verificando archivos base del arnés -------------"

$BaseFiles = @(
    "AGENTS.md",
    "CLAUDE.md",
    "CHECKPOINTS.md",
    "README.md",
    "feature_list.json",
    "progress/current.md",
    "progress/history.md",
    "specs/_plantilla_req.md",
    "docs/architecture.md",
    "docs/conventions.md",
    "docs/verification.md",
    "docs/scripts.md"
)

foreach ($file in $BaseFiles) {
    if (Test-Path -LiteralPath $file -PathType Leaf) {
        Write-Ok "Existe $file"
    } else {
        Write-Fail "Falta archivo base: $file"
        $ExitCode = 1
    }
}

Write-Host ""
Write-Host "-- 3. Verificando configuración del proyecto ----------"

# Bloqueante a propósito: un arnés sin configurar no tiene criterio de calidad
# (el reviewer juzga contra docs/architecture.md). Ver docs/scripts.md.
if (Test-Path -LiteralPath "scripts/validate_project_setup.py" -PathType Leaf) {
    $setup = & $Py "scripts/validate_project_setup.py" "."
    if ($LASTEXITCODE -ne 0) { $ExitCode = 1 }
    $setup | ForEach-Object { Write-Host $_ }
} else {
    Write-Fail "Falta scripts/validate_project_setup.py — no se puede verificar la configuración"
    $ExitCode = 1
}

Write-Host ""
Write-Host "-- 4. Validando feature_list.json ---------------------"

# Misma lógica de validación que init.sh: ambos delegan en el mismo módulo
# para que las reglas del alcance no se desincronicen entre plataformas.
if (Test-Path -LiteralPath "scripts/validate_feature_list.py" -PathType Leaf) {
    # Se captura la salida y se reemite con Write-Host para que quede en orden
    # respecto al resto de las secciones (stdout nativo no pasa por el pipeline).
    $validation = & $Py "scripts/validate_feature_list.py" "feature_list.json"
    if ($LASTEXITCODE -ne 0) { $ExitCode = 1 }
    $validation | ForEach-Object { Write-Host $_ }
} else {
    Write-Fail "Falta scripts/validate_feature_list.py — no se puede validar el alcance"
    $ExitCode = 1
}

Write-Host ""
Write-Host "-- 5. Validando requisitos y trazabilidad -------------"

# Bloqueante a propósito: la aprobación de un requisito no es un "dale" en el
# chat, es `estado: aprobado` en specs/ mas la feature en `pending`. Este
# módulo lo comprueba igual en Windows y en POSIX. Ver docs/scripts.md.
if (Test-Path -LiteralPath "scripts/validate_requirements.py" -PathType Leaf) {
    $requirements = & $Py "scripts/validate_requirements.py" "."
    if ($LASTEXITCODE -ne 0) { $ExitCode = 1 }
    $requirements | ForEach-Object { Write-Host $_ }
} else {
    Write-Fail "Falta scripts/validate_requirements.py — no se puede verificar la trazabilidad"
    $ExitCode = 1
}

Write-Host ""
Write-Host "-- 6. Ejecutando tests --------------------------------"

if (-not (Test-Path -LiteralPath "tests" -PathType Container)) {
    Write-Warn "La carpeta tests/ no existe todavía"
} else {
    # Contar antes de ejecutar: un discover sin tests devuelve 0 y no debe
    # confundirse con "todo verde". Un repo recién instanciado avisa, no falla.
    $count = & $Py -c "import unittest;print(unittest.TestLoader().discover('tests').countTestCases())" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "No se pudieron descubrir los tests (¿error de import en tests/?)"
        $ExitCode = 1
    } elseif ([int]$count -eq 0) {
        Write-Warn "0 tests en tests/ — el arnés no está verificando nada todavía"
    } else {
        # Sin capturar ni redirigir: unittest escribe su informe por stderr y en
        # PowerShell 5.1 un `2>&1` sobre un ejecutable nativo envuelve cada línea
        # en un ErrorRecord que se imprime como "...RemoteException". Se deja que
        # escriba directo en consola y solo se recoge el exit code.
        if ($Quiet) {
            & $Py -m unittest discover -s tests -q
        } else {
            & $Py -m unittest discover -s tests -v
        }
        $testsExit = $LASTEXITCODE
        if ($testsExit -eq 0) {
            Write-Ok "Todos los tests pasan ($count tests)"
        } else {
            Write-Fail "Hay tests rotos"
            $ExitCode = 1
        }
    }
}

Write-Host ""
Write-Host "-- 7. Resumen -----------------------------------------"

if ($ExitCode -eq 0) {
    Write-Ok "Entorno listo. Puedes empezar a trabajar."
} else {
    Write-Fail "Entorno NO está listo. Resuelve los errores antes de avanzar."
}

exit $ExitCode
