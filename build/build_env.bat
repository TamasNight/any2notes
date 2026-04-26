@echo off
REM any2notes — build_env.bat
REM Prepara l'ambiente di build completo:
REM   1. Scarica Python Embeddable 3.11
REM   2. Installa pip nell'env embedded
REM   3. Installa le dipendenze pip
REM   4. Compila launcher.exe con PyInstaller
REM
REM Prerequisiti:
REM   - Python 3.11+ installato nel sistema (usato solo per il build)
REM   - pip installato
REM   - Connessione internet
REM   - PyInstaller: pip install pyinstaller
REM
REM Eseguire dalla root del progetto: build\build_env.bat

setlocal EnableDelayedExpansion

set ROOT=%~dp0..
set BUILD=%~dp0
set PYENV=%BUILD%python_env
set PYEMB_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
set PYEMB_ZIP=%BUILD%python-embed.zip
set GET_PIP=%BUILD%get-pip.py
set WHEELS=%PYENV%\wheels

echo.
echo ============================================================
echo  any2notes — Build Environment
echo ============================================================
echo.

REM ── Step 1: Scarica Python Embeddable ──────────────────────────────────
if exist "%PYENV%\python.exe" (
    echo [1/4] Python embeddable gia' presente. Skip.
) else (
    echo [1/4] Download Python 3.11 embeddable...
    powershell -Command "Invoke-WebRequest -Uri '%PYEMB_URL%' -OutFile '%PYEMB_ZIP%'"
    if errorlevel 1 (
        echo ERRORE: Download Python fallito.
        exit /b 1
    )
    echo       Estrazione...
    mkdir "%PYENV%"
    powershell -Command "Expand-Archive -Path '%PYEMB_ZIP%' -DestinationPath '%PYENV%' -Force"
    del "%PYEMB_ZIP%"
    echo       OK.
)

REM ── Step 2: Abilita import di site-packages nell'embeddable ────────────
echo [2/4] Configurazione python311._pth...
REM Il file ._pth deve includere "import site" per permettere pip
set PTH_FILE=%PYENV%\python311._pth
(
    echo python311.zip
    echo .
    echo Lib\site-packages
    echo import site
) > "%PTH_FILE%"

REM ── Step 3: Installa pip nell'embeddable ───────────────────────────────
if exist "%PYENV%\Scripts\pip.exe" (
    echo [3/4] pip gia' installato. Skip.
) else (
    echo [3/4] Installazione pip nell'embeddable...
    powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%GET_PIP%'"
    if errorlevel 1 (
        echo ERRORE: Download get-pip.py fallito.
        exit /b 1
    )
    "%PYENV%\python.exe" "%GET_PIP%"
    del "%GET_PIP%"
    echo       OK.
)

REM ── Step 4: Compila launcher.exe con PyInstaller ───────────────────────
echo [4/4] Compilazione launcher.exe...

REM Assicurati che PyInstaller sia installato nel Python di sistema
python -m pip install pyinstaller --quiet

setlocal
set ROOT=%~dp0..
set BUILD_OUT=%ROOT%\build\output

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name launcher ^
    --distpath "%BUILD_OUT%" ^
    --workpath "%ROOT%\build\pyinstaller_tmp" ^
    --add-data "%ROOT%\app:app" ^
    --add-data "%ROOT%\app\ui\style.qss:app/ui" ^
    --add-data "%ROOT%\scripts:scripts" ^
    --add-data "%ROOT%\assets:assets" ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtGui ^
    --hidden-import PyQt6.QtWidgets ^
    --collect-all PyQt6 ^
    "%ROOT%\main.py"

if errorlevel 1 (
    echo ERRORE: PyInstaller fallito.
    exit /b 1
)

echo.
echo ============================================================
echo  Build completato con successo!
echo  Output: build\output\launcher.exe
echo  Env:    build\python_env\
echo.
echo  Prossimi passi:
echo    1. Apri installer\any2notes.iss con Inno Setup Compiler
echo    2. Compila per ottenere dist\any2notes-setup-0.4.0.exe
echo ============================================================
echo.

endlocal
