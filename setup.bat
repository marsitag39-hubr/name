@echo off
setlocal
cd /d "%~dp0"

echo === Preparando Sistema de Turnos ===

if not exist "backend\.venv\Scripts\python.exe" (
  echo Creando entorno de Python...
  py -3 -m venv backend\.venv 2>nul
  if errorlevel 1 python -m venv backend\.venv
  if errorlevel 1 goto python_error
) else (
  backend\.venv\Scripts\python.exe --version >nul 2>&1
  if errorlevel 1 (
    echo Reparando entorno de Python incompleto...
    rmdir /s /q backend\.venv
    py -3 -m venv backend\.venv 2>nul
    if errorlevel 1 python -m venv backend\.venv
    if errorlevel 1 goto python_error
  )
)

echo Instalando paquetes de Python...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto pip_error
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 goto pip_error

echo Instalando paquetes de Angular...
pushd frontend
call npm install
if errorlevel 1 (
  popd
  goto npm_error
)
popd

echo.
echo Preparacion completa.
exit /b 0

:python_error
echo.
echo ERROR: No se encontro Python. Instala Python 3.10 o posterior y activa "Add Python to PATH".
echo Descarga: https://www.python.org/downloads/
exit /b 1

:pip_error
echo.
echo ERROR: No se pudieron instalar los paquetes Python. Revisa tu conexion a internet e intenta setup.bat de nuevo.
exit /b 1

:npm_error
echo.
echo ERROR: No se pudieron instalar paquetes Angular. Confirma Node.js 24.x y tu conexion a internet.
echo Descarga: https://nodejs.org/
exit /b 1
