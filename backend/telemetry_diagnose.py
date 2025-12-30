#!/usr/bin/env python3
"""
Bus Telemetrie Diagnose-Tool
============================

Dieses Tool zeigt alle verfügbaren Telemetrie-Felder von "The Bus" an.
Nützlich um die korrekten Feldnamen für Ihr Setup herauszufinden.

Verwendung:
    python telemetry_diagnose.py --telemetry 192.168.2.216:37337
"""

import argparse
import json
import time
import sys
import requests
from requests.exceptions import RequestException


def get_all_telemetry(base_url: str) -> dict:
    """Holt alle verfügbaren Telemetrie-Daten"""
    result = {
        "vehicles": None,
        "player": None,
        "vehicle_data": None,
        "all_lamps": {},
        "all_buttons": []
    }
    
    # Fahrzeuge abrufen
    try:
        response = requests.get(f"{base_url}/vehicles", timeout=2)
        result["vehicles"] = response.json()
    except Exception as e:
        print(f"⚠ Fehler bei /vehicles: {e}")
    
    # Spieler-Info abrufen
    try:
        response = requests.get(f"{base_url}/player", timeout=2)
        result["player"] = response.json()
    except Exception as e:
        print(f"⚠ Fehler bei /player: {e}")
    
    # Aktuelles Fahrzeug ermitteln
    current_vehicle = None
    if result["player"] and result["player"].get("Mode") == "Vehicle":
        current_vehicle = result["player"].get("CurrentVehicle")
    
    if not current_vehicle and result["vehicles"] and len(result["vehicles"]) > 0:
        # Erstes verfügbares Fahrzeug verwenden
        current_vehicle = result["vehicles"][0] if isinstance(result["vehicles"][0], str) else result["vehicles"][0].get("Id")
    
    if current_vehicle:
        # Alle verfügbaren Variablen abrufen
        try:
            url = f"{base_url}/vehicles/{current_vehicle}"
            params = {"vars": "Buttons,AllLamps,IsPlayerControlled,BusLogic,Velocity,Gear,Speed,Position"}
            response = requests.get(url, params=params, timeout=2)
            result["vehicle_data"] = response.json()
            
            if "AllLamps" in result["vehicle_data"]:
                result["all_lamps"] = result["vehicle_data"]["AllLamps"]
            
            if "Buttons" in result["vehicle_data"]:
                result["all_buttons"] = result["vehicle_data"]["Buttons"]
                
        except Exception as e:
            print(f"⚠ Fehler bei Fahrzeugdaten: {e}")
    
    return result


def print_telemetry(data: dict) -> None:
    """Gibt die Telemetrie-Daten formatiert aus"""
    
    print("\n" + "="*70)
    print("BUS TELEMETRIE DIAGNOSE")
    print("="*70)
    
    # Verbindungsstatus
    print("\n📡 VERBINDUNG")
    print("-" * 40)
    
    if data["vehicles"]:
        print(f"  ✓ Fahrzeuge gefunden: {len(data['vehicles'])}")
    else:
        print("  ✗ Keine Fahrzeuge gefunden")
    
    if data["player"]:
        print(f"  ✓ Spieler-Modus: {data['player'].get('Mode', 'Unbekannt')}")
        if data["player"].get("Mode") == "Vehicle":
            print(f"  ✓ Aktuelles Fahrzeug: {data['player'].get('CurrentVehicle', 'Unbekannt')}")
    else:
        print("  ✗ Keine Spieler-Info")
    
    # Lampen
    print("\n💡 ALLE LAMPEN (AllLamps)")
    print("-" * 40)
    
    if data["all_lamps"]:
        # Sortieren nach Name
        sorted_lamps = sorted(data["all_lamps"].items())
        
        # Aktive Lampen zuerst
        active_lamps = [(k, v) for k, v in sorted_lamps if float(v) > 0]
        inactive_lamps = [(k, v) for k, v in sorted_lamps if float(v) <= 0]
        
        if active_lamps:
            print("\n  🟢 AKTIVE LAMPEN:")
            for name, value in active_lamps:
                print(f"    • {name}: {value}")
        
        print(f"\n  ⚪ INAKTIVE LAMPEN ({len(inactive_lamps)} Stück):")
        for name, value in inactive_lamps[:30]:  # Nur erste 30
            print(f"    • {name}: {value}")
        
        if len(inactive_lamps) > 30:
            print(f"    ... und {len(inactive_lamps) - 30} weitere")
    else:
        print("  ✗ Keine Lampen-Daten")
    
    # Buttons
    print("\n🔘 ALLE BUTTONS")
    print("-" * 40)
    
    if data["all_buttons"]:
        for button in data["all_buttons"]:
            name = button.get("Name", "Unbekannt")
            state = button.get("State", "Unbekannt")
            print(f"  • {name}: {state}")
    else:
        print("  ✗ Keine Button-Daten")
    
    # Sonstige Daten
    print("\n📊 WEITERE DATEN")
    print("-" * 40)
    
    if data["vehicle_data"]:
        for key, value in data["vehicle_data"].items():
            if key not in ["AllLamps", "Buttons"]:
                if isinstance(value, dict):
                    print(f"  • {key}:")
                    for k, v in value.items():
                        print(f"      {k}: {v}")
                else:
                    print(f"  • {key}: {value}")
    
    # Empfehlungen
    print("\n" + "="*70)
    print("📝 EMPFOHLENE FELDNAMEN FÜR DISPLAY-LOGIK")
    print("="*70)
    
    # Suche nach relevanten Feldern
    lamps = data.get("all_lamps", {})
    
    suggestions = {
        "Zündung": [],
        "Motor": [],
        "Nebelscheinwerfer": [],
        "Nebelschlussleuchte": [],
        "Absenkung/Kneeling": [],
        "Tür 1 (vorne)": [],
        "Tür 2 (hinten)": []
    }
    
    for name in lamps.keys():
        name_lower = name.lower()
        
        if "ignition" in name_lower or "zuend" in name_lower or "power" in name_lower:
            suggestions["Zündung"].append(name)
        
        if "engine" in name_lower or "motor" in name_lower:
            suggestions["Motor"].append(name)
        
        if "fog" in name_lower or "nebel" in name_lower:
            if "rear" in name_lower or "schluss" in name_lower or "back" in name_lower:
                suggestions["Nebelschlussleuchte"].append(name)
            else:
                suggestions["Nebelscheinwerfer"].append(name)
        
        if "kneel" in name_lower or "absenk" in name_lower or "lower" in name_lower:
            suggestions["Absenkung/Kneeling"].append(name)
        
        if "door" in name_lower or "tuer" in name_lower or "tür" in name_lower:
            if "1" in name or "front" in name_lower or "vorn" in name_lower:
                suggestions["Tür 1 (vorne)"].append(name)
            elif "2" in name or "rear" in name_lower or "hint" in name_lower:
                suggestions["Tür 2 (hinten)"].append(name)
    
    for category, fields in suggestions.items():
        if fields:
            print(f"\n  {category}:")
            for field in fields:
                value = lamps.get(field, "?")
                status = "🟢" if float(value) > 0 else "⚪"
                print(f"    {status} \"{field}\" (aktuell: {value})")
        else:
            print(f"\n  {category}:")
            print(f"    ⚠ Kein passendes Feld gefunden")
    
    print("\n" + "="*70)
    print("Kopieren Sie die Feldnamen in telemetry_display.py um sie zu verwenden")
    print("="*70 + "\n")


def monitor_mode(base_url: str, interval: float = 1.0) -> None:
    """Kontinuierliche Überwachung der Telemetrie-Änderungen"""
    print("\n🔄 LIVE-ÜBERWACHUNG (Strg+C zum Beenden)")
    print("-" * 40)
    print("Zeigt nur Änderungen an...\n")
    
    last_lamps = {}
    last_buttons = {}
    
    try:
        while True:
            data = get_all_telemetry(base_url)
            
            # Lampen-Änderungen
            current_lamps = data.get("all_lamps", {})
            for name, value in current_lamps.items():
                old_value = last_lamps.get(name)
                if old_value is not None and old_value != value:
                    status = "🟢 AN" if float(value) > 0 else "⚪ AUS"
                    print(f"  💡 {name}: {old_value} → {value} ({status})")
            
            last_lamps = current_lamps.copy()
            
            # Button-Änderungen
            current_buttons = {b.get("Name"): b.get("State") for b in data.get("all_buttons", [])}
            for name, state in current_buttons.items():
                old_state = last_buttons.get(name)
                if old_state is not None and old_state != state:
                    print(f"  🔘 {name}: {old_state} → {state}")
            
            last_buttons = current_buttons.copy()
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n→ Überwachung beendet")


def main():
    parser = argparse.ArgumentParser(
        description="Bus Telemetrie Diagnose-Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--telemetry", "-t",
        default="192.168.2.216:37337",
        help="Telemetrie-Adresse (Standard: 192.168.2.216:37337)"
    )
    
    parser.add_argument(
        "--monitor", "-m",
        action="store_true",
        help="Live-Überwachung von Änderungen"
    )
    
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Rohe JSON-Ausgabe"
    )
    
    args = parser.parse_args()
    
    base_url = f"http://{args.telemetry}"
    
    print(f"\n🔌 Verbinde mit {base_url}...")
    
    # Verbindung testen
    try:
        requests.get(f"{base_url}/vehicles", timeout=3)
        print("✓ Verbindung erfolgreich!")
    except RequestException as e:
        print(f"✗ Verbindungsfehler: {e}")
        print("\nMögliche Ursachen:")
        print("  • Spiel läuft nicht")
        print("  • Telemetrie nicht aktiviert")
        print("  • Falsche IP-Adresse")
        print("  • Firewall blockiert Port 37337")
        sys.exit(1)
    
    if args.monitor:
        monitor_mode(base_url)
    else:
        data = get_all_telemetry(base_url)
        
        if args.json:
            print(json.dumps(data, indent=2, default=str))
        else:
            print_telemetry(data)


if __name__ == "__main__":
    main()
