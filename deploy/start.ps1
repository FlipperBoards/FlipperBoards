# start.ps1 — starts backend and frontend, then watches GitHub for updates.
# Run from any directory: powershell -ExecutionPolicy Bypass -File deploy\start.ps1
#
# Prerequisites:
#   python + pip in PATH, node/npm in PATH, git in PATH

param(
    [string]$Branch = "main",
    [int]$PollSeconds = 60
)

$RepoDir = (Resolve-Path "$PSScriptRoot\..").Path
$script:Backend  = $null
$script:Frontend = $null

function Write-Log($msg) {
    Write-Host "$(Get-Date -Format 'HH:mm:ss') $msg" -ForegroundColor Cyan
}

function Start-Backend {
    if ($script:Backend -and -not $script:Backend.HasExited) {
        Write-Log "Stopping backend (PID $($script:Backend.Id))..."
        Stop-Process -Id $script:Backend.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep 1
    }
    Write-Log "Starting backend..."
    $script:Backend = Start-Process `
        -FilePath "python" `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" `
        -WorkingDirectory "$RepoDir\backend" `
        -PassThru -NoNewWindow
    Write-Log "Backend running (PID $($script:Backend.Id)) -> http://localhost:8000"
}

function Start-Frontend {
    if ($script:Frontend -and -not $script:Frontend.HasExited) {
        Write-Log "Stopping frontend (PID $($script:Frontend.Id))..."
        Stop-Process -Id $script:Frontend.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep 1
    }
    Write-Log "Starting frontend..."
    $script:Frontend = Start-Process `
        -FilePath "cmd" `
        -ArgumentList "/c", "npm run dev -- --host 0.0.0.0" `
        -WorkingDirectory "$RepoDir\frontend" `
        -PassThru -NoNewWindow
    Write-Log "Frontend running (PID $($script:Frontend.Id)) -> http://localhost:5173"
}

# Clean up child processes when this script exits
$null = Register-EngineEvent PowerShell.Exiting -Action {
    if ($script:Backend  -and -not $script:Backend.HasExited)  { Stop-Process -Id $script:Backend.Id  -Force -EA SilentlyContinue }
    if ($script:Frontend -and -not $script:Frontend.HasExited) { Stop-Process -Id $script:Frontend.Id -Force -EA SilentlyContinue }
}

Set-Location $RepoDir

# Initial start
Start-Backend
Start-Frontend

Write-Log "Watching '$Branch' every ${PollSeconds}s. Press Ctrl+C to stop."

while ($true) {
    Start-Sleep -Seconds $PollSeconds

    # Restart crashed processes without waiting for a git change
    if ($script:Backend  -and $script:Backend.HasExited)  { Write-Log "Backend crashed, restarting...";  Start-Backend }
    if ($script:Frontend -and $script:Frontend.HasExited) { Write-Log "Frontend crashed, restarting..."; Start-Frontend }

    git fetch origin $Branch --quiet 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Log "git fetch failed, skipping check"; continue }

    $local  = git rev-parse HEAD
    $remote = git rev-parse "origin/$Branch"

    if ($local -eq $remote) { continue }

    Write-Log "New commits detected ($($local.Substring(0,7)) -> $($remote.Substring(0,7))), pulling..."
    git pull origin $Branch --ff-only --quiet

    $changed = git diff --name-only $local $remote

    if ($changed -match "backend/requirements") {
        Write-Log "requirements.txt changed, reinstalling Python deps..."
        pip install -q -r "$RepoDir\backend\requirements.txt"
    }
    if ($changed -match "frontend/package") {
        Write-Log "package.json changed, running npm install..."
        npm --prefix "$RepoDir\frontend" install --silent
    }

    Start-Backend
    Start-Frontend
    Write-Log "Update complete — now at $(git rev-parse --short HEAD)."
}
