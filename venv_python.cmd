@echo off
set SCRIPT_DIR=%~dp0
set "REPO_DIR=%SCRIPT_DIR%\."

call "%REPO_DIR%\venv\Scripts\activate.bat"

python %*

