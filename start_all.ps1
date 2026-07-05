# ============================================================
#  Groundhog -- Start All Services
#  Run from the repo root:  .\start_all.ps1
# ============================================================

$root = $PSScriptRoot

Write-Host ""
Write-Host "  Groundhog -- Starting All Services" -ForegroundColor Cyan
Write-Host "  ====================================" -ForegroundColor Cyan
Write-Host ""

# 1. Cognee Memory Server (start first -- others depend on it)
Write-Host "  Starting [1] Cognee Memory Server :8010 ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$root'; .\venv\Scripts\activate; python main.py"

Write-Host "  Waiting 5s for Cognee to initialise..." -ForegroundColor DarkGray
Start-Sleep -Seconds 5

# 2. Backend Gateway
Write-Host "  Starting [2] Backend Gateway :8000 ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$root\backend'; ..\venv\Scripts\activate; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Seconds 2

# 3. MCP Server
Write-Host "  Starting [3] MCP Server :8002 ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$root'; .\venv\Scripts\activate; python -m uvicorn mcp_server.main:app --host 0.0.0.0 --port 8002 --reload"

Start-Sleep -Seconds 1

# 4. Frontend (Vite)
Write-Host "  Starting [4] Frontend :5173 ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$root\frontend'; npm run dev"

Write-Host ""
Write-Host "  All services launched!" -ForegroundColor Green
Write-Host ""
Write-Host "  Service            URL" -ForegroundColor White
Write-Host "  -----------------  --------------------------" -ForegroundColor DarkGray
Write-Host "  Cognee Memory      http://localhost:8010/docs" -ForegroundColor Cyan
Write-Host "  Backend Gateway    http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  MCP Server         http://localhost:8002/sse" -ForegroundColor Cyan
Write-Host "  Frontend           http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  MCP endpoint for Claude/Cursor/Antigravity:" -ForegroundColor White
Write-Host "    http://localhost:8002/sse" -ForegroundColor Yellow
Write-Host ""
Write-Host "  To stop: close each of the 4 terminal windows." -ForegroundColor DarkGray
Write-Host ""
