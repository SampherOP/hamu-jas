@echo off
setlocal EnableExtensions
title HAMU-GPT - website build
cd /d "%~dp0"

echo.
echo   ========================================================
echo     HAMU-GPT   -   website build
echo     (wahi app jo HAMU-GPT.exe hai, magar Chrome ke liye)
echo   ========================================================
echo.

rem ------------------------------------------------------------------
rem  1. Python dhoondo
rem ------------------------------------------------------------------
set "PY="
set "MANAGED=C:\Users\Amanat 777\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe"

if exist "%MANAGED%" set "PY=%MANAGED%"
if defined PY goto havepy

where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto havepy

where py >nul 2>nul
if not errorlevel 1 set "PY=py"
if defined PY goto havepy

echo   [X] Is PC pe Python nahi mila.
echo.
echo       Install karo:  https://www.python.org/downloads/
echo       Install karte waqt  "Add python.exe to PATH"  tick karna.
echo.
pause
exit /b 1

:havepy
rem sach me chalta hai? (Microsoft Store ka stub nahi)
"%PY%" -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo   [X] "%PY%" chal nahi raha.
  echo.
  echo       Python theek se install karo, phir dobara try karo.
  echo.
  pause
  exit /b 1
)

rem ------------------------------------------------------------------
rem  2. saari files yahin honi chahiye
rem ------------------------------------------------------------------
set "MISSING="
for %%F in (nexus_app.py auth.py store.py ads.py providers.py tools.py verify.py wsgi.py vercel.json) do (
  if not exist "%%F" set "MISSING=%%F"
)
if not exist "ui\index.html" set "MISSING=ui\index.html"
if not exist "ui\logo.png"   set "MISSING=ui\logo.png"

if defined MISSING (
  echo   [X] Yeh file missing hai:  %MISSING%
  echo.
  echo       Poora folder chahiye. Sirf index.html se kaam nahi chalega -
  echo       accounts, providers aur chat sab Python files se aate hain.
  echo.
  pause
  exit /b 1
)

rem ------------------------------------------------------------------
rem  3. chalao
rem ------------------------------------------------------------------
echo   Python :  %PY%
echo   Folder :  %CD%
echo.
echo   Server start ho raha hai...
echo   Browser khud khul jayega. Band karne ke liye is window me Ctrl+C.
echo.

"%PY%" nexus_app.py --web --open

echo.
echo   Server band ho gaya.
echo.
pause
endlocal
