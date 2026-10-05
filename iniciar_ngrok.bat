@echo off
echo =========================================
echo     Help Desk - Tunel Ngrok
echo =========================================
echo.
echo Abriendo tunel hacia internet...
echo.
echo Una vez iniciado, los usuarios acceden desde:
echo   https://contact-outing-outlet.ngrok-free.dev
echo.
echo Deja esta ventana abierta mientras el sistema este en uso.
echo.
"C:\Users\FINCOMEX\AppData\Local\Microsoft\WindowsApps\ngrok.exe" http 8000 --url https://contact-outing-outlet.ngrok-free.dev
pause
