# dev.ps1 — Start ParleyLab dev servers cleanly
# Usage: .\dev.ps1
# Kills anything on ports 8000 / 3000, then starts both servers in new windows.

$ProjectRoot = $PSScriptRoot

function Kill-Port($port) {
    $pids = (netstat -ano | Select-String ":$port\s") |
        ForEach-Object { ($_ -split '\s+')[-1] } |
        Sort-Object -Unique |
        Where-Object { $_ -match '^\d+$' -and $_ -ne '0' }
    foreach ($p in $pids) {
        try { taskkill /PID $p /F 2>$null | Out-Null } catch {}
    }
}

Write-Host "Stopping any existing servers..." -ForegroundColor Cyan
Kill-Port 8000
Kill-Port 3000
Start-Sleep -Seconds 1

Write-Host "Starting FastAPI backend (port 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "Set-Location '$ProjectRoot\backend'; python -m uvicorn main:app --port 8000 --reload"

Start-Sleep -Seconds 2

Write-Host "Starting Next.js frontend (port 3000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "Set-Location '$ProjectRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "Both servers starting in separate windows." -ForegroundColor Cyan
Write-Host "Backend:  http://localhost:8000/healthz" -ForegroundColor White
Write-Host "Frontend: http://localhost:3000" -ForegroundColor White
