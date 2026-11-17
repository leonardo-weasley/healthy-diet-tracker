@echo off
setlocal
cd /d "%~dp0"
set "PYARGS="
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYTHON=%~dp0.venv\Scripts\python.exe"
  goto ready
)
if exist "%~dp0..\..\work\python\python.exe" (
  set "PYTHON=%~dp0..\..\work\python\python.exe"
  goto ready
)
where python.exe >nul 2>&1
if not errorlevel 1 (
  set "PYTHON=python.exe"
  goto setup
)
where py.exe >nul 2>&1
if not errorlevel 1 (
  set "PYTHON=py.exe"
  set "PYARGS=-3"
  goto setup
)
echo Python 3.11 or newer was not found.
echo Install Python and select "Add python.exe to PATH", then reopen this file.
echo See README.md for details.
goto failed

:setup
"%PYTHON%" %PYARGS% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto badversion
echo Creating a project-only Python environment...
"%PYTHON%" %PYARGS% -m venv "%~dp0.venv"
if errorlevel 1 goto failed
set "PYTHON=%~dp0.venv\Scripts\python.exe"
set "PYARGS="

:ready
"%PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto badversion
"%PYTHON%" -c "import flask, flask_sqlalchemy, pydantic, dotenv, PIL, tzdata, openai" >nul 2>&1
if not errorlevel 1 goto run
echo Installing project dependencies. Internet access is needed on first setup...
"%PYTHON%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto failed

:run
echo Starting database, mock AI (if configured) and web app...
echo When ready, open http://127.0.0.1:5000/ in your browser.
echo Keep this window open. Press Ctrl+C to stop everything.
echo.
"%PYTHON%" -u "%~dp0scripts\start_dev.py"
set "RESULT=%ERRORLEVEL%"
echo.
echo The server has stopped. Any error is shown above.
pause
exit /b %RESULT%

:badversion
echo Python 3.11 or newer is required. Check the Python version and try again.
goto failed

:failed
echo Startup did not complete. Read the message above or share a screenshot.
pause
exit /b 1
