param(
    [switch]$Build,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDir
$composeFile = Join-Path $projectDir 'compose.yaml'
$projectUrl = 'http://127.0.0.1:8000'

function Test-DockerReady {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        docker info --format '{{.ServerVersion}}' *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker is not installed. Install Docker Desktop, then run start.bat again.'
    }

    if (-not (Test-DockerReady)) {
        $desktopExe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
        if (-not (Test-Path -LiteralPath $desktopExe)) {
            throw 'Docker is not running. Start Docker Desktop, then run start.bat again.'
        }
        Write-Host 'Starting Docker Desktop. Please wait...' -ForegroundColor Cyan
        Start-Process -FilePath $desktopExe -WindowStyle Hidden
        $deadline = (Get-Date).AddSeconds(180)
        while (-not (Test-DockerReady)) {
            if ((Get-Date) -ge $deadline) {
                throw 'Docker Desktop did not become ready within 180 seconds. Check Docker Desktop and try again.'
            }
            Start-Sleep -Seconds 2
        }
    }

    docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is unavailable. Update Docker Desktop.' }

    docker compose -f $composeFile config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose configuration is invalid.' }

    $container = docker ps --filter 'name=^/DriftSentinel$' --format '{{.Names}}'
    $listeners = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0 -and $container -ne 'DriftSentinel') {
        throw 'Port 8000 is already in use. Stop the local start-local.bat service or the other app using that port, then retry.'
    }

    $images = @(docker image ls --format '{{.Repository}}:{{.Tag}}' driftsentinel:1.0.0)
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect local Docker images.' }
    $imageExists = $images -contains 'driftsentinel:1.0.0'
    if ($Build -or -not $imageExists) {
        Write-Host 'Building DriftSentinel (the first build needs internet access)...' -ForegroundColor Cyan
        docker compose -f $composeFile build
        if ($LASTEXITCODE -ne 0) { throw 'Image build failed. Check the output above and run rebuild.bat to retry.' }
    }

    Write-Host 'Starting DriftSentinel...' -ForegroundColor Cyan
    docker compose -f $composeFile up -d --no-build --wait --wait-timeout 120
    if ($LASTEXITCODE -ne 0) {
        docker compose -f $composeFile logs --tail 50
        throw 'DriftSentinel could not start. Check the container logs above.'
    }

    $health = Invoke-RestMethod -Uri "$projectUrl/api/health" -TimeoutSec 10
    if ($health.status -ne 'ok') { throw 'The application health check failed.' }

    Write-Host "`nDriftSentinel is ready: $projectUrl" -ForegroundColor Green
    Write-Host 'Container: DriftSentinel | Image: driftsentinel:1.0.0'
    Write-Host 'You can close this window. Double-click stop.bat to stop the app.'
    Write-Host 'After changing source code or dependencies, double-click rebuild.bat.'
    if (-not $NoBrowser) {
        $browserUrl = $projectUrl
        if ($Build) {
            # Bypass an entry page cached before cache control was introduced.
            $browserUrl = "$projectUrl/?v=$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
        }
        Start-Process -FilePath $browserUrl
    }
} catch {
    Write-Host "`n$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
