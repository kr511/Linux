@echo off
rem Claudus starten: holt Administratorrechte und startet das Menue.
rem Nur ASCII in dieser Datei (cmd.exe liest sie in der OEM-Codepage).
setlocal
set "CLAUDUS_PS1=%~dp0Claudus.ps1"
net session >nul 2>&1
if not errorlevel 1 goto admin
echo Claudus braucht Administratorrechte, Windows fragt gleich nach.
powershell.exe -NoProfile -Command "Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',('\"' + $env:CLAUDUS_PS1 + '\"')"
exit /b
:admin
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CLAUDUS_PS1%" %*
echo.
pause
