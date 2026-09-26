@echo off
setlocal
set "APP_DIR=%~dp0"

set "MSYS_PYTHON=C:\msys64\ucrt64\bin\pythonw.exe"
if exist "%MSYS_PYTHON%" (
    "%MSYS_PYTHON%" "%APP_DIR%app.py" %*
    exit /b %errorlevel%
)

where pythonw.exe >nul 2>nul
if not errorlevel 1 (
    pythonw.exe -c "import gi; gi.require_version('Gtk','3.0')" >nul 2>nul
    if not errorlevel 1 (
        pythonw.exe "%APP_DIR%app.py" %*
        exit /b %errorlevel%
    )
)

echo Conversions Calculator requires Python, PyGObject, and GTK 3. 1>&2
echo Run install_windows.ps1 from PowerShell to install the Windows runtime. 1>&2
exit /b 1
