# ESP32-S3 Display Setup - Schritt für Schritt Anleitung

## 📦 Benötigte Hardware

1. **ESP32-S3** Development Board
2. **4" TFT Display** (480x320 Pixel)
   - Kompatibel mit ILI9341 Controller
   - SPI Interface
3. **Verbindungskabel** (falls nicht bereits gelötet)
4. **USB-C Kabel** für Programmierung

## 🔌 Pin-Verbindungen

| Display Pin | ESP32-S3 GPIO | Funktion |
|-------------|---------------|----------|
| SCK         | 12            | SPI Clock |
| MOSI (SDI)  | 11            | SPI Data Out |
| CS          | 10            | Chip Select |
| DC (RS)     | 9             | Data/Command |
| RST (RESET) | 8             | Reset |
| VCC         | 3.3V          | Stromversorgung |
| GND         | GND           | Ground |
| LED (BL)    | 3.3V          | Hintergrundbeleuchtung |

⚠️ **WICHTIG:** Verwenden Sie 3.3V, nicht 5V!

## 🖥️ Arduino IDE Setup

### 1. Arduino IDE installieren
- Download: https://www.arduino.cc/en/software
- Version 2.x empfohlen

### 2. ESP32 Board Support
1. Öffnen Sie Arduino IDE
2. Gehen Sie zu: `Datei` → `Voreinstellungen`
3. Bei "Zusätzliche Boardverwalter-URLs" einfügen:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Öffnen Sie: `Werkzeuge` → `Board` → `Boardverwalter`
5. Suchen Sie nach "esp32"
6. Installieren Sie "esp32 by Espressif Systems" (Version 2.0.11 oder höher)

### 3. Erforderliche Libraries installieren

Gehen Sie zu: `Sketch` → `Bibliothek einbinden` → `Bibliotheken verwalten`

Installieren Sie folgende Libraries:

#### a) Arduino_GFX Library
- Suche: "GFX Library for Arduino"
- von: moononournation
- Version: 1.3.7 oder höher
- ✅ Installieren

#### b) WebSockets
- Suche: "WebSockets"
- von: Markus Sattler
- Version: 2.4.0 oder höher
- ✅ Installieren

#### c) ArduinoJson
- Suche: "ArduinoJson"
- von: Benoit Blanchon
- Version: 6.21.0 oder höher
- ✅ Installieren

## 📝 Code konfigurieren

1. **Datei öffnen:**
   - Laden Sie `esp32_display.ino` aus dem Backend herunter
   - Oder kopieren Sie den Code von `/app/backend/esp32_display.ino`

2. **WiFi Zugangsdaten ändern:**
   ```cpp
   const char* ssid = "IHR_WIFI_SSID";        // Ihr WiFi Name
   const char* password = "IHR_WIFI_PASSWORT"; // Ihr WiFi Passwort
   ```

3. **WebSocket Server URL (bereits konfiguriert):**
   ```cpp
   const char* ws_host = "bus-telemetry-hud.preview.emergentagent.com";
   const uint16_t ws_port = 443;
   const char* ws_path = "/ws/esp32";
   const bool use_ssl = true;
   ```

## ⚙️ Board-Einstellungen

Wählen Sie in Arduino IDE unter `Werkzeuge`:

| Einstellung | Wert |
|-------------|------|
| **Board** | ESP32S3 Dev Module |
| **USB CDC On Boot** | Enabled |
| **CPU Frequency** | 240MHz (WiFi) |
| **Flash Mode** | QIO 80MHz |
| **Flash Size** | 4MB (oder Ihre Board-Größe) |
| **PSRAM** | QSPI PSRAM |
| **Partition Scheme** | Default 4MB with spiffs |
| **Upload Speed** | 921600 |
| **Port** | (Wählen Sie Ihren COM/USB Port) |

⚠️ **PSRAM ist wichtig!** Es wird für den Bild-Buffer verwendet.

## 🚀 Upload auf ESP32

1. **ESP32 anschließen:**
   - Verbinden Sie ESP32 via USB-C
   - Warten Sie bis Port erkannt wird

2. **Port auswählen:**
   - `Werkzeuge` → `Port` → Wählen Sie den ESP32 Port
   - Windows: meist `COM3`, `COM4`, etc.
   - Mac/Linux: meist `/dev/ttyUSB0` oder `/dev/cu.usbserial-...`

3. **Compilieren & Upload:**
   - Klicken Sie auf "Upload" (→ Pfeil-Symbol)
   - Warten Sie bis "Hard resetting via RTS pin..." erscheint
   - ✅ Upload erfolgreich!

## 🔍 Serial Monitor

1. **Serial Monitor öffnen:**
   - `Werkzeuge` → `Serieller Monitor`
   - Oder: `Ctrl+Shift+M`

2. **Baudrate einstellen:**
   - Wählen Sie: `115200 baud`

3. **Was Sie sehen sollten:**
   ```
   =================================
   Bus Simulator Display - ESP32
   =================================
   
   Initializing display...
   PSRAM found! Using PSRAM for image buffer.
   Image buffer allocated: 307200 bytes
   Connecting to WiFi: IHR_WIFI_SSID
   ..........
   WiFi connected!
   IP Address: 192.168.1.XXX
   Connecting to WebSocket: bus-telemetry-hud.preview.emergentagent.com:443/ws/esp32
   [WebSocket] Connected to: ...
   ```

## ✅ Funktionstest

### 1. Display-Test
- Nach dem Start sollte das Display aktiviert werden
- Sie sollten "Bus Display" Text sehen
- Ein grüner Punkt = Verbunden
- Ein roter Punkt = Getrennt

### 2. Verbindungstest
- Öffnen Sie das Web-Interface
- Oben rechts sollte "ESP32 Verbunden" (grün) stehen
- Wenn rot: Überprüfen Sie Serial Monitor für Fehler

### 3. Bild-Test
1. Laden Sie ein Bild im Web-Interface hoch
2. Klicken Sie auf "Senden"
3. Das Bild sollte nach 2-4 Sekunden auf dem Display erscheinen
4. Im Serial Monitor sollte stehen:
   ```
   Receiving image: [ID] (307200 bytes)
   Image displayed in XXX ms
   ```

## 🐛 Troubleshooting

### Problem: ESP32 wird nicht erkannt

**Lösung:**
- CP210x USB-Treiber installieren: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
- Anderes USB-Kabel versuchen
- Board BOOT-Taste gedrückt halten beim Upload

### Problem: WiFi Verbindung schlägt fehl

**Lösung:**
- SSID und Passwort nochmal überprüfen
- 2.4 GHz WiFi verwenden (ESP32 unterstützt kein 5 GHz)
- Router-Firewall überprüfen
- Näher am Router positionieren

### Problem: WebSocket Verbindung schlägt fehl

**Lösung:**
- Backend läuft? (`sudo supervisorctl status backend`)
- Firewall blockiert Port 443?
- `use_ssl = true` für HTTPS-Server
- Netzwerk erlaubt WebSocket-Verbindungen?

### Problem: Display bleibt schwarz

**Lösung:**
- Pin-Verbindungen überprüfen
- VCC und GND richtig angeschlossen?
- Hintergrundbeleuchtung (LED) angeschlossen?
- TFT_RST Pin überprüfen
- Anderen TFT-Controller? ILI9341 anpassen in Code

### Problem: Farben sind falsch

**Lösung:**
- Display-Rotation ändern:
  ```cpp
  gfx->setRotation(1);  // Versuchen Sie 0, 1, 2, oder 3
  ```
- IPS-Display Parameter anpassen:
  ```cpp
  Arduino_GFX *gfx = new Arduino_ILI9341(bus, TFT_RST, 1, true); // true für IPS
  ```

### Problem: Bild wird nicht angezeigt

**Lösung:**
- ESP32 verbunden? (Serial Monitor checken)
- Genug Speicher? PSRAM aktiviert?
- Backend sendet Bild? (Backend Logs checken)
- RGB565-Datei existiert? (`ls /app/backend/rgb565/`)

### Problem: "Image too large" Fehler

**Lösung:**
- PSRAM muss aktiviert sein in Board-Einstellungen
- Board Partition Scheme überprüfen
- Kleineres Bild verwenden (max 480x320)

## 📊 Performance-Tipps

### 1. PSRAM verwenden
- ✅ Aktiviert: Volle Performance, 8 MB zusätzlicher RAM
- ❌ Deaktiviert: Nur kleiner interner RAM, Probleme mit großen Bildern

### 2. WiFi optimieren
- Starkes WiFi-Signal (> -70 dBm)
- 2.4 GHz verwenden
- Weniger parallele WiFi-Geräte
- QoS für ESP32 im Router aktivieren

### 3. CPU auf 240 MHz
- Schnellere Bildverarbeitung
- Bessere WiFi-Performance
- Geringere Latenz

### 4. Upload Speed 921600
- Schnellerer Code-Upload
- Keine Auswirkung auf Runtime-Performance

## 🎯 Erwartete Performance

| Aktion | Zeit |
|--------|------|
| WiFi Verbindung | 2-5 Sekunden |
| WebSocket Verbindung | 1-2 Sekunden |
| Bildübertragung (300KB) | 1-3 Sekunden |
| Bilddarstellung | <100 ms |
| **Gesamt (Upload → Display)** | **2-5 Sekunden** |

## 🔄 Nächste Schritte

Nach erfolgreichem Setup:

1. ✅ Mehrere Bilder hochladen
2. ✅ Bildwechsel testen
3. ✅ Telemetrie-Funktion testen (später)
4. ✅ Integration mit Bus-Simulator vorbereiten

## 📞 Support

Bei Problemen:
1. Serial Monitor Ausgabe überprüfen
2. Backend Logs checken: `tail -f /var/log/supervisor/backend.err.log`
3. Frontend Console öffnen (F12 in Browser)
4. WiFi und Netzwerk-Verbindung testen

---

**Viel Erfolg mit Ihrem Bus Simulator Display! 🚌📺**
