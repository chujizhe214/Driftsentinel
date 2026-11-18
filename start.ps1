param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Please install Python 3.11+.' }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Please install Node.js 22.12+.' }
    $pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create Python virtual environment.' }
    }
    & $pythonPath -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    if (-not (Test-Path -LiteralPath 'node_modules')) {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    Write-Host "`nDriftSentinel: http://127.0.0.1:$Port" -ForegroundColor Green
    Write-Host 'Keep this window open. Press Ctrl+C to stop.'
    & $pythonPath -m uvicorn backend.app:app --host 127.0.0.1 --port $Port
} catch {
    Write-Host $_ -ForegroundColor Red
    exit 1
}
