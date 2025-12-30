# 🔧 ILI9488 Display - Korrigierte Version

## ⚠️ Wichtiger Unterschied!

**ILI9341 vs ILI9488:**

| Feature | ILI9341 | ILI9488 (Ihr Display) |
|---------|---------|----------------------|
| Auflösung | 240x320 | **480x320** ✅ |
| Farben | RGB565 (16-bit) | **RGB666 (18-bit)** |
| Driver | `Arduino_ILI9341` | **`Arduino_ILI9488_18bit`** ✅ |

## ✅ Was wurde korrigiert:

### 1. Richtiger Display-Treiber (Zeile 57):
```cpp
// FALSCH (vorher):
Arduino_GFX *gfx = new Arduino_ILI9341(bus, TFT_RST, 1, false);

// RICHTIG (jetzt):
Arduino_GFX *gfx = new Arduino_ILI9488_18bit(bus, TFT_RST, 0, false);
```

### 2. Rotation angepasst (Zeile 92):
```cpp
gfx->setRotation(3);  // Landscape mode für ILI9488
// Falls die Orientierung falsch ist, versuchen Sie: 0, 1, 2, oder 3
```

### 3. Display-Info hinzugefügt:
Der Welcome Screen zeigt jetzt "ILI9488 Driver" zur Bestätigung.

## 📥 Neue Version herunterladen:

Die Datei wurde bereits aktualisiert:

1. **Web-Interface:**
   - https://esp32-busscreen.preview.emergentagent.com
   - Klick auf 📥 **esp32_display_serial.ino**

2. **Direktlink:**
   ```
   https://esp32-busscreen.preview.emergentagent.com/api/esp32/download-sketch
   ```

3. **Lokaler Pfad:**
   ```
   /app/backend/esp32_display_serial.ino
   ```

## 🔧 Kompilieren & Hochladen:

1. ✅ Neue Version herunterladen (alte löschen!)
2. ✅ In Arduino IDE öffnen
3. ✅ Board: ESP32S3 Dev Module
4. ✅ PSRAM: QSPI PSRAM
5. ✅ Kompilieren & Hochladen
6. ✅ Serial Monitor öffnen (115200 baud)

## 📺 Erwartete Ausgabe:

```
=================================
Bus Simulator Display - ESP32
USB Serial Version (ILI9488)
=================================

Initializing ILI9488 display...
PSRAM found! Using PSRAM for image buffer.
Image buffer allocated: 307200 bytes

Ready! Waiting for images via USB Serial...
ACK
```

Auf dem Display sollten Sie sehen:
- **"Bus Display"** (groß)
- **"USB Serial Mode"** (mittel)
- **"ILI9488 Driver"** (klein, gelb) ← NEU!
- **"Bereit fur Bilder!"** (grün)
- Grüner Kreis mit "USB READY"

## ⚙️ Rotation einstellen:

Falls die Anzeige gedreht ist, ändern Sie Zeile 92:

```cpp
gfx->setRotation(3);  // Standard

// Versuchen Sie:
gfx->setRotation(0);  // 0° (Portrait)
gfx->setRotation(1);  // 90° (Landscape)
gfx->setRotation(2);  // 180° (Portrait umgekehrt)
gfx->setRotation(3);  // 270° (Landscape umgekehrt)
```

## 🎯 Wichtige Hinweise:

### ILI9488-spezifisch:
- ✅ Verwendet 18-bit Farbtiefe (RGB666)
- ✅ Arduino_GFX konvertiert automatisch von RGB565
- ✅ Bessere Farbqualität als ILI9341
- ✅ Gleiche Auflösung: 480x320

### Pin-Verbindungen bleiben gleich:
```
SCK  = GPIO 12
MOSI = GPIO 11
CS   = GPIO 10
DC   = GPIO 9
RST  = GPIO 8
VCC  = 3.3V
GND  = GND
```

## 🐛 Troubleshooting:

### Display bleibt weiß oder zeigt Müll
→ **ILI9488_18bit** Treiber verwenden (nicht ILI9341!)

### Farben sind falsch
→ Normal bei ILI9488, Library konvertiert automatisch

### Text ist verdreht/gedreht
→ `setRotation(0-3)` in Zeile 92 ändern

### Display zeigt nur teilweise Bild
→ PSRAM muss aktiviert sein in Board-Einstellungen

## ✅ Jetzt sollte es funktionieren!

**Bitte laden Sie die neue ILI9488-Version herunter und testen Sie sie!**

Der Unterschied zwischen ILI9341 und ILI9488 ist erheblich - der richtige Treiber ist entscheidend! 🎯
