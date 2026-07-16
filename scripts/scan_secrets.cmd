@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scan_secrets.ps1" %*
exit /b %ERRORLEVEL%
