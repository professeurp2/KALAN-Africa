@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Kalan en une commande (Windows). Premiere fois : installe tout, avec Internet.
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\.kalan-installe" (
  echo Premiere installation de Kalan : quelques minutes, Internet requis...
  if not exist ".venv\Scripts\python.exe" python -m venv .venv || goto :erreur
  ".venv\Scripts\python" -m pip install --upgrade pip || goto :erreur
  ".venv\Scripts\python" -m pip install -r requirements.txt || goto :erreur
  echo ok> ".venv\.kalan-installe"
)
".venv\Scripts\python" -m kalan.lancer %*
exit /b %errorlevel%

:erreur
echo.
echo L'installation a echoue. Verifier la connexion Internet et que Python 3.12 est installe, puis relancer kalan.
exit /b 1
