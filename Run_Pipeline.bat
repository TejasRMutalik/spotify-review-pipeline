@echo off
echo =======================================================
echo          Spotify Review Pipeline (Manual Run)
echo =======================================================
echo.
echo Setting credentials...
set GOOGLE_SHEET_ID=1iqYFAtN7viDcOh7Egke0oolMcVvzGPf6vqb3LMuzy70
set GOOGLE_SERVICE_ACCOUNT_JSON=service_account.json

echo Starting scraper...
echo.
python main.py

echo.
echo =======================================================
echo                 FINISHED
echo =======================================================
pause
