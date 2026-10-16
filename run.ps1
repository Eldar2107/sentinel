# Sentinel — Bir əmrlə işə salma skripti (PowerShell)
# İstifadə: .\run.ps1

param(
    [switch]$Down,
    [switch]$Rebuild,
    [switch]$Logs,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot

function Write-Header {
    param($text)
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║  $text" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Check-Docker {
    try {
        $null = docker info 2>&1
        Write-Host "  ✓ Docker işləyir" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ Docker işləmir. Docker Desktop-u başladın." -ForegroundColor Red
        exit 1
    }
}

# Status
if ($Status) {
    Write-Header "Sentinel — Servis Statusu"
    docker compose -f "$ProjectDir\docker-compose.yml" ps
    exit 0
}

# Logs
if ($Logs) {
    Write-Header "Sentinel — Loglar"
    docker compose -f "$ProjectDir\docker-compose.yml" logs --follow --tail=100
    exit 0
}

# Down
if ($Down) {
    Write-Header "Sentinel — Dayandırılır"
    docker compose -f "$ProjectDir\docker-compose.yml" down -v
    Write-Host "  ✓ Bütün servislər dayandırıldı." -ForegroundColor Green
    exit 0
}

# UP / Rebuild
Write-Header "SENTINEL — Georgia Open Banking Monitor v2.0"
Write-Host "  Başlanır..." -ForegroundColor White
Write-Host ""

Check-Docker

Set-Location $ProjectDir

if ($Rebuild) {
    Write-Host "  → Yenidən build edilir (bu 5-10 dəq. çəkə bilər)..." -ForegroundColor Yellow
    docker compose build --no-cache
} else {
    Write-Host "  → Image-lər yoxlanır..." -ForegroundColor Yellow
    docker compose build
}

Write-Host ""
Write-Host "  → Servislər başladılır..." -ForegroundColor Yellow
docker compose up -d

Write-Host ""
Write-Host "  ⏳ Servislərin hazır olması gözlənilir (30 san.)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Health yoxla
Write-Host ""
Write-Host "  ── Servis Sağlamlığı ──" -ForegroundColor Cyan
$services = @(
    @{Name="Bank A (TBC)"; Url="http://localhost:8001/health"},
    @{Name="Bank B (BoG)"; Url="http://localhost:8002/health"},
    @{Name="Bank C (Liberty)"; Url="http://localhost:8003/health"},
    @{Name="Backend API"; Url="http://localhost:8000/api/health"},
    @{Name="Dashboard"; Url="http://localhost:3000"}
)

foreach ($svc in $services) {
    try {
        $resp = Invoke-WebRequest -Uri $svc.Url -TimeoutSec 5 -UseBasicParsing
        if ($resp.StatusCode -eq 200) {
            Write-Host "  ✓ $($svc.Name)" -ForegroundColor Green
        }
    } catch {
        Write-Host "  ⚠ $($svc.Name) — hələ hazır deyil" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Header "SENTINEL HAZIRDIR!"
Write-Host "  🌐 Dashboard:    http://localhost:3000" -ForegroundColor Cyan
Write-Host "  🔌 Backend API:  http://localhost:8000/api" -ForegroundColor Cyan
Write-Host "  📖 API Docs:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  🏦 Bank A:       http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "  🏦 Bank B:       http://localhost:8002/docs" -ForegroundColor Cyan
Write-Host "  🏦 Bank C:       http://localhost:8003/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Loglar üçün:  .\run.ps1 -Logs" -ForegroundColor Gray
Write-Host "  Status üçün:  .\run.ps1 -Status" -ForegroundColor Gray
Write-Host "  Dayandırmaq:  .\run.ps1 -Down" -ForegroundColor Gray
Write-Host "  Yenidən qur:  .\run.ps1 -Rebuild" -ForegroundColor Gray
Write-Host ""
