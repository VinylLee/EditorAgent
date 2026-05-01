@echo off
setlocal enabledelayedexpansion

for /l %%i in (1,1,5) do (
    echo Attempt %%i: Starting the application...
    C:\Users\28911\miniconda3\envs\agent311\python.exe e:/Files/Documents/other/aw/wechat/EditorAgent/wechat_edu_agent/main.py run
    if !errorlevel! equ 0 (
        echo Application started successfully.
        goto :eof
    ) else (
        echo Application failed to start. Retrying in 5 seconds...
        timeout /t 5 /nobreak >nul
    )
)
