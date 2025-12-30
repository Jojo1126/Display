#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bus Simulator Display - Komplette Anwendung
============================================

Vollständige Anwendung mit:
- Bild-Upload und Caching auf ESP32
- Telemetrie-Steuerung
- Grafische Oberfläche
- Eingebettete Bilder (test1-test8)

Zum Erstellen der .exe:
    pip install pyinstaller pillow
    pyinstaller --onefile --windowed --name "BusDisplay" bus_display_app.py

Version: 3.0
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import struct
import os
import base64
import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List

# Eingebettete Bilder (komprimiert, Base64-kodiert)
# Diese werden beim Start dekomprimiert
try:
    from embedded_images import EMBEDDED_IMAGES
    HAS_EMBEDDED_IMAGES = True
except ImportError:
    EMBEDDED_IMAGES = {}
    HAS_EMBEDDED_IMAGES = False

# Imports mit Fehlerbehandlung
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ============================================================================
# Konstanten
# ============================================================================

APP_NAME = "Bus Simulator Display"
APP_VERSION = "3.0"
DEFAULT_TELEMETRY = "192.168.2.216:37337"
DEFAULT_BAUDRATE = 921600
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
IMAGE_SIZE = SCREEN_WIDTH * SCREEN_HEIGHT * 2  # RGB565 = 2 bytes per pixel
MAX_SLOTS = 8


def decompress_embedded_image(slot: int) -> Optional[bytes]:
    """Dekomprimiert ein eingebettetes Bild"""
    if slot not in EMBEDDED_IMAGES:
        return None
    try:
        compressed = base64.b64decode(EMBEDDED_IMAGES[slot])
        return zlib.decompress(compressed)
    except Exception as e:
        print(f"Fehler beim Dekomprimieren von Bild {slot}: {e}")
        return None


class DisplayImage(Enum):
    """Bild-Zuordnungen"""
    NORMAL = 1
    FOG_LIGHTS = 2
    REAR_FOG = 3
    FRONT_DOOR = 4
    DOORS_KNEELING = 5
    AFTER_KNEELING = 6
    IGNITION_NO_ENGINE = 7
    IGNITION_START = 8


@dataclass
class BusState:
    """Aktueller Zustand des Busses"""
    ignition_on: bool = False
    engine_running: bool = False
    fog_lights_on: bool = False
    rear_fog_on: bool = False
    front_door_open: bool = False
    rear_door_open: bool = False
    kneeling: bool = False
    gear: int = 0
    speed: int = 0
    connected: bool = False


# ============================================================================
# Bild-Konvertierung
# ============================================================================

def convert_to_rgb565(image_path: str) -> Optional[bytes]:
    """Konvertiert ein Bild zu RGB565 Format"""
    if not PIL_AVAILABLE:
        return None
    
    try:
        img = Image.open(image_path)
        img = img.convert('RGB')
        img = img.resize((SCREEN_WIDTH, SCREEN_HEIGHT), Image.Resampling.LANCZOS)
        
        pixels = list(img.getdata())
        rgb565_data = bytearray()
        
        for r, g, b in pixels:
            # RGB888 zu RGB565
            r5 = (r >> 3) & 0x1F
            g6 = (g >> 2) & 0x3F
            b5 = (b >> 3) & 0x1F
            rgb565 = (r5 << 11) | (g6 << 5) | b5
            # Little-endian
            rgb565_data.append(rgb565 & 0xFF)
            rgb565_data.append((rgb565 >> 8) & 0xFF)
        
        return bytes(rgb565_data)
    except Exception as e:
        print(f"Konvertierungsfehler: {e}")
        return None


# ============================================================================
# ESP32 Controller
# ============================================================================

class ESP32Controller:
    """Controller für ESP32-Kommunikation"""
    
    def __init__(self, log_callback=None):
        self.serial: Optional[serial.Serial] = None
        self.log = log_callback or print
        self.connected = False
        self.cached_slots = [False] * MAX_SLOTS
    
    def connect(self, port: str, baudrate: int = DEFAULT_BAUDRATE) -> bool:
        """Verbindung herstellen"""
        if not SERIAL_AVAILABLE:
            self.log("FEHLER: PySerial nicht installiert!")
            return False
        
        try:
            self.serial = serial.Serial(port=port, baudrate=baudrate, timeout=1)
            time.sleep(2)
            self.log(f"Verbunden: {port} @ {baudrate} baud")
            
            # Auf ESP32 warten
            start = time.time()
            while time.time() - start < 5:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    self.log(f"  ESP32: {line}")
                    if "ACK" in line or "Ready" in line:
                        self.connected = True
                        self.log("ESP32 bereit!")
                        return True
            
            self.connected = True
            return True
            
        except Exception as e:
            self.log(f"Verbindungsfehler: {e}")
            return False
    
    def disconnect(self):
        """Verbindung trennen"""
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.connected = False
        self.log("Verbindung getrennt")
    
    def read_response(self, timeout: float = 1.0) -> List[str]:
        """Liest Antworten vom ESP32"""
        responses = []
        if not self.serial:
            return responses
        
        start = time.time()
        while time.time() - start < timeout:
            if self.serial.in_waiting:
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    responses.append(line)
            time.sleep(0.01)
        
        return responses
    
    def cache_image(self, slot: int, image_data: bytes, progress_callback=None) -> bool:
        """Cached ein Bild auf dem ESP32"""
        if not self.serial or not self.connected:
            return False
        
        if slot < 0 or slot >= MAX_SLOTS:
            self.log(f"Ungueltiger Slot: {slot}")
            return False
        
        if len(image_data) != IMAGE_SIZE:
            self.log(f"Falsche Bildgroesse: {len(image_data)} (erwartet: {IMAGE_SIZE})")
            return False
        
        try:
            # Cache-Befehl senden
            command = f"CACHE:{slot}:{IMAGE_SIZE}\n"
            self.serial.write(command.encode())
            self.log(f"Sende CACHE:{slot}:{IMAGE_SIZE}")
            
            # Auf ACK warten
            time.sleep(0.1)
            responses = self.read_response(2.0)
            for r in responses:
                self.log(f"  ESP32: {r}")
            
            ack_received = any("ACK" in r for r in responses)
            if not ack_received:
                self.log("Kein ACK erhalten, sende trotzdem...")
            
            # Bilddaten in Chunks senden
            chunk_size = 4096
            total_sent = 0
            
            while total_sent < len(image_data):
                chunk = image_data[total_sent:total_sent + chunk_size]
                self.serial.write(chunk)
                total_sent += len(chunk)
                
                progress = int((total_sent / len(image_data)) * 100)
                if progress_callback:
                    progress_callback(progress)
                
                # Kurze Pause fuer Stabilitaet
                time.sleep(0.005)
            
            self.log(f"Gesendet: {total_sent} bytes")
            
            # Auf Bestaetigung warten
            time.sleep(0.5)
            responses = self.read_response(5.0)
            for r in responses:
                self.log(f"  ESP32: {r}")
            
            if any("CACHED_OK" in r for r in responses):
                self.cached_slots[slot] = True
                self.log(f"Bild {slot + 1} erfolgreich gecached!")
                return True
            else:
                self.log("Keine CACHED_OK Bestaetigung")
                return False
            
        except Exception as e:
            self.log(f"Cache-Fehler: {e}")
            return False
    
    def show_image(self, slot: int, gear: int = 0, speed: int = 0) -> bool:
        """Zeigt ein gecachtes Bild an"""
        if not self.serial or not self.connected:
            return False
        
        try:
            command = f"SHOW:{slot}:{gear}:{speed}\n"
            self.serial.write(command.encode())
            return True
        except:
            return False
    
    def get_status(self) -> List[str]:
        """Holt den Status vom ESP32"""
        if not self.serial or not self.connected:
            return []
        
        try:
            self.serial.write(b"STATUS\n")
            time.sleep(0.2)
            return self.read_response(2.0)
        except:
            return []


# ============================================================================
# Telemetrie Controller
# ============================================================================

class TelemetryController:
    """Controller fuer Telemetrie"""
    
    def __init__(self, esp32: ESP32Controller, log_callback=None):
        self.esp32 = esp32
        self.log = log_callback or print
        self.telemetry_url = ""
        self.bus_state = BusState()
        self.current_image = -1
        self.current_vehicle = None
        self.running = False
        
        # Timing
        self.ignition_start_time = None
        self.front_door_open_time = None
        self.kneeling_complete_time = None
        
        # Vorherige Zustaende
        self.prev_ignition = False
        self.prev_front_door = False
        self.prev_kneeling = False
        self.prev_both_doors = False
        
        # Animationen
        self.showing_ignition_animation = False
        self.showing_door_animation = False
        self.in_kneeling_sequence = False
        
        # Lampenkonfiguration
        self.lamp_config = {
            "ignition": ["LED Ignition", "LED Zuendung", "Ignition", "LED Power", "LED_Ignition"],
            "engine": ["LED Engine", "LED Motor", "Engine Running", "LED EngineRunning", "LED_EngineRunning"],
            "fog_front": ["LED FogLight", "LED Nebelscheinwerfer", "FogLight", "LED FogLightFront"],
            "fog_rear": ["LED RearFogLight", "LED Nebelschlussleuchte", "RearFogLight", "LED FogLightRear"],
            "kneeling": ["LED Kneeling", "LED Absenkung", "Kneeling", "LED BusKneeling"],
            "door1": ["ButtonLight Door 1", "LED Door1", "Door1Open", "LED DoorFront"],
            "door2": ["ButtonLight Door 2", "LED Door2", "Door2Open", "LED DoorRear"],
            "door3": ["ButtonLight Door 3", "LED Door3", "Door3Open"]
        }
    
    def get_current_vehicle(self):
        """Holt aktuelles Fahrzeug"""
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            response = requests.get(f"{self.telemetry_url}/vehicles", timeout=1)
            vehicles = response.json()
            if not vehicles:
                return None
            
            response = requests.get(f"{self.telemetry_url}/player", timeout=1)
            player = response.json()
            
            if player.get("Mode") == "Vehicle":
                return player.get("CurrentVehicle")
            return None
        except:
            return None
    
    def get_telemetry(self):
        """Holt Telemetrie-Daten"""
        if not REQUESTS_AVAILABLE:
            return None
        
        if not self.current_vehicle:
            self.current_vehicle = self.get_current_vehicle()
            if not self.current_vehicle:
                return None
        
        try:
            url = f"{self.telemetry_url}/vehicles/{self.current_vehicle}"
            params = {"vars": "Buttons,AllLamps,IsPlayerControlled,BusLogic,Velocity,Gear,Speed"}
            response = requests.get(url, params=params, timeout=1)
            data = response.json()
            
            if data.get("IsPlayerControlled") == "false":
                self.current_vehicle = None
                return None
            
            return data
        except:
            self.current_vehicle = None
            return None
    
    def check_lamp(self, lamps: dict, names: list) -> bool:
        """Prueft ob eine Lampe aktiv ist"""
        for name in names:
            if name in lamps:
                try:
                    if float(lamps[name]) > 0:
                        return True
                except:
                    pass
        return False
    
    def parse_telemetry(self, data: dict):
        """Parst Telemetrie-Daten"""
        lamps = data.get("AllLamps", {})
        buttons = data.get("Buttons", [])
        
        # Vorherige Zustaende speichern
        self.prev_ignition = self.bus_state.ignition_on
        self.prev_front_door = self.bus_state.front_door_open
        self.prev_kneeling = self.bus_state.kneeling
        self.prev_both_doors = self.bus_state.front_door_open and self.bus_state.rear_door_open
        
        # Lampen auswerten
        self.bus_state.ignition_on = self.check_lamp(lamps, self.lamp_config["ignition"])
        self.bus_state.engine_running = self.check_lamp(lamps, self.lamp_config["engine"])
        self.bus_state.fog_lights_on = self.check_lamp(lamps, self.lamp_config["fog_front"])
        self.bus_state.rear_fog_on = self.check_lamp(lamps, self.lamp_config["fog_rear"])
        self.bus_state.kneeling = self.check_lamp(lamps, self.lamp_config["kneeling"])
        self.bus_state.front_door_open = self.check_lamp(lamps, self.lamp_config["door1"])
        self.bus_state.rear_door_open = (
            self.check_lamp(lamps, self.lamp_config["door2"]) or
            self.check_lamp(lamps, self.lamp_config["door3"])
        )
        
        # Gang
        for button in buttons:
            if button.get("Name") == "GearSwitch":
                state = button.get("State", "Neutral")
                self.bus_state.gear = 1 if state == "Drive" else (-1 if state == "Reverse" else 0)
        
        # Geschwindigkeit
        if "Speed" in data:
            try:
                self.bus_state.speed = int(abs(float(data["Speed"])))
            except:
                pass
        
        self.bus_state.connected = True
    
    def determine_image(self) -> int:
        """Bestimmt welches Bild angezeigt werden soll"""
        now = time.time()
        
        # Zuendung Animation (3 Sekunden)
        if self.bus_state.ignition_on and not self.prev_ignition:
            self.ignition_start_time = now
            self.showing_ignition_animation = True
            self.log("Zuendung AN - Bild 8 (3 Sek)")
        
        if self.showing_ignition_animation:
            if self.ignition_start_time and (now - self.ignition_start_time) < 3.0:
                return 8
            else:
                self.showing_ignition_animation = False
        
        # Zuendung an, Motor aus
        if self.bus_state.ignition_on and not self.bus_state.engine_running:
            return 7
        
        # Tuer-Sequenzen
        if self.bus_state.front_door_open and not self.prev_front_door:
            self.front_door_open_time = now
            self.showing_door_animation = True
            self.log("Vordere Tuer oeffnet - Bild 4 (2 Sek)")
        
        if self.showing_door_animation and self.bus_state.front_door_open:
            if self.front_door_open_time and (now - self.front_door_open_time) < 2.0:
                return 4
            else:
                self.showing_door_animation = False
        
        # Beide Tueren + Absenkung
        both_doors = self.bus_state.front_door_open and self.bus_state.rear_door_open
        
        if both_doors and self.bus_state.kneeling:
            if not self.in_kneeling_sequence:
                self.in_kneeling_sequence = True
                self.log("Absenkung - Bild 5")
            return 5
        
        # Nach Absenkung
        if self.in_kneeling_sequence and not self.bus_state.kneeling and both_doors:
            if not self.kneeling_complete_time:
                self.kneeling_complete_time = now
                self.log("Absenkung fertig - Bild 6")
            return 6
        
        # Tueren schliessen
        if self.in_kneeling_sequence and not both_doors:
            if self.prev_both_doors:
                self.log("Tueren schliessen - Bild 5")
                self.kneeling_complete_time = None
            
            if not self.bus_state.front_door_open and not self.bus_state.rear_door_open:
                self.in_kneeling_sequence = False
                self.log("Tueren geschlossen - Bild 1")
            else:
                return 5
        
        # Lichter
        if self.bus_state.fog_lights_on:
            return 2
        if self.bus_state.rear_fog_on:
            return 3
        
        # Normal
        return 1
    
    def run_loop(self):
        """Hauptschleife"""
        last_time = 0
        connection_msg = False
        
        while self.running:
            now = time.time()
            
            if now - last_time >= 0.1:
                last_time = now
                
                data = self.get_telemetry()
                
                if data:
                    if not self.bus_state.connected:
                        self.log("Verbunden mit Spiel!")
                        connection_msg = False
                    
                    self.parse_telemetry(data)
                    target = self.determine_image()
                    
                    if target != self.current_image:
                        self.log(f"Wechsel zu Bild {target}")
                        slot = target - 1
                        if self.esp32.show_image(slot, self.bus_state.gear, self.bus_state.speed):
                            self.current_image = target
                else:
                    if self.bus_state.connected and not connection_msg:
                        self.log("Warte auf Spielverbindung...")
                        connection_msg = True
                    self.bus_state.connected = False
            
            time.sleep(0.01)


# ============================================================================
# Hauptanwendung
# ============================================================================

class BusDisplayApp:
    """Hauptanwendung mit GUI"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("750x700")
        self.root.minsize(700, 600)
        
        # Controller
        self.esp32 = ESP32Controller(log_callback=self.log)
        self.telemetry = TelemetryController(self.esp32, log_callback=self.log)
        
        # Bild-Pfade
        self.image_paths = [""] * MAX_SLOTS
        
        # Thread
        self.telemetry_thread = None
        
        # UI erstellen
        self.create_ui()
        self.refresh_ports()
        
        # Schliessen-Handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_ui(self):
        """Erstellt die Benutzeroberflaeche"""
        # Notebook fuer Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Bilder cachen
        self.create_cache_tab()
        
        # Tab 2: Telemetrie
        self.create_telemetry_tab()
        
        # Tab 3: Info
        self.create_info_tab()
        
        # Log-Bereich (immer sichtbar)
        log_frame = ttk.LabelFrame(self.root, text="Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def create_cache_tab(self):
        """Tab fuer Bild-Caching"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Bilder Cachen")
        
        # Verbindung
        conn_frame = ttk.LabelFrame(tab, text="ESP32 Verbindung", padding="10")
        conn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        port_frame = ttk.Frame(conn_frame)
        port_frame.pack(fill=tk.X)
        
        ttk.Label(port_frame, text="Port:").pack(side=tk.LEFT)
        self.port_combo = ttk.Combobox(port_frame, width=15, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(port_frame, text="Aktualisieren", command=self.refresh_ports).pack(side=tk.LEFT, padx=5)
        
        self.connect_btn = ttk.Button(port_frame, text="Verbinden", command=self.toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=20)
        
        self.conn_status = ttk.Label(port_frame, text="Nicht verbunden", foreground="red")
        self.conn_status.pack(side=tk.LEFT, padx=10)
        
        # Bilder
        images_frame = ttk.LabelFrame(tab, text="Bilder (1-8)", padding="10")
        images_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.image_frames = []
        self.image_labels = []
        self.image_buttons = []
        self.cache_buttons = []
        self.status_labels = []
        
        # 2x4 Grid
        for i in range(MAX_SLOTS):
            row = i // 4
            col = i % 4
            
            frame = ttk.Frame(images_frame)
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            ttk.Label(frame, text=f"Bild {i+1}", font=("Arial", 10, "bold")).pack()
            
            label = ttk.Label(frame, text="Kein Bild", width=20, anchor="center")
            label.pack(pady=2)
            self.image_labels.append(label)
            
            btn_frame = ttk.Frame(frame)
            btn_frame.pack()
            
            select_btn = ttk.Button(btn_frame, text="Waehlen", width=8,
                                   command=lambda idx=i: self.select_image(idx))
            select_btn.pack(side=tk.LEFT, padx=2)
            self.image_buttons.append(select_btn)
            
            cache_btn = ttk.Button(btn_frame, text="Cachen", width=8,
                                  command=lambda idx=i: self.cache_image(idx))
            cache_btn.pack(side=tk.LEFT, padx=2)
            self.cache_buttons.append(cache_btn)
            
            status = ttk.Label(frame, text="", foreground="gray")
            status.pack()
            self.status_labels.append(status)
        
        # Grid-Konfiguration
        for i in range(4):
            images_frame.columnconfigure(i, weight=1)
        for i in range(2):
            images_frame.rowconfigure(i, weight=1)
        
        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(tab, variable=self.progress_var, maximum=100)
        self.progress.pack(fill=tk.X, padx=10, pady=5)
        
        # Buttons Frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(pady=5)
        
        # Eingebettete Bilder Button (wenn verfuegbar)
        if HAS_EMBEDDED_IMAGES:
            self.embedded_btn = ttk.Button(btn_frame, text="Eingebettete Bilder cachen (test1-8)", 
                                          command=self.cache_embedded_images)
            self.embedded_btn.pack(side=tk.LEFT, padx=5)
            # Status-Labels aktualisieren
            for i in range(MAX_SLOTS):
                if (i + 1) in EMBEDDED_IMAGES:
                    self.image_labels[i].config(text=f"test{i+1} (eingebettet)")
                    self.status_labels[i].config(text="Bereit", foreground="blue")
        
        # Alle cachen Button
        ttk.Button(btn_frame, text="Alle ausgewaehlten cachen", command=self.cache_all_images).pack(side=tk.LEFT, padx=5)
    
    def create_telemetry_tab(self):
        """Tab fuer Telemetrie"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Telemetrie")
        
        # Einstellungen
        settings_frame = ttk.LabelFrame(tab, text="Telemetrie-Einstellungen", padding="10")
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(settings_frame, text="Telemetrie-Adresse:").pack(side=tk.LEFT)
        self.telemetry_entry = ttk.Entry(settings_frame, width=25)
        self.telemetry_entry.pack(side=tk.LEFT, padx=5)
        self.telemetry_entry.insert(0, DEFAULT_TELEMETRY)
        
        self.start_btn = ttk.Button(settings_frame, text="Starten", command=self.start_telemetry)
        self.start_btn.pack(side=tk.LEFT, padx=10)
        
        self.stop_btn = ttk.Button(settings_frame, text="Stoppen", command=self.stop_telemetry, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        
        # Status
        status_frame = ttk.LabelFrame(tab, text="Status", padding="10")
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.tele_status = ttk.Label(status_frame, text="Telemetrie: Inaktiv", font=("Arial", 11))
        self.tele_status.pack(anchor=tk.W)
        
        self.image_status = ttk.Label(status_frame, text="Aktuelles Bild: -", font=("Arial", 11))
        self.image_status.pack(anchor=tk.W)
        
        # Bild-Zuordnung
        legend_frame = ttk.LabelFrame(tab, text="Bild-Zuordnung", padding="10")
        legend_frame.pack(fill=tk.X, padx=10, pady=5)
        
        legend = """Bild 1: Motor laeuft (Normal)       Bild 5: Beide Tueren + Absenkung
Bild 2: Nebelscheinwerfer           Bild 6: Nach Absenkung
Bild 3: Nebelschlussleuchte         Bild 7: Zuendung AN, Motor AUS
Bild 4: Vordere Tuer (2 Sek)        Bild 8: Zuendung AN (3 Sek)"""
        
        ttk.Label(legend_frame, text=legend, font=("Consolas", 9)).pack()
        
        # Diagnose
        ttk.Button(tab, text="Telemetrie-Diagnose", command=self.show_diagnosis).pack(pady=10)
    
    def create_info_tab(self):
        """Info-Tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Info")
        
        info_text = f"""
{APP_NAME} v{APP_VERSION}

ANLEITUNG:

1. BILDER CACHEN (Tab "Bilder Cachen")
   - ESP32 verbinden
   - Fuer jedes Bild (1-8): "Waehlen" klicken und Bild auswaehlen
   - "Cachen" klicken um das Bild auf den ESP32 zu laden
   - Oder "Alle Bilder cachen" fuer alle auf einmal

2. TELEMETRIE STARTEN (Tab "Telemetrie")
   - Telemetrie-Adresse eingeben (Standard: {DEFAULT_TELEMETRY})
   - "Starten" klicken
   - Das Spiel "The Bus" starten mit aktivierter Telemetrie

WICHTIG:
- Zuerst alle Bilder cachen, dann Telemetrie starten
- Die Telemetrie muss im Spiel aktiviert sein
- Der ESP32 muss mit den richtigen Bildern gecached sein

BILD-LOGIK:
- Bild 8 erscheint wenn die Zuendung eingeschaltet wird (3 Sek)
- Bild 7 bei Zuendung an, Motor aus
- Bild 1 ist der Normalzustand (Motor laeuft)
- Bild 2/3 bei Nebel-Lichtern
- Bild 4-6 bei Tuer-/Absenkungssequenzen
"""
        
        text = scrolledtext.ScrolledText(tab, font=("Arial", 10), wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, info_text)
        text.config(state=tk.DISABLED)
    
    def refresh_ports(self):
        """Aktualisiert Port-Liste"""
        if not SERIAL_AVAILABLE:
            self.port_combo['values'] = ["PySerial fehlt!"]
            return
        
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports if ports else ["Keine Ports"]
        if ports:
            self.port_combo.current(0)
    
    def log(self, message: str):
        """Log-Nachricht hinzufuegen"""
        def update():
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
        self.root.after(0, update)
    
    def toggle_connection(self):
        """Verbindung umschalten"""
        if self.esp32.connected:
            self.esp32.disconnect()
            self.connect_btn.config(text="Verbinden")
            self.conn_status.config(text="Nicht verbunden", foreground="red")
        else:
            port = self.port_combo.get()
            if not port or "fehlt" in port or "Keine" in port:
                messagebox.showerror("Fehler", "Bitte Port auswaehlen!")
                return
            
            if self.esp32.connect(port, DEFAULT_BAUDRATE):
                self.connect_btn.config(text="Trennen")
                self.conn_status.config(text="Verbunden", foreground="green")
            else:
                messagebox.showerror("Fehler", "Verbindung fehlgeschlagen!")
    
    def select_image(self, idx: int):
        """Bild auswaehlen"""
        filetypes = [
            ("Bilder", "*.png *.jpg *.jpeg *.bmp *.gif"),
            ("Alle Dateien", "*.*")
        ]
        path = filedialog.askopenfilename(filetypes=filetypes)
        
        if path:
            self.image_paths[idx] = path
            filename = os.path.basename(path)
            self.image_labels[idx].config(text=filename[:18] + "..." if len(filename) > 18 else filename)
            self.status_labels[idx].config(text="Bereit", foreground="blue")
    
    def cache_image(self, idx: int):
        """Einzelnes Bild cachen"""
        if not self.esp32.connected:
            messagebox.showerror("Fehler", "ESP32 nicht verbunden!")
            return
        
        if not self.image_paths[idx]:
            messagebox.showerror("Fehler", f"Kein Bild fuer Slot {idx + 1} ausgewaehlt!")
            return
        
        if not PIL_AVAILABLE:
            messagebox.showerror("Fehler", "Pillow nicht installiert!\npip install pillow")
            return
        
        self.status_labels[idx].config(text="Konvertiere...", foreground="orange")
        self.root.update()
        
        # Konvertieren
        rgb565_data = convert_to_rgb565(self.image_paths[idx])
        if not rgb565_data:
            self.status_labels[idx].config(text="Fehler!", foreground="red")
            messagebox.showerror("Fehler", "Bildkonvertierung fehlgeschlagen!")
            return
        
        self.status_labels[idx].config(text="Sende...", foreground="orange")
        self.root.update()
        
        # Progress Callback
        def progress(p):
            self.progress_var.set(p)
            self.root.update()
        
        # Cachen
        if self.esp32.cache_image(idx, rgb565_data, progress_callback=progress):
            self.status_labels[idx].config(text="Gecached!", foreground="green")
        else:
            self.status_labels[idx].config(text="Fehler!", foreground="red")
        
        self.progress_var.set(0)
    
    def cache_all_images(self):
        """Alle Bilder cachen"""
        if not self.esp32.connected:
            messagebox.showerror("Fehler", "ESP32 nicht verbunden!")
            return
        
        # Pruefen welche Bilder ausgewaehlt sind
        selected = [(i, p) for i, p in enumerate(self.image_paths) if p]
        
        if not selected:
            messagebox.showerror("Fehler", "Keine Bilder ausgewaehlt!")
            return
        
        self.log(f"Cache {len(selected)} Bilder...")
        
        for idx, path in selected:
            self.cache_image(idx)
            time.sleep(0.5)
        
        self.log("Alle Bilder gecached!")
        messagebox.showinfo("Fertig", f"{len(selected)} Bilder erfolgreich gecached!")
    
    def cache_embedded_images(self):
        """Cached alle eingebetteten Bilder (test1-test8)"""
        if not self.esp32.connected:
            messagebox.showerror("Fehler", "ESP32 nicht verbunden!")
            return
        
        if not HAS_EMBEDDED_IMAGES:
            messagebox.showerror("Fehler", "Keine eingebetteten Bilder gefunden!")
            return
        
        self.log("Cache alle eingebetteten Bilder (test1-test8)...")
        
        success_count = 0
        for slot in range(1, MAX_SLOTS + 1):
            idx = slot - 1
            
            self.status_labels[idx].config(text="Dekomprimiere...", foreground="orange")
            self.root.update()
            
            # Eingebettetes Bild dekomprimieren
            rgb565_data = decompress_embedded_image(slot)
            
            if not rgb565_data:
                self.status_labels[idx].config(text="Nicht gefunden", foreground="red")
                self.log(f"Bild {slot} nicht gefunden!")
                continue
            
            self.status_labels[idx].config(text="Sende...", foreground="orange")
            self.root.update()
            
            # Progress Callback
            def progress(p):
                self.progress_var.set(p)
                self.root.update()
            
            # Cachen (idx ist 0-basiert)
            if self.esp32.cache_image(idx, rgb565_data, progress_callback=progress):
                self.status_labels[idx].config(text="Gecached!", foreground="green")
                success_count += 1
            else:
                self.status_labels[idx].config(text="Fehler!", foreground="red")
            
            self.progress_var.set(0)
            time.sleep(0.3)
        
        self.log(f"Fertig! {success_count}/{MAX_SLOTS} Bilder gecached.")
        messagebox.showinfo("Fertig", f"{success_count} von {MAX_SLOTS} Bildern erfolgreich gecached!")
    
    def start_telemetry(self):
        """Startet Telemetrie"""
        if not self.esp32.connected:
            messagebox.showerror("Fehler", "ESP32 nicht verbunden!\nBitte zuerst im Tab 'Bilder Cachen' verbinden.")
            return
        
        if not REQUESTS_AVAILABLE:
            messagebox.showerror("Fehler", "Requests nicht installiert!\npip install requests")
            return
        
        telemetry_addr = self.telemetry_entry.get()
        if not telemetry_addr:
            messagebox.showerror("Fehler", "Telemetrie-Adresse eingeben!")
            return
        
        self.telemetry.telemetry_url = f"http://{telemetry_addr}"
        self.telemetry.running = True
        
        self.telemetry_thread = threading.Thread(target=self.run_telemetry, daemon=True)
        self.telemetry_thread.start()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.tele_status.config(text="Telemetrie: Aktiv", foreground="green")
        
        self.log("Telemetrie gestartet")
    
    def run_telemetry(self):
        """Telemetrie-Thread"""
        last_image = -1
        
        while self.telemetry.running:
            try:
                data = self.telemetry.get_telemetry()
                
                if data:
                    self.telemetry.parse_telemetry(data)
                    target = self.telemetry.determine_image()
                    
                    if target != self.telemetry.current_image:
                        self.log(f"Wechsel zu Bild {target}")
                        slot = target - 1
                        if self.esp32.show_image(slot, self.telemetry.bus_state.gear, self.telemetry.bus_state.speed):
                            self.telemetry.current_image = target
                    
                    if target != last_image:
                        self.root.after(0, lambda t=target: self.image_status.config(text=f"Aktuelles Bild: {t}"))
                        last_image = target
                
            except Exception as e:
                self.log(f"Fehler: {e}")
            
            time.sleep(0.1)
    
    def stop_telemetry(self):
        """Stoppt Telemetrie"""
        self.telemetry.running = False
        
        if self.telemetry_thread:
            self.telemetry_thread.join(timeout=2)
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.tele_status.config(text="Telemetrie: Inaktiv", foreground="black")
        
        self.log("Telemetrie gestoppt")
    
    def show_diagnosis(self):
        """Zeigt Diagnose"""
        telemetry_addr = self.telemetry_entry.get()
        if not telemetry_addr:
            messagebox.showerror("Fehler", "Telemetrie-Adresse eingeben!")
            return
        
        if not REQUESTS_AVAILABLE:
            messagebox.showerror("Fehler", "Requests nicht installiert!")
            return
        
        self.log("Lade Telemetrie-Diagnose...")
        
        try:
            base_url = f"http://{telemetry_addr}"
            
            # Fahrzeug finden
            response = requests.get(f"{base_url}/vehicles", timeout=2)
            vehicles = response.json()
            
            if not vehicles:
                messagebox.showerror("Fehler", "Keine Fahrzeuge gefunden!")
                return
            
            response = requests.get(f"{base_url}/player", timeout=2)
            player = response.json()
            
            vehicle = None
            if player.get("Mode") == "Vehicle":
                vehicle = player.get("CurrentVehicle")
            elif vehicles:
                vehicle = vehicles[0] if isinstance(vehicles[0], str) else vehicles[0].get("Id")
            
            if not vehicle:
                messagebox.showerror("Fehler", "Kein aktives Fahrzeug!")
                return
            
            # Daten abrufen
            url = f"{base_url}/vehicles/{vehicle}"
            params = {"vars": "Buttons,AllLamps"}
            response = requests.get(url, params=params, timeout=2)
            data = response.json()
            
            lamps = data.get("AllLamps", {})
            buttons = data.get("Buttons", [])
            
            # Fenster erstellen
            diag = tk.Toplevel(self.root)
            diag.title("Telemetrie-Diagnose")
            diag.geometry("500x400")
            
            text = scrolledtext.ScrolledText(diag, font=("Consolas", 9))
            text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            text.insert(tk.END, "=== AKTIVE LAMPEN ===\n\n")
            active = [(k, v) for k, v in sorted(lamps.items()) if float(v) > 0]
            for name, val in active:
                text.insert(tk.END, f"  {name}: {val}\n")
            
            if not active:
                text.insert(tk.END, "  (keine)\n")
            
            text.insert(tk.END, f"\n=== ALLE LAMPEN ({len(lamps)}) ===\n\n")
            for name, val in sorted(lamps.items())[:30]:
                status = "AN" if float(val) > 0 else "aus"
                text.insert(tk.END, f"  {name}: {val} ({status})\n")
            
            if len(lamps) > 30:
                text.insert(tk.END, f"  ... und {len(lamps) - 30} weitere\n")
            
            text.insert(tk.END, "\n=== BUTTONS ===\n\n")
            for btn in buttons:
                text.insert(tk.END, f"  {btn.get('Name')}: {btn.get('State')}\n")
            
            self.log(f"Diagnose: {len(lamps)} Lampen, {len(buttons)} Buttons")
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Diagnose fehlgeschlagen:\n{e}")
    
    def on_closing(self):
        """Beim Schliessen"""
        self.telemetry.running = False
        self.esp32.disconnect()
        self.root.destroy()
    
    def run(self):
        """Startet die App"""
        self.root.mainloop()


# ============================================================================
# Hauptprogramm
# ============================================================================

def main():
    """Einstiegspunkt"""
    # Abhaengigkeiten pruefen
    missing = []
    if not SERIAL_AVAILABLE:
        missing.append("pyserial")
    if not REQUESTS_AVAILABLE:
        missing.append("requests")
    if not PIL_AVAILABLE:
        missing.append("pillow")
    
    if missing:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Fehlende Pakete",
            f"Bitte installieren Sie:\n\npip install {' '.join(missing)}"
        )
        root.destroy()
        return
    
    app = BusDisplayApp()
    app.run()


if __name__ == "__main__":
    main()
