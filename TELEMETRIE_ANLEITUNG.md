# 🚌 Bus Simulator Display - Telemetrie-Steuerung

## Übersicht

Dieses Python-Skript verbindet sich mit der Telemetrie von "The Bus" und steuert
automatisch das ESP32-Display basierend auf dem Spielzustand.

## 📋 Voraussetzungen

1. **Python 3.8+** auf Ihrem Gaming-PC installiert
2. **ESP32** mit den gecachten Bildern verbunden
3. **Telemetrie** im Spiel aktiviert (Einstellungen → Telemetrie → Aktivieren)

## 🔧 Installation

### Schritt 1: Python-Pakete installieren

Öffnen Sie eine Eingabeaufforderung (CMD) oder PowerShell und führen Sie aus:

```bash
pip install pyserial requests
```

### Schritt 2: Skript herunterladen

Laden Sie `telemetry_display.py` aus dem Backend-Ordner herunter und speichern Sie
es auf Ihrem PC.

## 🚀 Verwendung

### Verfügbare Ports auflisten

```bash
python telemetry_display.py --list-ports
```

### Starten mit Standard-Telemetrie (192.168.2.216:37337)

```bash
python telemetry_display.py --port COM3
```

(Ersetzen Sie `COM3` durch Ihren tatsächlichen Port)

### Mit benutzerdefinierter Telemetrie-Adresse

```bash
python telemetry_display.py --port COM3 --telemetry 192.168.2.216:37337
```

## 📺 Bild-Zuordnungen

| Bild | Slot | Bedingung | Dauer |
|------|------|-----------|-------|
| 8 | 7 | Zündung eingeschaltet | 3 Sekunden |
| 7 | 6 | Zündung AN, Motor AUS | Bis Motor startet |
| 1 | 0 | Motor läuft (Normal) | Standard |
| 2 | 1 | Nebelscheinwerfer AN | Solange aktiv |
| 3 | 2 | Nebelschlussleuchte AN | Solange aktiv |
| 4 | 3 | Vordere Tür öffnet | 2 Sekunden |
| 5 | 4 | Beide Türen + Absenkung | Bis abgesenkt |
| 6 | 5 | Nach Absenkung | Bis Türen schließen |
| 5 | 4 | Türen schließen | Bis geschlossen |
| 1 | 0 | Zurück zu Normal | - |

## ⚠️ Wichtige Hinweise

### Bilder müssen gecacht sein!

Bevor Sie das Telemetrie-Skript verwenden, müssen Sie alle 8 Bilder
über die Web-App auf den ESP32 cachen:

1. Öffnen Sie die Web-App
2. Verbinden Sie sich mit dem ESP32
3. Laden Sie Bilder 1-8 in die entsprechenden Slots
4. Erst dann das Telemetrie-Skript starten

### Telemetrie im Spiel aktivieren

1. "The Bus" starten
2. Einstellungen → Telemetrie
3. Telemetrie aktivieren
4. Spiel neu starten (falls erforderlich)

### Slot-Nummerierung

- **Web-App**: Bild 1-8 = Slot 0-7
- **Skript**: Verwendet automatisch die richtige Zuordnung

## 🔍 Fehlerbehebung

### "Konnte nicht mit ESP32 verbinden"

- Prüfen Sie ob der ESP32 angeschlossen ist
- Verwenden Sie `--list-ports` um den richtigen Port zu finden
- Schließen Sie die Arduino IDE / Serial Monitor (blockiert den Port)

### "Verbindung zum Spiel verloren"

- Ist Telemetrie im Spiel aktiviert?
- Ist die IP-Adresse korrekt? (Standard: 192.168.2.216)
- Firewall könnte Port 37337 blockieren

### Display zeigt falsches Bild

- Prüfen Sie ob alle Bilder gecacht sind (in der Web-App)
- Die Telemetrie-Feldnamen könnten je nach Spielversion variieren

## 📊 Debug-Ausgabe

Das Skript zeigt detaillierte Informationen:

```
============================================================
Bus Simulator Display - Telemetry Controller
============================================================
Telemetrie: http://192.168.2.216:37337
Seriell: COM3 @ 921600 baud
============================================================

✓ Seriell verbunden: COM3 @ 921600 baud
  ESP32: === Bus Simulator Display ===
  ESP32: Ready for image caching!
✓ ESP32 bereit!

→ Warte auf Spielverbindung...
  (Stellen Sie sicher, dass Telemetrie im Spiel aktiviert ist)

✓ Verbunden mit Spiel!
→ Zündung eingeschaltet - zeige Bild 8 für 3 Sekunden
→ Wechsel zu Bild 8
  ESP32: >>> Displaying slot 7 with telemetry
  ESP32: SHOW_OK
→ Zündungs-Animation beendet
→ Wechsel zu Bild 7
...
```

## 🛠️ Anpassung der Telemetrie-Felder

Falls die Lampen-Namen in Ihrer Spielversion anders heißen, können Sie
die Felder in `telemetry_display.py` anpassen:

```python
# Zeile ~130-145 in telemetry_display.py
ignition_lamps = ["LED Ignition", "LED Zuendung", "Ignition", "LED Power"]
engine_lamps = ["LED Engine", "LED Motor", "Engine Running", "LED EngineRunning"]
fog_lamps = ["LED FogLight", "LED Nebelscheinwerfer", "FogLight"]
rear_fog_lamps = ["LED RearFogLight", "LED Nebelschlussleuchte", "RearFogLight"]
kneeling_lamps = ["LED Kneeling", "LED Absenkung", "Kneeling"]
door1_lamps = ["ButtonLight Door 1", "LED Door1", "Door1Open"]
door2_lamps = ["ButtonLight Door 2", "LED Door2", "Door2Open"]
```

## 📞 Support

Bei Fragen können Sie die Telemetrie-Daten selbst prüfen:

```bash
curl http://192.168.2.216:37337/vehicles
curl http://192.168.2.216:37337/player
```

Oder im Browser öffnen, um die verfügbaren Felder zu sehen.
