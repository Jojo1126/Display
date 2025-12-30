#!/usr/bin/env python3
"""
Bus Simulator Display - Telemetry Controller
============================================

Dieses Skript verbindet sich mit der Telemetrie von "The Bus" und
steuert das ESP32-Display basierend auf dem Spielzustand.

Verwendung:
    python telemetry_display.py --port COM3 --telemetry 192.168.2.216:37337

Autor: Bus Display Project
"""

import argparse
import asyncio
import json
import time
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
import serial
import serial.tools.list_ports
import requests
from requests.exceptions import RequestException

# ============================================================================
# Konfiguration
# ============================================================================

class DisplayImage(Enum):
    """Bild-Zuordnungen für verschiedene Zustände"""
    NORMAL = 1          # Bild 1: Motor läuft (Normalzustand)
    FOG_LIGHTS = 2      # Bild 2: Nebelscheinwerfer an
    REAR_FOG = 3        # Bild 3: Nebelschlussleuchte an
    FRONT_DOOR = 4      # Bild 4: Vordere Tür öffnet
    DOORS_KNEELING = 5  # Bild 5: Beide Türen öffnen + Bus senkt sich / Türen schließen
    AFTER_KNEELING = 6  # Bild 6: Nach Absenkung
    IGNITION_NO_ENGINE = 7  # Bild 7: Zündung an, Motor aus
    IGNITION_START = 8  # Bild 8: Zündung gerade eingeschaltet (3 Sek)


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
    gear: int = 0  # -1=R, 0=N, 1+=Gänge
    speed: int = 0
    connected: bool = False


class TelemetryDisplayController:
    """Hauptcontroller für die Display-Steuerung"""
    
    def __init__(self, telemetry_host: str, telemetry_port: int, serial_port: str, baudrate: int = 921600):
        self.telemetry_url = f"http://{telemetry_host}:{telemetry_port}"
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        
        self.bus_state = BusState()
        self.current_image = -1
        self.current_vehicle: Optional[str] = None
        
        # Timing für Zustandsübergänge
        self.ignition_start_time: Optional[float] = None
        self.front_door_open_time: Optional[float] = None
        self.kneeling_complete_time: Optional[float] = None
        self.last_state_change_time: float = 0
        
        # Vorheriger Zustand für Änderungserkennung
        self.prev_ignition = False
        self.prev_front_door = False
        self.prev_kneeling = False
        self.prev_both_doors = False
        
        # Display-Zustand
        self.showing_ignition_animation = False
        self.showing_door_animation = False
        self.in_kneeling_sequence = False
        
    def connect_serial(self) -> bool:
        """Verbindung zum ESP32 herstellen"""
        try:
            self.serial = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                timeout=1
            )
            time.sleep(2)  # Warten auf ESP32-Reset
            print(f"✓ Seriell verbunden: {self.serial_port} @ {self.baudrate} baud")
            
            # Warten auf "ACK" vom ESP32
            start = time.time()
            while time.time() - start < 5:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    print(f"  ESP32: {line}")
                    if "ACK" in line or "Ready" in line:
                        print("✓ ESP32 bereit!")
                        return True
            
            print("⚠ ESP32 antwortet nicht, aber Verbindung besteht")
            return True
            
        except Exception as e:
            print(f"✗ Seriell-Fehler: {e}")
            return False
    
    def get_current_vehicle(self) -> Optional[str]:
        """Aktuelles Fahrzeug vom Spiel abrufen"""
        try:
            # Erst prüfen ob Fahrzeuge verfügbar sind
            response = requests.get(f"{self.telemetry_url}/vehicles", timeout=1)
            vehicles = response.json()
            
            if not vehicles or len(vehicles) == 0:
                return None
            
            # Spieler-Info abrufen
            response = requests.get(f"{self.telemetry_url}/player", timeout=1)
            player_data = response.json()
            
            if player_data.get("Mode") == "Vehicle":
                return player_data.get("CurrentVehicle")
            
            return None
            
        except RequestException:
            return None
    
    def get_telemetry_data(self) -> Optional[Dict[str, Any]]:
        """Telemetrie-Daten vom Spiel abrufen"""
        if not self.current_vehicle:
            self.current_vehicle = self.get_current_vehicle()
            if not self.current_vehicle:
                return None
        
        try:
            url = f"{self.telemetry_url}/vehicles/{self.current_vehicle}"
            params = {"vars": "Buttons,AllLamps,IsPlayerControlled,BusLogic,Velocity,Gear"}
            response = requests.get(url, params=params, timeout=1)
            data = response.json()
            
            # Prüfen ob Spieler noch im Fahrzeug ist
            if data.get("IsPlayerControlled") == "false":
                self.current_vehicle = None
                return None
            
            return data
            
        except RequestException:
            self.current_vehicle = None
            return None
    
    def parse_telemetry(self, data: Dict[str, Any]) -> None:
        """Telemetrie-Daten in BusState umwandeln"""
        lamps = data.get("AllLamps", {})
        buttons = data.get("Buttons", [])
        
        # Vorherige Zustände speichern
        self.prev_ignition = self.bus_state.ignition_on
        self.prev_front_door = self.bus_state.front_door_open
        self.prev_kneeling = self.bus_state.kneeling
        self.prev_both_doors = self.bus_state.front_door_open and self.bus_state.rear_door_open
        
        # Lampen auswerten (Wert > 0 = AN)
        # Mögliche Lampennamen - wir probieren verschiedene Varianten
        ignition_lamps = ["LED Ignition", "LED Zuendung", "Ignition", "LED Power"]
        engine_lamps = ["LED Engine", "LED Motor", "Engine Running", "LED EngineRunning"]
        fog_lamps = ["LED FogLight", "LED Nebelscheinwerfer", "FogLight", "LED FogLightFront"]
        rear_fog_lamps = ["LED RearFogLight", "LED Nebelschlussleuchte", "RearFogLight", "LED FogLightRear"]
        kneeling_lamps = ["LED Kneeling", "LED Absenkung", "Kneeling", "LED BusKneeling"]
        
        def check_lamp(lamp_names: list) -> bool:
            for name in lamp_names:
                if name in lamps and float(lamps[name]) > 0:
                    return True
            return False
        
        # Zündung und Motor
        self.bus_state.ignition_on = check_lamp(ignition_lamps)
        self.bus_state.engine_running = check_lamp(engine_lamps)
        
        # Wenn kein expliziter Motor-Status, schätzen wir basierend auf anderen Daten
        # Motor läuft wahrscheinlich wenn Gang nicht N ist oder Geschwindigkeit > 0
        
        # Lichter
        self.bus_state.fog_lights_on = check_lamp(fog_lamps)
        self.bus_state.rear_fog_on = check_lamp(rear_fog_lamps)
        
        # Kneeling (Absenkung)
        self.bus_state.kneeling = check_lamp(kneeling_lamps)
        
        # Türen aus Lampen oder Buttons
        door1_lamps = ["ButtonLight Door 1", "LED Door1", "Door1Open", "LED DoorFront"]
        door2_lamps = ["ButtonLight Door 2", "LED Door2", "Door2Open", "LED DoorRear"]
        door3_lamps = ["ButtonLight Door 3", "LED Door3", "Door3Open"]
        
        self.bus_state.front_door_open = check_lamp(door1_lamps)
        self.bus_state.rear_door_open = check_lamp(door2_lamps) or check_lamp(door3_lamps)
        
        # Buttons auswerten für Gänge
        for button in buttons:
            if button.get("Name") == "GearSwitch":
                state = button.get("State", "Neutral")
                if state == "Drive":
                    self.bus_state.gear = 1
                elif state == "Reverse":
                    self.bus_state.gear = -1
                else:
                    self.bus_state.gear = 0
        
        # Geschwindigkeit (falls verfügbar)
        velocity = data.get("Velocity", {})
        if isinstance(velocity, dict):
            speed = velocity.get("Speed", 0)
            self.bus_state.speed = int(abs(float(speed)) * 3.6)  # m/s zu km/h
        elif isinstance(velocity, (int, float)):
            self.bus_state.speed = int(abs(float(velocity)) * 3.6)
        
        # Alternative: Geschwindigkeit direkt
        if "Speed" in data:
            self.bus_state.speed = int(abs(float(data["Speed"])))
        
        self.bus_state.connected = True
    
    def determine_display_image(self) -> int:
        """Bestimmt welches Bild angezeigt werden soll basierend auf der Logik"""
        now = time.time()
        
        # ============================================================
        # PRIORITÄT 1: Zündung gerade eingeschaltet (3 Sekunden Bild 8)
        # ============================================================
        if self.bus_state.ignition_on and not self.prev_ignition:
            # Zündung wurde gerade eingeschaltet
            self.ignition_start_time = now
            self.showing_ignition_animation = True
            print("→ Zündung eingeschaltet - zeige Bild 8 für 3 Sekunden")
        
        if self.showing_ignition_animation:
            if self.ignition_start_time and (now - self.ignition_start_time) < 3.0:
                return DisplayImage.IGNITION_START.value  # Bild 8
            else:
                self.showing_ignition_animation = False
                print("→ Zündungs-Animation beendet")
        
        # ============================================================
        # PRIORITÄT 2: Zündung an, Motor aus (Bild 7)
        # ============================================================
        if self.bus_state.ignition_on and not self.bus_state.engine_running:
            return DisplayImage.IGNITION_NO_ENGINE.value  # Bild 7
        
        # Ab hier: Motor läuft (oder wir nehmen an dass er läuft)
        
        # ============================================================
        # PRIORITÄT 3: Tür-Sequenzen
        # ============================================================
        
        # Vordere Tür öffnet (Bild 4 für 2 Sekunden, dann Bild 5)
        if self.bus_state.front_door_open and not self.prev_front_door:
            # Vordere Tür wurde gerade geöffnet
            self.front_door_open_time = now
            self.showing_door_animation = True
            print("→ Vordere Tür öffnet - zeige Bild 4 für 2 Sekunden")
        
        if self.showing_door_animation and self.bus_state.front_door_open:
            if self.front_door_open_time and (now - self.front_door_open_time) < 2.0:
                return DisplayImage.FRONT_DOOR.value  # Bild 4
            else:
                self.showing_door_animation = False
        
        # Beide Türen offen + Absenkung (Bild 5)
        both_doors_open = self.bus_state.front_door_open and self.bus_state.rear_door_open
        
        if both_doors_open and self.bus_state.kneeling:
            if not self.in_kneeling_sequence:
                self.in_kneeling_sequence = True
                print("→ Beide Türen offen + Absenkung - zeige Bild 5")
            return DisplayImage.DOORS_KNEELING.value  # Bild 5
        
        # Nach Absenkung (Bild 6) - wenn Kneeling gerade beendet wurde
        if self.in_kneeling_sequence and not self.bus_state.kneeling and both_doors_open:
            if not self.kneeling_complete_time:
                self.kneeling_complete_time = now
                print("→ Absenkung abgeschlossen - zeige Bild 6")
            return DisplayImage.AFTER_KNEELING.value  # Bild 6
        
        # Türen schließen (Bild 5)
        if self.in_kneeling_sequence and not both_doors_open:
            if self.prev_both_doors:
                print("→ Türen schließen - zeige Bild 5")
                self.kneeling_complete_time = None
            
            # Wenn alle Türen geschlossen, Sequenz beenden
            if not self.bus_state.front_door_open and not self.bus_state.rear_door_open:
                self.in_kneeling_sequence = False
                print("→ Türen geschlossen - zurück zu Normalzustand")
            else:
                return DisplayImage.DOORS_KNEELING.value  # Bild 5
        
        # ============================================================
        # PRIORITÄT 4: Lichter
        # ============================================================
        
        # Nebelscheinwerfer (Bild 2)
        if self.bus_state.fog_lights_on:
            return DisplayImage.FOG_LIGHTS.value  # Bild 2
        
        # Nebelschlussleuchte (Bild 3)
        if self.bus_state.rear_fog_on:
            return DisplayImage.REAR_FOG.value  # Bild 3
        
        # ============================================================
        # STANDARD: Motor läuft, Normalzustand (Bild 1)
        # ============================================================
        return DisplayImage.NORMAL.value  # Bild 1
    
    def send_display_command(self, image_slot: int, gear: int = 0, speed: int = 0) -> bool:
        """Sendet SHOW-Befehl an ESP32"""
        if not self.serial or not self.serial.is_open:
            return False
        
        try:
            # SHOW:[slot]:[gear]:[speed]
            # Slot ist 0-basiert (Bild 1 = Slot 0)
            slot = image_slot - 1  # Umrechnung: Bild 1 → Slot 0
            
            if slot < 0 or slot > 7:
                print(f"⚠ Ungültiger Slot: {slot}")
                return False
            
            command = f"SHOW:{slot}:{gear}:{speed}\n"
            self.serial.write(command.encode())
            
            return True
            
        except Exception as e:
            print(f"✗ Sende-Fehler: {e}")
            return False
    
    def read_serial_response(self) -> None:
        """Liest Antworten vom ESP32"""
        if not self.serial:
            return
            
        try:
            while self.serial.in_waiting:
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"  ESP32: {line}")
        except Exception:
            pass
    
    async def run(self) -> None:
        """Hauptschleife"""
        print("\n" + "="*60)
        print("Bus Simulator Display - Telemetry Controller")
        print("="*60)
        print(f"Telemetrie: {self.telemetry_url}")
        print(f"Seriell: {self.serial_port} @ {self.baudrate} baud")
        print("="*60 + "\n")
        
        # Seriell verbinden
        if not self.connect_serial():
            print("✗ Konnte nicht mit ESP32 verbinden!")
            return
        
        print("\n→ Warte auf Spielverbindung...")
        print("  (Stellen Sie sicher, dass Telemetrie im Spiel aktiviert ist)\n")
        
        last_telemetry_time = 0
        connection_lost_printed = False
        
        try:
            while True:
                now = time.time()
                
                # Telemetrie alle 100ms abrufen
                if now - last_telemetry_time >= 0.1:
                    last_telemetry_time = now
                    
                    data = self.get_telemetry_data()
                    
                    if data:
                        if not self.bus_state.connected or connection_lost_printed:
                            print("✓ Verbunden mit Spiel!")
                            connection_lost_printed = False
                        
                        self.parse_telemetry(data)
                        
                        # Bild bestimmen
                        target_image = self.determine_display_image()
                        
                        # Nur senden wenn sich das Bild ändert
                        if target_image != self.current_image:
                            print(f"→ Wechsel zu Bild {target_image}")
                            if self.send_display_command(
                                target_image, 
                                self.bus_state.gear, 
                                self.bus_state.speed
                            ):
                                self.current_image = target_image
                        
                        # Telemetrie aktualisieren (Geschwindigkeit etc.) alle 500ms
                        elif now % 0.5 < 0.1:
                            self.send_display_command(
                                self.current_image,
                                self.bus_state.gear,
                                self.bus_state.speed
                            )
                    
                    else:
                        if self.bus_state.connected and not connection_lost_printed:
                            print("⚠ Verbindung zum Spiel verloren - warte...")
                            connection_lost_printed = True
                        self.bus_state.connected = False
                
                # ESP32-Antworten lesen
                self.read_serial_response()
                
                # Kurze Pause
                await asyncio.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n\n→ Beende...")
        finally:
            if self.serial and self.serial.is_open:
                self.serial.close()
            print("✓ Beendet")


def list_serial_ports() -> None:
    """Listet verfügbare serielle Ports auf"""
    ports = serial.tools.list_ports.comports()
    print("\nVerfügbare serielle Ports:")
    print("-" * 40)
    
    if not ports:
        print("  Keine Ports gefunden!")
        print("  Ist der ESP32 angeschlossen?")
    else:
        for port in ports:
            print(f"  {port.device}: {port.description}")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Bus Simulator Display - Telemetry Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python telemetry_display.py --port COM3
  python telemetry_display.py --port /dev/ttyUSB0 --telemetry 192.168.2.216:37337
  python telemetry_display.py --list-ports

Bild-Zuordnung:
  Bild 1: Motor läuft (Normalzustand)
  Bild 2: Nebelscheinwerfer an
  Bild 3: Nebelschlussleuchte an
  Bild 4: Vordere Tür öffnet (2 Sek)
  Bild 5: Beide Türen + Absenkung / Türen schließen
  Bild 6: Nach Absenkung
  Bild 7: Zündung an, Motor aus
  Bild 8: Zündung eingeschaltet (3 Sek)
        """
    )
    
    parser.add_argument(
        "--port", "-p",
        help="Serieller Port (z.B. COM3 oder /dev/ttyUSB0)"
    )
    
    parser.add_argument(
        "--telemetry", "-t",
        default="192.168.2.216:37337",
        help="Telemetrie-Adresse (Standard: 192.168.2.216:37337)"
    )
    
    parser.add_argument(
        "--baudrate", "-b",
        type=int,
        default=921600,
        help="Baudrate (Standard: 921600)"
    )
    
    parser.add_argument(
        "--list-ports", "-l",
        action="store_true",
        help="Verfügbare serielle Ports auflisten"
    )
    
    args = parser.parse_args()
    
    if args.list_ports:
        list_serial_ports()
        return
    
    if not args.port:
        print("Fehler: Bitte geben Sie einen seriellen Port an!")
        print("Verwenden Sie --list-ports um verfügbare Ports zu sehen.")
        list_serial_ports()
        sys.exit(1)
    
    # Telemetrie-Adresse parsen
    telemetry_parts = args.telemetry.split(":")
    telemetry_host = telemetry_parts[0]
    telemetry_port = int(telemetry_parts[1]) if len(telemetry_parts) > 1 else 37337
    
    # Controller starten
    controller = TelemetryDisplayController(
        telemetry_host=telemetry_host,
        telemetry_port=telemetry_port,
        serial_port=args.port,
        baudrate=args.baudrate
    )
    
    asyncio.run(controller.run())


if __name__ == "__main__":
    main()
