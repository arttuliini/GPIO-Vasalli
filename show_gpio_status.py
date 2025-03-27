#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
show_gpio_status.py

Lukee viimeisimmän GPIO-tilatiedon JSON-tiedostosta, jonka 
hourly_control.py on luonut DATA_DIR-hakemistoon, ja tulostaa sen 
selkeässä taulukkomuodossa.
"""

import json
import os
import sys
import datetime
# Aikavyöhykkeitä varten (varmistetaan olemassaolo)
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    try:
        from pytz import timezone as ZoneInfo, UnknownTimeZoneError as ZoneInfoNotFoundError
        # Ei tulosteta huomautusta tässä työkalussa
    except ImportError:
        print("VIRHE: Aikavyöhykekirjastoa (zoneinfo tai pytz) ei löydy.", file=sys.stderr)
        ZoneInfo = None # Asetetaan None, jotta myöhempi koodi ei kaadu täysin

# --- Konfiguraatio ---

# Hakemisto, josta tilatiedosto luetaan (sama kuin hourly_control.py:ssä)
DATA_DIR = os.path.expanduser('~/gpio_pricer_data') 

# Tilatiedoston nimi ja polku
STATUS_FILENAME = 'gpio_current_status.json'
STATUS_FILE = os.path.join(DATA_DIR, STATUS_FILENAME) 

def read_status_file(status_file_path):
    """Lukee ja jäsentää JSON-tilatiedoston."""
    abs_path = os.path.abspath(status_file_path)
    if not os.path.exists(abs_path):
        print(f"VIRHE: Tilatiedostoa '{abs_path}' ei löydy.", file=sys.stderr)
        print("Aja 'hourly_control.py' ainakin kerran luodaksesi tiedoston.", file=sys.stderr)
        return None, None # Palauta None datalle ja timestampille
        
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            status_data = json.load(f)
            
            # Yritetään poimia aikaleima ja muotoilla se
            run_timestamp_str = "N/A"
            if status_data:
                 first_key = next(iter(status_data)) 
                 ts_str = status_data[first_key].get('timestamp')
                 if ts_str:
                      try:
                           run_timestamp = datetime.datetime.fromisoformat(ts_str)
                           # Jos ZoneInfo on saatavilla, yritä näyttää paikallisessa ajassa
                           if ZoneInfo:
                                local_tz_str = "Europe/Helsinki" # Voitaisiin hakea järjestelmästäkin
                                try:
                                     local_tz = ZoneInfo(local_tz_str)
                                     run_timestamp = run_timestamp.astimezone(local_tz)
                                     run_timestamp_str = run_timestamp.strftime('%Y-%m-%d %H:%M:%S %Z%z')
                                except ZoneInfoNotFoundError:
                                     run_timestamp_str = run_timestamp.strftime('%Y-%m-%d %H:%M:%S') + " (Tuntematon vyöhyke)"
                           else: # Jos ZoneInfo ei saatavilla, näytä alkuperäisessä (tod.näk. UTC offsetilla)
                                run_timestamp_str = run_timestamp.isoformat()

                      except (ValueError, TypeError):
                           run_timestamp_str = ts_str # Näytä sellaisenaan, jos muotoilu epäonnistuu
            return status_data, run_timestamp_str
            
    except json.JSONDecodeError as e:
        print(f"VIRHE: Tilatiedosto '{abs_path}' on virheellisessä JSON-muodossa: {e}", file=sys.stderr)
        return None, None
    except IOError as e:
        print(f"VIRHE: Tilatiedoston '{abs_path}' lukeminen epäonnistui: {e}", file=sys.stderr)
        return None, None
    except Exception as e:
        print(f"VIRHE: Odottamaton virhe tilatiedostoa lukiessa: {e}", file=sys.stderr)
        return None, None

def display_status_table(status_data, run_timestamp_str="N/A"):
    """Tulostaa tilatiedot siistissä taulukossa."""
    if not status_data:
        print("Ei tilatietoja näytettäväksi.")
        return

    # Määritä sarakkeiden maksimileveydet muotoilua varten
    max_pin_len = len("Pin")
    max_id_len = len("Tunniste")
    max_state_len = len("Tila")
    max_reason_len = len("Syy")
    
    items_to_display = []
    for identifier in sorted(status_data.keys()): # Järjestä tunnisteen mukaan
        data = status_data[identifier]
        pin_str = str(data.get('pin', 'N/A'))
        state_str = data.get('state', 'N/A')
        reason_str = data.get('reason', 'N/A')
        items_to_display.append((pin_str, identifier, state_str, reason_str))
        max_pin_len = max(max_pin_len, len(pin_str))
        max_id_len = max(max_id_len, len(identifier))
        max_state_len = max(max_state_len, len(state_str))
        max_reason_len = max(max_reason_len, len(reason_str))

    # Tulosta otsikkotiedot
    print(f"--- GPIO Tilatiedot (Viimeisin ajo: {run_timestamp_str}) ---")
    header = (f"{'Pin':<{max_pin_len}} | {'Tunniste':<{max_id_len}} | "
              f"{'Tila':<{max_state_len}} | {'Syy':<{max_reason_len}}")
    print(header)
    separator = ("-" * max_pin_len + "-+-" + "-" * max_id_len + "-+-" +
                 "-" * max_state_len + "-+-" + "-" * max_reason_len)
    print(separator)

    # Tulosta datarivit
    for pin_str, identifier, state_str, reason_str in items_to_display:
         row = (f"{pin_str:<{max_pin_len}} | {identifier:<{max_id_len}} | "
                f"{state_str:<{max_state_len}} | {reason_str:<{max_reason_len}}")
         print(row)
    
    print("-" * len(separator)) 

if __name__ == "__main__":
    # Varmistetaan, että datahakemisto on olemassa ennen lukuyritystä
    # (vaikka lukufunktio tarkistaakin tiedoston, tämä voi auttaa selkeyttämään virhettä)
    if not os.path.isdir(DATA_DIR):
         print(f"VIRHE: Datahakemistoa '{DATA_DIR}' ei löydy.", file=sys.stderr)
         print("Aja 'hourly_control.py' ainakin kerran luodaksesi hakemiston ja tilatiedoston.", file=sys.stderr)
         sys.exit(1)
         
    status_data, timestamp = read_status_file(STATUS_FILE)
    if status_data is not None: 
        display_status_table(status_data, timestamp)
    else:
        sys.exit(1)
