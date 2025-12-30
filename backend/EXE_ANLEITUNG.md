# 🚌 Bus Display - EXE erstellen

## Schnellstart (Windows)

### Methode 1: Automatisch (empfohlen)

1. Laden Sie diese Dateien herunter:
   - `bus_display_app.py`
   - `ERSTELLE_EXE.bat`

2. Legen Sie beide Dateien in denselben Ordner

3. **Doppelklicken** Sie auf `ERSTELLE_EXE.bat`

4. Warten Sie bis der Prozess abgeschlossen ist (~2-5 Minuten)

5. Die fertige `BusDisplay.exe` finden Sie im `dist` Ordner

---

### Methode 2: Manuell

1. Öffnen Sie eine Eingabeaufforderung (CMD)

2. Navigieren Sie zum Ordner mit `bus_display_app.py`:
   ```
   cd C:\Pfad\zum\Ordner
   ```

3. Installieren Sie die Abhängigkeiten:
   ```
   pip install pyserial requests pyinstaller
   ```

4. Erstellen Sie die EXE:
   ```
   pyinstaller --onefile --windowed --name "BusDisplay" bus_display_app.py
   ```

5. Die EXE befindet sich in `dist\BusDisplay.exe`

---

## 🖥️ Verwendung der EXE

1. **Starten** Sie `BusDisplay.exe`

2. **Wählen** Sie den COM-Port Ihres ESP32

3. **Geben** Sie die Telemetrie-Adresse ein (Standard: `192.168.2.216:37337`)

4. **Klicken** Sie auf "Starten"

5. **Starten** Sie "The Bus" und aktivieren Sie die Telemetrie

---

## 📋 Voraussetzungen

- Windows 10/11
- Python 3.8+ (nur zum Erstellen der EXE)
- ESP32 mit gecachten Bildern
- "The Bus" mit aktivierter Telemetrie

---

## ⚠️ Wichtig: Bilder vorher cachen!

Bevor Sie die EXE verwenden, müssen die Bilder 1-8 über die Web-App
auf den ESP32 gecacht werden!

---

## 🔧 Fehlerbehebung

### "Python wurde nicht gefunden"
→ Installieren Sie Python von https://www.python.org/downloads/
→ Aktivieren Sie "Add Python to PATH"

### "COM-Port nicht gefunden"
→ Ist der ESP32 angeschlossen?
→ Schließen Sie den Arduino Serial Monitor

### "Verbindung zum Spiel fehlgeschlagen"
→ Ist Telemetrie im Spiel aktiviert?
→ Prüfen Sie die IP-Adresse
→ Firewall könnte Port 37337 blockieren

### Antivirus blockiert die EXE
→ PyInstaller-EXEs werden manchmal fälschlicherweise blockiert
→ Fügen Sie eine Ausnahme für BusDisplay.exe hinzu

---

## 📊 Features

- ✅ Grafische Benutzeroberfläche
- ✅ Automatische Bild-Umschaltung
- ✅ Diagnose-Funktion
- ✅ Live-Log
- ✅ Keine Installation nötig (portable EXE)
