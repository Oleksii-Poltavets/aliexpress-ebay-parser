@echo off
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo Virtual environment not found at .venv.
  echo Create it first:
  echo   python -m venv .venv
  echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

"%PYTHON_EXE%" "%~dp0main.py" %*
exit /b %errorlevel%
