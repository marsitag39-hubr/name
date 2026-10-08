@echo off
setlocal
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\uvicorn.exe" goto setup
if not exist "frontend\node_modules\@angular\cli\bin\ng.js" goto setup
goto launch

:setup
call setup.bat
if errorlevel 1 (
  pause
  exit /b 1
)

:launch
echo Iniciando backend y Angular...
start "Turnos - Backend Python" "%~dp0run-backend.bat"
start "Turnos - Frontend Angular" "%~dp0run-frontend.bat"
echo Esperando que Angular arranque...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$limit=(Get-Date).AddSeconds(90); do { if (Test-NetConnection 127.0.0.1 -Port 4200 -InformationLevel Quiet) { Start-Process 'http://localhost:4200'; exit 0 }; Start-Sleep -Seconds 2 } while ((Get-Date) -lt $limit); Write-Host 'Angular tarda mas de lo esperado. Revisa su ventana de terminal.'"
echo.
echo Panel: http://localhost:4200
echo Pantalla publica: http://localhost:4200/display
echo Mantén abiertas las ventanas de backend y frontend. Ctrl+C en cada una para detenerlas.
