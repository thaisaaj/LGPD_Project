@echo off
title LGPD Web Analyzer
cd /d "%~dp0"

rem ---- Localiza o Python (launcher "py" ou "python") ----
set PY=
where py >nul 2>nul && set PY=py
if not defined PY (
    python --version >nul 2>nul && set PY=python
)
if not defined PY (
    echo [ERRO] Python nao encontrado. Instale em https://www.python.org/downloads/
    pause
    exit /b 1
)

rem ---- Instala dependencias na primeira execucao ----
%PY% -c "import flask, bs4, requests, playwright, anthropic, dotenv" >nul 2>nul
if errorlevel 1 (
    echo Instalando dependencias, aguarde...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar as dependencias.
        pause
        exit /b 1
    )
    %PY% -m playwright install chromium
)

rem ---- Abre o navegador alguns segundos depois do servidor subir ----
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:5000"

echo.
echo ================================================
echo   LGPD Web Analyzer rodando em http://127.0.0.1:5000
echo   Para encerrar, feche esta janela ou pressione Ctrl+C
echo ================================================
echo.
%PY% app.py

pause
