@echo off

set arg1=%1

if "%arg1%"=="" (
    echo [ERROR] Please pass a valid script name
    echo usage: auswaves-ecm-pipelines.bat [python_script_name]
    exit /b 1
)

REM Resolve absolute project root path
for %%I in ("%~dp0..") do set "ROOT_DIR=%%~fI"

REM Load .env from root directory
for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT_DIR%\.env") do (
    set "%%A=%%B"
)

REM Conditional execution based on the passed argument
if "%arg1%"=="ecm-get-raw-nrt" (
    echo [STARTED] %DATE% %TIME%
    %PYTHON_EXEC% "%ROOT_DIR%\scripts\%arg1%.py" ^
    -o %INCOMING_PATH% ^
    -i %INCOMING_PATH% ^
    --window 5 ^
    -e > %INCOMING_PATH%\task_scheduler_logs\%arg1%.log 2>&1
    echo [FINISHED] %DATE% %TIME%

) else if "%arg1%"=="ecm-proc-auswaves-csvs" (
    echo [STARTED] %DATE% %TIME%
    %PYTHON_EXEC% "%ROOT_DIR%\scripts\%arg1%.py" ^
    -o %INCOMING_PATH% ^
    -i %INCOMING_PATH% ^
    --window 5 ^
    -e > %INCOMING_PATH%\task_scheduler_logs\%arg1%.log 2>&1
    echo [FINISHED] %DATE% %TIME%

) else if "%arg1%"=="ecm-alerts" (
    echo [STARTED] %DATE% %TIME%
    %PYTHON_EXEC% "%ROOT_DIR%\scripts\%arg1%.py" ^
    -o %INCOMING_PATH% ^
    -i %INCOMING_PATH% ^
    --window 5 ^
    -e > %INCOMING_PATH%\task_scheduler_logs\%arg1%.log 2>&1
    echo [FINISHED] %DATE% %TIME%

) else (
    echo [ERROR] Invalid script name provided.
    exit /b 1
)