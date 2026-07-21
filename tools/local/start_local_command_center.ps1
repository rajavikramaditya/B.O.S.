# M4-A7 - One-command local Command Center start (safe, non-destructive).
param(
    [switch]$ForceKillPort,
    [switch]$SkipDocker,
    [int]$MemoryWaitSeconds = 90
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

$HostAddr = "127.0.0.1"
$Port = 8000
$ComposeFile = Join-Path $Root "docker-compose.memory.yml"

function Write-Info([string]$msg) {
    Write-Host "[orai] $msg" -ForegroundColor Cyan
}

function Write-Warn([string]$msg) {
    Write-Host "[orai] $msg" -ForegroundColor Yellow
}

function Test-PortListening([int]$listenPort) {
    $matches = netstat -ano | Select-String "LISTENING" | Select-String ":$listenPort"
    return [bool]$matches
}

function Get-ListenerPid([int]$listenPort) {
    $matches = netstat -ano | Select-String "LISTENING" | Select-String ":$listenPort"
    foreach ($line in $matches) {
        $text = $line.ToString().Trim()
        if ($text -match '\s(\d+)\s*$') {
            return [int]$Matches[1]
        }
    }
    return $null
}

function Wait-MemoryStack([int]$timeoutSec) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    $format = '{{.State.Health.Status}}'
    while ((Get-Date) -lt $deadline) {
        $pg = & docker inspect --format $format neena-postgres 2>$null
        $rd = & docker inspect --format $format neena-redis 2>$null
        if ($pg -eq "healthy" -and $rd -eq "healthy") {
            return $true
        }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Print-RunningUrls([string]$memoryStatus, [int]$backendPid) {
    Write-Info "Backend already listening on http://${HostAddr}:$Port (PID $backendPid)"
    Write-Info "Command Center URL : http://${HostAddr}:$Port/"
    Write-Info "cockpit-status     : http://${HostAddr}:$Port/api/neena/cockpit-status"
    Write-Info "launch-health      : http://${HostAddr}:$Port/api/neena/launch-health"
    Write-Info "security-status    : http://${HostAddr}:$Port/api/neena/security-status"
    Write-Info "Memory stack       : $memoryStatus"
    Write-Info "Not starting duplicate backend (use -ForceKillPort to replace)."
}

Write-Info "Orai Radio - local Command Center bootstrap"
Write-Info "Project root: $Root"

$memoryStatus = "skipped"
if (-not $SkipDocker) {
    $dockerOk = $false
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            $dockerOk = $true
        }
    }
    catch {
        $dockerOk = $false
    }
    $ErrorActionPreference = $prevEap

    if ($dockerOk) {
        Write-Info "Starting memory stack: docker compose -f docker-compose.memory.yml up -d"
        $ErrorActionPreference = "Continue"
        & docker compose -f $ComposeFile up -d
        $composeExit = $LASTEXITCODE
        $ErrorActionPreference = $prevEap

        if ($composeExit -ne 0) {
            Write-Warn "Docker compose returned non-zero - continuing without memory stack."
            $memoryStatus = "compose_failed"
        }
        else {
            Write-Info "Waiting up to $MemoryWaitSeconds s for Postgres/Redis healthy..."
            if (Wait-MemoryStack -timeoutSec $MemoryWaitSeconds) {
                $memoryStatus = "healthy"
                Write-Info "Memory stack healthy."
            }
            else {
                $memoryStatus = "timeout"
                Write-Warn "Memory stack not healthy yet - run: python tools/local/check_memory_stack.py"
            }
        }
    }
    else {
        $memoryStatus = "docker_offline"
        Write-Warn "Docker engine not running - skipping memory stack."
        Write-Warn "Recovery: start Docker Desktop, then docker compose -f docker-compose.memory.yml up -d"
    }
}
else {
    $memoryStatus = "skipped_flag"
}

$portBusy = Test-PortListening -listenPort $Port
$existingPid = Get-ListenerPid -listenPort $Port

if ($portBusy -or ($null -ne $existingPid)) {
    if ($null -eq $existingPid) {
        $existingPid = 0
    }
    if ($ForceKillPort -and $existingPid -gt 0) {
        Write-Warn "Port $Port in use by PID $existingPid - stopping (owner flag)."
        Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    elseif ($ForceKillPort -and $portBusy) {
        Write-Warn "Port $Port is busy but PID unknown - cannot safely kill. Not starting duplicate backend."
        exit 1
    }
    else {
        Print-RunningUrls -memoryStatus $memoryStatus -backendPid $existingPid
        exit 0
    }
}

Write-Info "Starting backend uvicorn on http://${HostAddr}:$Port ..."
$backendLogOut = Join-Path $Root "runtime\logs\backend_uvicorn.out.log"
$backendLogErr = Join-Path $Root "runtime\logs\backend_uvicorn.err.log"
$proc = Start-Process -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", $HostAddr, "--port", "$Port") `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $backendLogOut `
    -RedirectStandardError $backendLogErr `
    -PassThru `
    -WindowStyle Hidden

Start-Sleep -Seconds 3
if (-not $proc.HasExited) {
    Write-Info "Backend started (PID $($proc.Id))"
}
else {
    Write-Warn "Backend exited early - see $backendLogOut and $backendLogErr"
    exit 1
}

Write-Host ""
Write-Info "Command Center URL : http://${HostAddr}:$Port/"
Write-Info "cockpit-status     : http://${HostAddr}:$Port/api/neena/cockpit-status"
Write-Info "launch-health      : http://${HostAddr}:$Port/api/neena/launch-health"
Write-Info "security-status    : http://${HostAddr}:$Port/api/neena/security-status"
Write-Info "Memory stack       : $memoryStatus"
Write-Info "Backend PID        : $($proc.Id)"
Write-Info "Log files          : $backendLogOut | $backendLogErr"
Write-Host ""
Write-Info "Launch rehearsal: python tools/verify/test_m4_a7_launch_hardening.py"
