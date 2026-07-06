@echo off
REM Double-click this file to push your local commits to GitHub.
cd /d C:\dev\api.quiverquant.com
echo ================================================
echo Pushing your local commits to GitHub...
echo ================================================
echo.
git push origin main
echo.
echo ================================================
echo Done. If it says "Everything up-to-date" or lists
echo objects written, your commits are now on GitHub.
echo Refresh https://github.com/topnodrog/Quant-Foundry
echo ================================================
echo.
pause
