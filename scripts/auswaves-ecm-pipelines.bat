echo off

set arg1=%1

if "%arg1%"=="" (
    echo [ERROR] Please pass a valid script name
    echo usage: auswaves-ecm-pipelines.bat [python_script_name]
    exit /b 1
)

REM Set up virtual environment Python path
set PYTHON_EXEC=C:\Users\00116827\cwb\imos_ecm_moorings\.imos_ecm_moorings\Scripts\python.exe
set INCOMING_PATH=C:\Users\00116827\cwb\imos_ecm_moorings\data


REM Conditional execution based on the passed argument
if "%arg1%"=="get-ecm-nrt" (
    echo [STARTED] %DATE% %TIME%
    %PYTHON_EXEC% C:\Users\00116827\cwb\imos_ecm_moorings\scripts\get-ecm-nrt.py ^
    -o %INCOMING_PATH% ^
    -i %INCOMING_PATH% ^
    -e > %INCOMING_PATH%\task_scheduler_logs\get-ecm-nrt.log 2>&1
    echo [FINISHED] %DATE% %TIME%

) else (
    echo [ERROR] Invalid script name provided.
    exit /b 1
)