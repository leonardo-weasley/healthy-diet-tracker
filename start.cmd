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
if /I "%~1"=="--check" goto check
echo Starting the local backend...
echo When ready, open http://127.0.0.1:5000/ in your browser.
echo Keep this window open. Press Ctrl+C to stop.
echo DEMO MODE: fixed AI output; records are cleared on restart.
echo.
"%PYTHON%" -u "%~dp0run.py"
set "RESULT=%ERRORLEVEL%"
echo.
echo The server has stopped. Any error is shown above.
pause
exit /b %RESULT%

:check
"%PYTHON%" "%~dp0demo.py"
exit /b %ERRORLEVEL%

:badversion
echo Python 3.11 or newer is required. Check the Python version and try again.

:failed
echo Startup did not complete. Read the message above or share a screenshot.
if /I not "%~1"=="--check" pause
exit /b 1
