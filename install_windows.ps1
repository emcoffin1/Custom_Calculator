$ErrorActionPreference = "Stop"
$MsysRoot = "C:\msys64"
$Pacman = Join-Path $MsysRoot "usr\bin\pacman.exe"

if (-not (Test-Path $Pacman)) {
    throw "MSYS2 was not found at C:\msys64. Install it from https://www.msys2.org, then run this script again."
}

& $Pacman -S --needed --noconfirm `
    mingw-w64-ucrt-x86_64-python `
    mingw-w64-ucrt-x86_64-python-gobject `
    mingw-w64-ucrt-x86_64-gtk3
if ($LASTEXITCODE -ne 0) {
    throw "MSYS2 could not install the calculator dependencies."
}

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $MsysRoot "ucrt64\bin\python.exe"
$PythonW = Join-Path $MsysRoot "ucrt64\bin\pythonw.exe"
$AppScript = Join-Path $AppDir "app.py"
$Programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$ShortcutPath = Join-Path $Programs "Conversions Calculator.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = '"' + $AppScript + '"'
$Shortcut.WorkingDirectory = $AppDir
$Shortcut.Description = "Calculator and engineering unit converter"
$Shortcut.Save()

& $Python $AppScript --diagnostics
if ($LASTEXITCODE -ne 0) {
    throw "The calculator runtime check failed."
}

Write-Host "Installed Windows dependencies and Start menu shortcut: $ShortcutPath"
