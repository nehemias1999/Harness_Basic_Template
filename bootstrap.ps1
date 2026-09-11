<#
.SYNOPSIS
    Instantiates a new project from this harness template (Windows).

.DESCRIPTION
    Fills in the template's placeholders and leaves the repository in a
    "project just started" state:

      1. `feature_list.json` -> writes project/description and empties `features`.
      2. Replaces `<YOUR_PROJECT>` and `<PROJECT_DESCRIPTION>` in README.md and
         in docs/architecture.md, conventions.md and verification.md.
      3. Resets `progress/current.md` and `progress/history.md` to their template.
      4. Deletes previous sessions' reports (`progress/explore_*.md`,
         `impl_*.md`, `review_*.md`, `intake_*.md`) if any are left.
      5. Creates `specs/` and deletes the previous project's requirements
         (`specs/REQ-*.md`), which no longer have features to point at.
      6. Leaves the git repository ready with two remotes: `origin` (yours)
         and `template` (the harness).

    A human runs it ONCE. **It is not on the agent's allow list**:
    instantiating empties the scope and deletes the requirements, and that
    decision is yours. On a repository that is already a project it refuses and
    demands `-Force`.

    This script is a wrapper around `scripts/instantiate.py`, just like
    `bootstrap.sh`. The logic lives there for the same reason the validators'
    does: duplicating 200 lines of decisions about what to delete in two
    dialects guarantees that one day they will say different things.

    What it does NOT do: define the scope for you. The draft of
    `docs/architecture.md` and the requirements are written by the `analyst`
    agent (`/requirements`), but **approving them is yours** and until you do
    the verifier does not go green.

.PARAMETER Name
    Name of the new project (required).

.PARAMETER Description
    One line describing the project. If omitted, the placeholder stays.

.PARAMETER Repo
    URL of YOUR project's repository. It becomes `origin`; the URL the clone
    came from is kept as `template`, which is what lets you reset this folder
    later for the next project. Passing the template's own URL is refused.

.PARAMETER TemplateRepo
    URL of the harness's repository. Only needed when it cannot be worked out
    from the current `origin` (you copied the template instead of cloning it).

.PARAMETER Force
    Instantiate even if the repository is already a project, and reset
    `progress/history.md` even if it has entries.

.PARAMETER ResetGit
    Delete the `.git` inherited from the template and start a new history.
    Use it when you CLONED the template: without this you keep its commits.

.PARAMETER NoGit
    Do not touch git at all. For when you manage the repository by hand.

.PARAMETER WhatIf
    List the changes without applying them.

.EXAMPLE
    ./bootstrap.ps1 -Name "my-project" -WhatIf

.EXAMPLE
    ./bootstrap.ps1 -Name "my-project" -ResetGit

.EXAMPLE
    ./bootstrap.ps1 -Name "my-project" -Description "Daily ingestion pipeline." -Repo "https://github.com/me/my-project.git"

.OUTPUTS
    [OK] / [WARN] lines per change applied, and a closing checklist.

.NOTES
    Exit codes: 0 instantiated · 1 files missing, or already a project.
    After running it, validate with ./init.ps1.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [string]$Description = "",

    [string]$Repo = "",

    [string]$TemplateRepo = "",

    [switch]$Force,

    [switch]$ResetGit,

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

$Arguments = @("scripts/instantiate.py", "--name", $Name)
if ($Description)  { $Arguments += @("--description", $Description) }
if ($Repo)         { $Arguments += @("--repo", $Repo) }
if ($TemplateRepo) { $Arguments += @("--template-repo", $TemplateRepo) }
if ($Force)       { $Arguments += "--force" }
if ($ResetGit)    { $Arguments += "--reset-git" }
if ($NoGit)       { $Arguments += "--no-git" }
if ($WhatIf)      { $Arguments += "--dry-run" }

& $Py @Arguments
exit $LASTEXITCODE
