<#
.SYNOPSIS
    Returns the workspace to the template and starts another project (Windows).

.DESCRIPTION
    One local copy of the harness, many projects, one after another. When a
    project is finished and pushed to its own repository, this makes the folder
    identical to the template again and instantiates the next project on top.

    The rule, in three sentences: everything git tracked in the previous
    project is deleted; everything in the template's tree is written in its
    place; everything git ignored stays where it is, and is listed at the end
    so you can see what came across.

    It reads the pristine template from the `template` remote, which
    `bootstrap` sets up. Nothing here is deleted until a verified copy of the
    template exists in a temporary folder, so a wrong URL or a network failure
    leaves the current project exactly as it was. Before deleting `.git` it
    writes a bundle of the previous history next to the folder.

    A human runs it. **It is on the agent's `deny` list**: resetting deletes a
    project's working copy, and that decision is yours.

    This script is a wrapper around `scripts/reset_workspace.py`, just like
    `reset.sh`.

.PARAMETER Name
    Name of the new project (required).

.PARAMETER Description
    One line describing the new project.

.PARAMETER Repo
    URL of the new project's repository. It becomes `origin`.

.PARAMETER TemplateRepo
    URL of the harness's repository. Only needed when there is no `template`
    remote yet, or to change it.

.PARAMETER From
    A local copy of the template to restore from, instead of the network.

.PARAMETER Force
    Reset even with uncommitted changes, unpushed commits or stashes.

.PARAMETER CleanIgnored
    Also delete the files git ignores (`.venv/`, `.env`, …).

.PARAMETER NoBundle
    Do not write the backup bundle of the previous history.

.PARAMETER NoGit
    Do not touch git at all. For when you manage the repository by hand.

.PARAMETER WhatIf
    List everything it would delete and keep, and write nothing.

.EXAMPLE
    ./reset.ps1 -Name "ecommerce" -Repo "https://github.com/me/ecommerce.git" -WhatIf

.EXAMPLE
    ./reset.ps1 -Name "ecommerce" -Description "Online store." -Repo "https://github.com/me/ecommerce.git"

.OUTPUTS
    [OK] / [WARN] lines, the list of what survived, and a closing checklist.

.NOTES
    Exit codes: 0 reset (or simulated) · 1 it refused, and nothing was deleted.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [string]$Description = "",

    [string]$Repo = "",

    [string]$TemplateRepo = "",

    [string]$From = "",

    [switch]$Force,

    [switch]$CleanIgnored,

    [switch]$NoBundle,

    [switch]$NoGit,

    [switch]$WhatIf
)

Set-Location -Path $PSScriptRoot

# Same probe as init.ps1: the stubs that exist on PATH but run nothing have to
# be discarded (the Microsoft Store's `python3` alias, for example).
$Py = $null
foreach ($candidate in @("python", "py", "python3")) {
    if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
    $probe = & $candidate -c "print('PYOK')" 2>$null
    if ($LASTEXITCODE -eq 0 -and ([string]$probe).Trim() -eq "PYOK") { $Py = $candidate; break }
}

if (-not $Py) {
    Write-Host "[FAIL]  No runnable Python found: the harness needs it (see docs/scripts.md)" -ForegroundColor Red
    exit 1
}

$Arguments = @("scripts/reset_workspace.py", "--name", $Name)
if ($Description)  { $Arguments += @("--description", $Description) }
if ($Repo)         { $Arguments += @("--repo", $Repo) }
if ($TemplateRepo) { $Arguments += @("--template-repo", $TemplateRepo) }
if ($From)         { $Arguments += @("--from", $From) }
if ($Force)        { $Arguments += "--force" }
if ($CleanIgnored) { $Arguments += "--clean-ignored" }
if ($NoBundle)     { $Arguments += "--no-bundle" }
if ($NoGit)        { $Arguments += "--no-git" }
if ($WhatIf)       { $Arguments += "--dry-run" }

& $Py @Arguments
exit $LASTEXITCODE
