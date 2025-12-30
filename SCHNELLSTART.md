# 🚀 SCHNELLSTART - ESP32 Display einrichten

## ✅ Was Sie brauchen:
1. ESP32-S3 Board
2. 4" TFT Display (480x320)
3. Arduino IDE installiert
4. USB-Kabel

## 📥 Code herunterladen

### Option 1: Über das Web-Interface (EINFACHSTE METHODE)
1. Öffnen Sie: https://esp32-busscreen.preview.emergentagent.com
2. Scrollen Sie nach unten zur "ESP32 Setup" Sektion
3. Klicken Sie auf: **📥 esp32_display.ino**
4. Datei wird heruntergeladen!

### Option 2: Direkter Download-Link
```
https://esp32-busscreen.preview.emergentagent.com/api/esp32/download-sketch
```

### Option 3: Datei vom Server kopieren
Die Datei liegt hier:
```
/app/backend/esp32_display.ino
```

## ⚙️ Code konfigurieren

Öffnen Sie die heruntergeladene Datei und ändern Sie diese Zeilen:

```cpp
// ZEILE 35-36: IHRE WLAN-DATEN EINTRAGEN
const char* ssid = "MeinWLAN";              // ← Ihr WLAN-Name hier eintragen
const char* password = "MeinPasswort123";   // ← Ihr WLAN-Passwort hier eintragen
```

**Beispiele:**
- WLAN-Name: "FritzBox 7590", "TP-Link Home", "Vodafone-AB12CD", etc.
- Passwort: Ihr WLAN-Passwort (normalerweise auf dem Router-Aufkleber)

⚠️ **WICHTIG:** Nutzen Sie 2.4 GHz WLAN (ESP32 unterstützt kein 5 GHz)

Die WebSocket-Server-Adresse ist **bereits korrekt konfiguriert**:
```cpp
const char* ws_host = "bus-telemetry-hud.preview.emergentagent.com";
```
→ Diese Zeile **nicht ändern**!

## 🔧 Arduino IDE Setup

### 1. Libraries installieren
In Arduino IDE: `Sketch` → `Bibliothek einbinden` → `Bibliotheken verwalten`

Installieren Sie:
- **GFX Library for Arduino** (von moononournation)
- **WebSockets** (von Markus Sattler)  
- **ArduinoJson** (von Benoit Blanchon)

### 2. Board-Einstellungen
`Werkzeuge` → Folgende Einstellungen wählen:

| Einstellung | Wert |
|-------------|------|
| Board | ESP32S3 Dev Module |
| USB CDC On Boot | Enabled |
| PSRAM | QSPI PSRAM |
| Upload Speed | 921600 |

### 3. Port wählen
`Werkzeuge` → `Port` → Ihr ESP32 Port auswählen

## ⬆️ Code hochladen

1. ESP32 per USB verbinden
2. In Arduino IDE: Klick auf **Upload** (→ Pfeil-Symbol)
3. Warten bis "Hard resetting..." erscheint
4. ✅ Fertig!

## 🔍 Testen

### Serial Monitor öffnen
`Werkzeuge` → `Serieller Monitor` (Baudrate: 115200)

**Sie sollten sehen:**
```
=================================
Bus Simulator Display - ESP32
=================================

Initializing display...
PSRAM found!
Connecting to WiFi: MeinWLAN
..........
WiFi connected!
IP Address: 192.168.1.XXX
[WebSocket] Connected!
```

### Im Web-Interface prüfen
Öffnen Sie: https://esp32-busscreen.preview.emergentagent.com

Oben rechts sollte stehen: **🟢 ESP32 Verbunden**

## 🖼️ Erstes Bild senden

1. Im Web-Interface ein Bild hochladen (falls noch nicht geschehen)
2. Bei einem Bild auf **"Senden"** klicken
3. Nach 2-5 Sekunden erscheint das Bild auf Ihrem Display!

## ❓ Probleme?

### ESP32 verbindet sich nicht mit WLAN
- WLAN-Name und Passwort nochmal überprüfen (Groß-/Kleinschreibung!)
- 2.4 GHz WLAN verwenden (kein 5 GHz)
- Näher am Router positionieren
- Router-Firewall prüfen

### Display bleibt schwarz
- Pin-Verbindungen überprüfen (SCK=12, MOSI=11, CS=10, DC=9, RST=8)
- VCC an 3.3V (nicht 5V!)
- LED (Backlight) angeschlossen?

### "PSRAM not found" Fehler
- In Arduino IDE: `PSRAM` auf **QSPI PSRAM** setzen
- Board neu flashen

### WebSocket verbindet nicht
- Backend läuft? (sollte automatisch laufen)
- Firewall blockiert Port 443?

## 📊 Erwartete Performance

| Aktion | Zeit |
|--------|------|
| Bildübertragung | 2-5 Sekunden |
| Bildwechsel | Sofort |
| Verbindungsaufbau | 5-10 Sekunden |

## 🎉 Fertig!

Ihr Bus Simulator Display ist einsatzbereit!

**Nächste Schritte:**
- Weitere Bilder hochladen
- Telemetrie-Funktion testen
- Später: Spiel-Integration

---

**Support:** Bei Problemen Serial Monitor und Browser-Konsole (F12) überprüfen!
