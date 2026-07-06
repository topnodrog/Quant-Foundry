@echo off
REM Daily incremental crypto-news pull (Perigon, ~1 API call). Registered as a
REM Windows Scheduled Task by the Quant Foundry project; logs to data\news_cron.log.
cd /d C:\dev\api.quiverquant.com
"C:\Users\jgord\AppData\Local\hermes\bin\uv.exe" run quiverquant perigon >> "C:\dev\api.quiverquant.com\data\news_cron.log" 2>&1
echo %DATE% %TIME% exit=%ERRORLEVEL% >> "C:\dev\api.quiverquant.com\data\news_cron.log"
