@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Traductor de PDF

echo.
echo  ============================================
echo   Traductor de PDF - inicio
echo  ============================================
echo.

python -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo  No se encontro Python.
  echo.
  echo  Instala Python 3.10 o superior desde:
  echo    https://www.python.org/downloads/
  echo  Durante la instalacion marca "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  Creando el entorno virtual la primera vez...
  python -m venv .venv
  if errorlevel 1 goto :error
)

set "PY=.venv\Scripts\python.exe"

"%PY%" -c "import flask, pymupdf, requests" >nul 2>nul
if errorlevel 1 (
  echo  Instalando dependencias la primera vez...
  "%PY%" -m pip install --disable-pip-version-check --quiet -r requirements.txt
  if errorlevel 1 goto :error
) else (
  echo  Dependencias listas.
)

echo.
echo  Iniciando el servidor local. No cierres esta ventana.
echo.
"%PY%" app.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo  Ocurrio un error. Revisa los mensajes de arriba.
echo.
pause
exit /b 1
