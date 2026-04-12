# ZeusOpen v2 — One-click start script for Windows
# Usage: .\start.ps1 [-Port 8234] [-Build]

param(
    [int]$Port = 8234,
    [switch]$Build
)

Write-Host "🚀 ZeusOpen v2 launcher" -ForegroundColor Cyan
Write-Host "   Port: $Port"

# Ensure Python >= 3.11
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "❌ Python is required but not found." -ForegroundColor Red
    exit 1
}

$pyVersion = & python --version 2>&1
Write-Host "   Python: $pyVersion"

# Install dependencies if missing
try {
    $null = python -c "import fastapi, uvicorn, filelock" 2>$null
} catch {
    Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
    & pip install -r requirements.txt
}

# Docker mode
if ($Build) {
    Write-Host "🐳 Building Docker image..." -ForegroundColor Cyan
    docker build -t zeus-open:v2 .
    Write-Host "🐳 Starting container on port $Port..." -ForegroundColor Cyan
    $cwd = (Get-Location).Path
    docker run --rm -p "${Port}:${Port}" -v "${cwd}:/app" zeus-open:v2 `
        python .zeus/v2/scripts/zeus_server.py --host 0.0.0.0 --port $Port
    exit 0
}

# Native mode
Write-Host "▶ Starting ZeusOpen v2 backend (native)..." -ForegroundColor Green
& python .zeus/v2/scripts/zeus_server.py --port $Port
