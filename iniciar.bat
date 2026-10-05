@echo off
echo =========================================
echo     Help Desk - ABC Gotuplas
echo =========================================
echo.
echo Iniciando servidor...
echo.
echo Los usuarios pueden acceder desde:
echo   http://192.168.0.55:8000
echo.
echo Deja esta ventana abierta mientras el sistema este en uso.
echo Para detener el servidor cierra esta ventana.
echo.
cd /d "%~dp0"
call venv\Scripts\activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
