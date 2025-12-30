@echo off
title Bus Display - EXE Erstellen

echo.
echo ============================================================
echo         BUS DISPLAY - EXE ERSTELLEN
echo         Mit eingebetteten Bildern (test1-test8)
echo ============================================================
echo.

:: Pruefen ob Python installiert ist
echo [1/4] Pruefe Python-Installation...
python --version > nul 2>&1
if errorlevel 1 (
    echo.
    echo FEHLER: Python ist nicht installiert!
    echo.
    echo Bitte installieren Sie Python von: https://www.python.org/downloads/
    echo Aktivieren Sie "Add Python to PATH" waehrend der Installation!
    echo.
    pause
    exit /b 1
)
echo OK - Python gefunden!
echo.

:: Abhaengigkeiten installieren
echo [2/4] Installiere Abhaengigkeiten...
pip install pyserial requests pillow pyinstaller --quiet
if errorlevel 1 (
    echo FEHLER beim Installieren der Abhaengigkeiten!
    pause
    exit /b 1
)
echo OK - Abhaengigkeiten installiert!
echo.

:: EXE erstellen
echo [3/4] Erstelle EXE-Datei...
echo     (Dies kann 2-5 Minuten dauern)
echo.
pyinstaller --onefile --windowed --name "BusDisplay" --clean BusDisplay_Complete.py

if errorlevel 1 (
    echo.
    echo FEHLER beim Erstellen der EXE!
    pause
    exit /b 1
)
echo.
echo OK - EXE erfolgreich erstellt!
echo.

:: Aufraeumen
echo [4/4] Raeume auf...
if exist build rmdir /s /q build
if exist BusDisplay_Complete.spec del BusDisplay_Complete.spec
if exist __pycache__ rmdir /s /q __pycache__
echo OK - Aufgeraeumt!
echo.

:: Fertig
echo ============================================================
echo                    FERTIG!
echo ============================================================
echo.
echo Die EXE-Datei befindet sich in:
echo    %cd%\dist\BusDisplay.exe
echo.
echo Die Bilder test1-test8 sind bereits eingebettet!
echo Klicken Sie einfach auf "Eingebettete Bilder cachen"
echo.

explorer dist

pause
