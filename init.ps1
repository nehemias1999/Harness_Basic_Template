<#
.SYNOPSIS
    Environment verification and setup (Windows / PowerShell).

.DESCRIPTION
    Checks the repository is in a healthy state before working and before
    declaring any feature `done`.

    The agent runs it when STARTING a session, the `Stop` hook (through
    scripts/harness_hook.py) when closing it, and the reviewer before issuing
    its verdict. If it fails, the session does not move on.

    POSIX equivalent: ./init.sh (same output, same exit code).

.PARAMETER Quiet
    Skips the detailed test listing; leaves only the headers and the summary.

.EXAMPLE
    ./init.ps1

.EXAMPLE
    pwsh -File ./init.ps1 -Quiet

.OUTPUTS
    Numbered blocks with [OK] / [WARN] / [FAIL] lines.

.NOTES
    Exit codes: 0 environment ready (warnings do not block) · 1 something to fix.
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

Write-Host "-- 1. Checking the environment ------------------------"

# Python interpreter: accepts any of the usual names and discards the stubs that
# run nothing (the Microsoft Store's `python3` alias exists on PATH but only
# prints an install notice).
$Py = $null
$PyVersion = $null
$PyOk = $false

foreach ($candidate in @("python", "py", "python3")) {
    if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
    # Python strings use single quotes: PowerShell 5.1 eats the double quotes
    # when passing arguments to a native executable.
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
    Write-Fail "No runnable Python found (tried python, py, python3)"
    exit 1
}
Write-Ok "Python -> $Py $PyVersion"

if (-not $PyOk) {
    Write-Fail "Python >= 3.9 is required (found $PyVersion)"
    exit 1
}
Write-Ok "Compatible Python version"

Write-Host ""
Write-Host "-- 2. Checking the harness base files -----------------"

$BaseFiles = @(
    "AGENTS.md",
    "CLAUDE.md",
    "CHECKPOINTS.md",
    "README.md",
    "feature_list.json",
    "progress/current.md",
    "progress/history.md",
    "specs/_req_template.md",
    "docs/architecture.md",
    "docs/conventions.md",
    "docs/verification.md",
    "docs/scripts.md"
)

foreach ($file in $BaseFiles) {
    if (Test-Path -LiteralPath $file -PathType Leaf) {
        Write-Ok "$file exists"
    } else {
        Write-Fail "Base file missing: $file"
        $ExitCode = 1
    }
}

Write-Host ""
Write-Host "-- 3. Checking the project configuration --------------"

# Blocking on purpose: an unconfigured harness has no quality criteria (the
# reviewer judges against docs/architecture.md). See docs/scripts.md.
if (Test-Path -LiteralPath "scripts/validate_project_setup.py" -PathType Leaf) {
    $setup = & $Py "scripts/validate_project_setup.py" "."
    if ($LASTEXITCODE -ne 0) { $ExitCode = 1 }
    $setup | ForEach-Object { Write-Host $_ }
} else {
    Write-Fail "scripts/validate_project_setup.py is missing — cannot check the configuration"
    $ExitCode = 1
}

Write-Host ""
Write-Host "-- 4. Validating feature_list.json --------------------"

# Same validation logic as init.sh: both delegate to the same module so the
# scope rules do not drift apart between platforms.
if (Test-Path -LiteralPath "scripts/validate_feature_list.py" -PathType Leaf) {
    # The output is captured and re-emitted with Write-Host so it stays in order
    # with the rest of the sections (native stdout does not go through the pipeline).
    $validation = & $Py "scripts/validate_feature_list.py" "feature_list.json"
    if ($LASTEXITCODE -ne 0) { $ExitCode = 1 }
    $validation | ForEach-Object { Write-Host $_ }
} else {
    Write-Fail "scripts/validate_feature_list.py is missing — cannot validate the scope"
    $ExitCode = 1
}

Write-Host ""
Write-Host "-- 5. Validating requirements and traceability --------"

# Blocking on purpose: approving a requirement is not a "sure" in the chat, it is
# `status: approved` in specs/ plus the feature in `pending`. The same module
# init.sh uses. See docs/scripts.md.
if (Test-Path -LiteralPath "scripts/validate_requirements.py" -PathType Leaf) {
    $requirements = & $Py "scripts/validate_requirements.py" "."
    if ($LASTEXITCODE -ne 0) { $ExitCode = 1 }
    $requirements | ForEach-Object { Write-Host $_ }
} else {
    Write-Fail "scripts/validate_requirements.py is missing — cannot check traceability"
    $ExitCode = 1
}

Write-Host ""
Write-Host "-- 6. Running tests -----------------------------------"

if (-not (Test-Path -LiteralPath "tests" -PathType Container)) {
    Write-Warn "The tests/ folder does not exist yet"
} else {
    # Count before running: a discover with no tests returns 0 and must not be
    # mistaken for "all green". A freshly instantiated repo warns, it does not fail.
    $count = & $Py -c "import unittest;print(unittest.TestLoader().discover('tests').countTestCases())" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Could not discover the tests (import error in tests/?)"
        $ExitCode = 1
    } elseif ([int]$count -eq 0) {
        Write-Warn "0 tests in tests/ — the harness is not verifying anything yet"
    } else {
        # Neither captured nor redirected: unittest writes its report to stderr and
        # in PowerShell 5.1 a `2>&1` over a native executable wraps every line in an
        # ErrorRecord that prints as "...RemoteException". It is left to write
        # straight to the console and only the exit code is collected.
        if ($Quiet) {
            & $Py -m unittest discover -s tests -q
        } else {
            & $Py -m unittest discover -s tests -v
        }
        $testsExit = $LASTEXITCODE
        if ($testsExit -eq 0) {
            Write-Ok "All tests pass ($count tests)"
        } else {
            Write-Fail "There are broken tests"
            $ExitCode = 1
        }
    }
}

Write-Host ""
Write-Host "-- 7. Summary -----------------------------------------"

if ($ExitCode -eq 0) {
    Write-Ok "Environment ready. You can start working."
} else {
    Write-Fail "Environment NOT ready. Resolve the failures before moving on."
}

exit $ExitCode
