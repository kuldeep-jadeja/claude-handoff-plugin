# Install the handoff skills and hooks for Kiro (Windows PowerShell).
#
#   irm https://raw.githubusercontent.com/kuldeep-jadeja/claude-handoff-plugin/main/kiro/install.ps1 | iex
#   & ([scriptblock]::Create((irm .../kiro/install.ps1))) -Project      also add the hooks to this project
#   & ([scriptblock]::Create((irm .../kiro/install.ps1))) -Uninstall    remove everything it installed
#
# Writes only these files:
#   ~\.kiro\handoff\handoff.py                 the hook script (Python 3, standard library only)
#   ~\.kiro\skills\handoff, handoff-resume, handoff-list
#   ~\.kiro\hooks\handoff.json                 global hooks (Kiro CLI)
#   .\.kiro\hooks\handoff.json                 project hooks, only with -Project (Kiro IDE)
param([switch]$Project, [switch]$Uninstall)
$ErrorActionPreference = "Stop"

$Raw = if ($env:HANDOFF_RAW) { $env:HANDOFF_RAW } else { "https://raw.githubusercontent.com/kuldeep-jadeja/claude-handoff-plugin/main" }
$Kiro = if ($env:KIRO_HOME) { $env:KIRO_HOME } else { Join-Path $HOME ".kiro" }
$Skills = @("handoff", "handoff-resume", "handoff-list")

if ($Uninstall) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Kiro "handoff")
    foreach ($s in $Skills) { Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Kiro "skills\$s") }
    Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $Kiro "hooks\handoff.json")
    if (Test-Path ".kiro\hooks\handoff.json") {
        Remove-Item -Force ".kiro\hooks\handoff.json"
        Write-Host "Removed .kiro\hooks\handoff.json from this project."
    }
    Write-Host "Handoff removed from $Kiro. Saved handoffs in knowledge\handoffs\ were left alone."
    return
}

$Py = $null
foreach ($candidate in @("python3", "python", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c "import sys; sys.exit(sys.version_info < (3, 6))" 2>$null
        if ($LASTEXITCODE -eq 0) { $Py = $candidate; break }
    }
}
if (-not $Py) {
    Write-Error "Python 3 is needed for the hooks. Install it from python.org (tick 'Add python.exe to PATH'), then run this again."
}

# Use the files next to this script when run from a clone, otherwise download them.
$Here = $null
if ($PSScriptRoot) {
    $candidate = Split-Path -Parent $PSScriptRoot
    if (Test-Path (Join-Path $candidate "scripts\handoff.py")) { $Here = $candidate }
}
function Fetch($RepoPath, $Destination) {
    New-Item -ItemType Directory -Force (Split-Path -Parent $Destination) | Out-Null
    if ($Here) { Copy-Item (Join-Path $Here $RepoPath) $Destination -Force }
    else { Invoke-WebRequest "$Raw/$RepoPath" -OutFile $Destination -UseBasicParsing }
}

$Script = Join-Path $Kiro "handoff\handoff.py"
Fetch "scripts/handoff.py" $Script
foreach ($s in $Skills) { Fetch "kiro/skills/$s/SKILL.md" (Join-Path $Kiro "skills\$s\SKILL.md") }

function Write-Hooks($Destination) {
    function Cmd($Mode) { "$Py -I `"$Script`" --client kiro $Mode" }
    $hooks = [ordered]@{
        version = "v1"
        hooks = @(
            [ordered]@{ name = "handoff-load"; description = "Load the last handoff into the new session"
                trigger = "SessionStart"; action = [ordered]@{ type = "command"; command = (Cmd "start") }; timeout = 10 },
            [ordered]@{ name = "handoff-remember-prompt"; description = "Remember the prompt (redacted) for the automatic snapshot"
                trigger = "UserPromptSubmit"; action = [ordered]@{ type = "command"; command = (Cmd "prompt") }; timeout = 10 },
            [ordered]@{ name = "handoff-snapshot"; description = "Write knowledge/handoffs/AUTO.md when the agent stops"
                trigger = "Stop"; action = [ordered]@{ type = "command"; command = (Cmd "stop") }; timeout = 10 }
        )
    }
    New-Item -ItemType Directory -Force (Split-Path -Parent $Destination) | Out-Null
    $json = $hooks | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($Destination, $json + "`n", (New-Object System.Text.UTF8Encoding $false))
}

Write-Hooks (Join-Path $Kiro "hooks\handoff.json")
Write-Host "Installed the handoff skills and hooks in $Kiro."
if ($Project) {
    Write-Hooks (Join-Path (Get-Location) ".kiro\hooks\handoff.json")
    Write-Host "Added .kiro\hooks\handoff.json to $(Get-Location)."
} else {
    Write-Host "Kiro IDE: run this again with -Project inside each project to add the hooks there."
}
Write-Host 'Restart Kiro or open a new chat. Say "handoff" to save, "resume" to pick up.'
