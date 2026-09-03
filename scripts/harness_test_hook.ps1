<#
.SYNOPSIS
    Corre los tests tras cada edición. Lo invoca el hook `PostToolUse`.

.DESCRIPTION
    Feedback inmediato: cada vez que un agente escribe o edita un archivo,
    Claude Code ejecuta este script y le devuelve el resultado de los tests.
    El agente no puede saltárselo.

    Existe como script aparte (en vez de un one-liner en `.claude/settings.json`)
    por un motivo concreto: `python -m unittest discover` sobre una carpeta sin
    tests termina con **exit code 1** ("NO TESTS RAN"), lo que en un proyecto
    recién instanciado haría fallar el hook en cada edición. Aquí se cuenta
    primero y se sale con 0 cuando simplemente no hay nada que ejecutar.

.PARAMETER TestsDir
    Carpeta de tests (por defecto: tests).

.EXAMPLE
    ./scripts/harness_test_hook.ps1

.NOTES
    Exit codes: 0 tests verdes o sin tests todavía · 1 hay tests rotos.
    Verificación completa: ./init.ps1 — ver docs/scripts.md.
#>
[CmdletBinding()]
param(
    [string]$TestsDir = "tests"
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -Path $repoRoot

if (-not (Test-Path -LiteralPath $TestsDir -PathType Container)) {
    Write-Host "[harness] no existe $TestsDir/ — nada que ejecutar"
    exit 0
}

$py = $null
foreach ($candidate in @("python", "py", "python3")) {
    if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
    $probe = & $candidate -c "print('PYOK')" 2>$null
    if ($LASTEXITCODE -eq 0 -and ([string]$probe).Trim() -eq "PYOK") { $py = $candidate; break }
}

if (-not $py) {
    Write-Host "[harness] no se encontró un Python ejecutable"
    exit 0
}

$count = & $py -c "import unittest;print(unittest.TestLoader().discover('$TestsDir').countTestCases())" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[harness] no se pudieron descubrir los tests (¿error de import en $TestsDir/?)"
    exit 1
}

if ([int]$count -eq 0) {
    Write-Host "[harness] 0 tests en $TestsDir/ — todavía no se está verificando nada"
    exit 0
}

# Sin `2>&1`: en PowerShell 5.1 redirigir el stderr de un ejecutable nativo
# envuelve cada línea en un ErrorRecord que se imprime como "RemoteException".
# `-q` ya deja la salida en unas pocas líneas.
& $py -m unittest discover -s $TestsDir -q
$testsExit = $LASTEXITCODE

if ($testsExit -eq 0) {
    Write-Host "[harness] $count tests en verde"
    exit 0
}

Write-Host "[harness] tests ROTOS — arréglalos antes de seguir"
exit 1
