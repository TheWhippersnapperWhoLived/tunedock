@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title Tunedock setup
cd /d "%~dp0"

echo.
echo   ==========================================================
echo     Tunedock setup
echo   ==========================================================
echo     Sets everything up and creates Tunedock.exe for you.
echo     First time: a few minutes. Safe to run again any time.
echo.

echo %~dp0 | findstr /I /C:"\Temp\Temp" >nul
if not errorlevel 1 (
  echo   [ XX ] This folder is still inside the zip file.
  echo          Right-click the zip, choose "Extract All...", then run setup.bat from the new folder.
  goto :fail
)

echo [1/7] Looking for Python 3.10 or newer
set "PY="
call :trypy "py -3"
if not defined PY call :trypy "python"
if defined PY goto :havepy

echo    [ XX ] Python 3.10+ was not found.
where winget >nul 2>&1
if errorlevel 1 (
  echo           Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^),
  echo           then run setup.bat again.
  goto :fail
)
echo.
choice /C YN /M "         Install Python 3.12 now with winget (about 25 MB)"
if errorlevel 2 goto :fail
echo.
echo    Installing Python, this takes a minute...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
call :trypy "py -3"
if not defined PY (
  echo.
  echo    [ !! ] Python was installed, but this window cannot see it yet.
  echo           Close this window and run setup.bat once more.
  goto :fail
)

:havepy
echo.
echo [2/7] Preparing a private environment (.venv)
if exist ".venv\Scripts\python.exe" (
  echo    [ OK ] already there
) else (
  echo           creating it...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo    [ XX ] Couldn't create the environment. Is the folder write-protected or in a cloud-synced location?
    goto :fail
  )
  echo    [ OK ] created
)

".venv\Scripts\python.exe" -X utf8 "tools\setup_tunedock.py" %*
if errorlevel 1 goto :fail
echo.
echo   You can close this window.
pause >nul
exit /b 0

:trypy
%~1 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if errorlevel 1 exit /b 0
set "PY=%~1"
for /f "delims=" %%v in ('%~1 -c "import sys; print(sys.version.split()[0])"') do echo    [ OK ] Python %%v found
exit /b 0

:fail
echo.
echo   Setup did not finish. The message above says why; setup.log has the details.
echo   Press any key to close this window.
pause >nul
exit /b 1
