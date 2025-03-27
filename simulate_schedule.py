#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
simulate_schedule.py

Simuloi Raspberry Pi GPIO-pinnien ohjausta sähkön spot-hinnan perusteella
käyttäen Sahkotin /prices API:n tulevia hintatietoja ja paikallisia asetuksia. 
Tulostaa simuloidun ON/OFF-aikataulun taulukkona tiedostoon DATA_DIR-hakemistoon.
Asetukset luetaan skriptin omasta hakemistosta.
Hyväksyy komentoriviparametrit --today, --tomorrow, --date VVVV-KK-PP.
"""

import requests
import json
import datetime
import os
import sys
import argparse
from collections import defaultdict
# Aikavyöhykkeitä varten (Python 3.9+)
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    try:
        from pytz import timezone as ZoneInfo, UnknownTimeZoneError as ZoneInfoNotFoundError
        print("Huom: Käytetään pytz-kirjastoa zoneinfon sijaan. Varmista, että se ja tzdata on asennettu (pip install pytz tzdata).", file=sys.stderr)
    except ImportError:
        print("VIRHE: Aikavyöhykekirjastoa (zoneinfo tai pytz) ei löydy.", file=sys.stderr)
        sys.exit(1)

# --- Konfiguraatio ja Polut ---

# Hakemisto, jossa tämä skriptitiedosto sijaitsee
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) 

# Asetustiedoston polku SUHTEESSA skriptin sijaintiin
SETTINGS_FILE = os.path.join(SCRIPT_DIR, 'settings.json') 

# Hakemisto datatiedostoille (luodaan tarvittaessa)
DATA_DIR = os.path.expanduser('~/gpio_pricer_data') 

# Simuloinnin tulostiedosto datahakemistossa
OUTPUT_FILE = os.path.join(DATA_DIR, 'simulation_schedule.txt') 

# Sahkotin API konfiguraatio
SAHKOTIN_API_URL = 'https://sahkotin.fi/prices' 
API_TIMEOUT = 15 

# Paikallinen aikavyöhyke
LOCAL_TIMEZONE_STR = "Europe/Helsinki"

# --- Funktiot ---

def load_settings(settings_file_path):
    """Lataa asetukset JSON-tiedostosta (käyttää annettua polkua)."""
    # Käytetään nyt parametrina annettua polkua
    abs_path = os.path.abspath(settings_file_path) 
    print(f"Ladataan asetukset tiedostosta: {abs_path}")
    # ...(Loput funktiosta pysyy samana)...
    if not os.path.exists(abs_path):
        print(f"VIRHE: Asetustiedostoa '{abs_path}' ei löydy.", file=sys.stderr)
        return None
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            settings_list = json.load(f)
            if not isinstance(settings_list, list):
                print(f"VIRHE: Asetustiedosto '{abs_path}' ei sisältänyt listaa.", file=sys.stderr)
                return None
            valid_settings = []
            required_keys = {'gpio_pin', 'upper_limit_ct_kwh', 'lower_limit_ct_kwh', 'cheapest_hours_n'}
            for i, item in enumerate(settings_list):
                 is_valid = False
                 if isinstance(item, dict) and required_keys.issubset(item.keys()):
                      try:
                           n_value = int(item['cheapest_hours_n'])
                           if 0 <= n_value <= 24: # Simulaattorissa N voi olla 0-24
                                if 'identifier' not in item or not item['identifier']:
                                     item['identifier'] = f"Pin_{item['gpio_pin']}"
                                valid_settings.append(item)
                                is_valid = True
                           else:
                                print(f"VAROITUS: Ohitetaan asetusrivi {i+1}, koska 'cheapest_hours_n' ({n_value}) ei ole välillä 0-24: {item}")
                      except (ValueError, TypeError):
                           print(f"VAROITUS: Ohitetaan asetusrivi {i+1}, virheellinen 'cheapest_hours_n': {item.get('cheapest_hours_n')}")
                 if not is_valid and isinstance(item, dict): 
                      if not required_keys.issubset(item.keys()):
                           missing = required_keys - item.keys()
                           print(f"VAROITUS: Ohitetaan asetusrivi {i+1} puuttuvien avainten vuoksi ({missing}): {item}")
            if not valid_settings:
                print(f"VIRHE: Asetustiedosto '{abs_path}' ei sisältänyt yhtään kelvollista pinnimääritystä.", file=sys.stderr)
                return None
            print(f"Löytyi {len(valid_settings)} kelvollista pinnin asetusta.")
            return valid_settings
    except json.JSONDecodeError as e:
        print(f"VIRHE: Asetustiedosto '{abs_path}' on virheellinen JSON: {e}", file=sys.stderr)
        return None
    except IOError as e:
         print(f"VIRHE: Asetustiedoston '{abs_path}' lukeminen epäonnistui: {e}", file=sys.stderr)
         return None
    except Exception as e:
        print(f"VIRHE: Odottamaton virhe ladattaessa asetuksia: {e}", file=sys.stderr)
        return None


def fetch_price_data(api_base_url, target_date, local_timezone_str, timeout):
    """Hakee hintadataa Sahkotin /prices API:sta annetulle päivälle."""
    # ...(sisältö sama)...
    print(f"Valmistellaan API-kutsua päivälle {target_date.isoformat()}...")
    prices_raw = None 
    try:
        local_tz = ZoneInfo(local_timezone_str)
        local_start_naive = datetime.datetime.combine(target_date, datetime.time.min)
        if hasattr(local_tz, 'localize'): local_start_aware = local_tz.localize(local_start_naive)
        else: local_start_aware = local_start_naive.replace(tzinfo=local_tz)
        utc_start_aware = local_start_aware.astimezone(datetime.timezone.utc)
        start_param = utc_start_aware.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        url = f"{api_base_url}?fix&vat&start={start_param}"
        print(f"Haetaan hintadataa osoitteesta: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status() 
        data = response.json()
        if "prices" in data and isinstance(data["prices"], list):
             prices_raw = data["prices"] 
             print(f"Hintadata haettu onnistuneesti ({len(prices_raw)} hintapistettä).")
             return prices_raw
        else:
             print("VIRHE: Odottamaton JSON-rakenne Sahkotin API:sta (puuttuu 'prices' lista).", file=sys.stderr); return None
    except (ZoneInfoNotFoundError, Exception) as e: print(f"VIRHE: Virhe API-kutsun valmistelussa tai suorituksessa: {e}", file=sys.stderr); return None
    except requests.exceptions.Timeout: print(f"VIRHE: API-pyynnön aikakatkaisu", file=sys.stderr); return None
    except requests.exceptions.ConnectionError: print(f"VIRHE: Yhteysvirhe API-osoitteeseen", file=sys.stderr); return None
    except requests.exceptions.HTTPError as e: print(f"VIRHE: HTTP-virhe {e.response.status_code}", file=sys.stderr); return None
    except requests.exceptions.RequestException as e: print(f"VIRHE: Yleinen API-pyyntövirhe: {e}", file=sys.stderr); return None
    except json.JSONDecodeError: print(f"VIRHE: API:n vastaus ei ollut kelvollista JSONia.", file=sys.stderr); return None


def filter_and_prepare_prices(prices_raw, target_date, local_timezone_str):
    """Suodattaa ja valmistelee hinnat {tunti: hinta_ct}."""
    # ...(sisältö sama, ilman debug-tulosteita)...
    daily_prices = {}
    print(f"Suodatetaan ja valmistellaan hintoja päivälle: {target_date.isoformat()}")
    if not prices_raw: return {}
    try: local_tz = ZoneInfo(local_timezone_str)
    except Exception as e: print(f"VIRHE: Virheellinen aikavyöhyke '{local_timezone_str}': {e}", file=sys.stderr); return {} 
    processed_hours = set()
    for entry_index, price_entry in enumerate(prices_raw): 
        try:
            timestamp_str = price_entry.get('date')   
            price_eur_mwh = price_entry.get('value') 
            if timestamp_str is None or price_eur_mwh is None: continue 
            original_timestamp_str = timestamp_str 
            if timestamp_str.endswith('Z'): timestamp_str = timestamp_str[:-1] + '+00:00' 
            try:
                dt_object_aware = datetime.datetime.fromisoformat(timestamp_str) 
                dt_local = dt_object_aware.astimezone(local_tz) 
            except ValueError: continue 
            if dt_local.date() == target_date:
                hour = dt_local.hour
                if hour not in processed_hours:
                     try:
                         price_ct_kwh = float(price_eur_mwh) / 10.0
                         daily_prices[hour] = price_ct_kwh
                         processed_hours.add(hour)
                     except (ValueError, TypeError): continue
        except Exception as e: print(f"VAROITUS (filter): Odottamaton virhe {price_entry}: {e}", file=sys.stderr); continue 
    missing_hours = set(range(24)) - processed_hours
    if missing_hours: print(f"VAROITUS: Hintatieto puuttuu/ei suodatettu tunneilta {sorted(list(missing_hours))} päivälle {target_date.isoformat()}. Tila 'N/A'.", file=sys.stderr)
    print(f"Löytyi ja valmisteltiin {len(daily_prices)} hintaa päivälle {target_date.isoformat()}.")
    return daily_prices

# find_cheapest_hours ja simulate_pin_state pysyvät samoina
def find_cheapest_hours(daily_prices_dict, n):
    if n <= 0 or not daily_prices_dict: return set()
    price_hour_list = [(price, hour) for hour, price in daily_prices_dict.items() if price is not None]
    if not price_hour_list: return set()
    if len(price_hour_list) < n: n = len(price_hour_list) 
    price_hour_list.sort()
    cheapest_entries = price_hour_list[:n]
    return {hour for price, hour in cheapest_entries}

def simulate_pin_state(pin_setting, hour, hourly_price_ct_kwh, cheapest_hours_set):
    if hourly_price_ct_kwh is None: return None 
    try:
        upper_limit = float(pin_setting['upper_limit_ct_kwh'])
        lower_limit = float(pin_setting['lower_limit_ct_kwh'])
        n = int(pin_setting['cheapest_hours_n']) 
    except (KeyError, ValueError, TypeError): return False
    if hourly_price_ct_kwh > upper_limit: return False 
    elif hourly_price_ct_kwh < lower_limit: return True 
    else: 
        if n > 0: return hour in cheapest_hours_set 
        else: return False 

# --- Pääohjelma ---
def main(target_date):
    print("-" * 50)
    print("--- GPIO Ohjauksen Simulaattori Käynnistyy (Sahkotin /prices API) ---") 
    print(f"Simuloidaan aikataulu päivälle: {target_date.isoformat()}")
    print("-" * 50)
    
    # Varmistetaan datahakemiston olemassaolo
    try:
        # DATA_DIR on nyt määritelty globaalisti
        os.makedirs(DATA_DIR, exist_ok=True) 
        print(f"Varmistettu datahakemiston olemassaolo: {DATA_DIR}")
    except OSError as e:
        print(f"KRIITTINEN VIRHE datahakemiston '{DATA_DIR}' luonnissa/varmistuksessa: {e}. Ohjelma lopetetaan.", file=sys.stderr)
        sys.exit(1)

    # Käytetään globaalia SETTINGS_FILE polkua
    settings_list = load_settings(SETTINGS_FILE) 
    if not settings_list: sys.exit(1)

    raw_prices = fetch_price_data(SAHKOTIN_API_URL, target_date, LOCAL_TIMEZONE_STR, API_TIMEOUT) 
    if raw_prices is None: sys.exit(1)

    daily_prices_dict = filter_and_prepare_prices(raw_prices, target_date, LOCAL_TIMEZONE_STR)
    
    if not daily_prices_dict and target_date >= datetime.date.today(): 
         print(f"Hintatietoja päivälle {target_date.isoformat()} ei löytynyt tai niitä ei ole vielä julkaistu. Aikataulua ei voi luoda.", file=sys.stderr)
         if target_date > datetime.date.today(): print("Yritä myöhemmin uudelleen.", file=sys.stderr)
         sys.exit(1 if target_date == datetime.date.today() else 0) 

    print("Simuloidaan pinnien tilat...")
    # ...(Simulointilogiikka pysyy samana)...
    schedule = defaultdict(dict)
    pin_identifiers = [] 
    for setting in settings_list:
        identifier = setting['identifier']
        pin_identifiers.append(identifier) 
        n = setting.get('cheapest_hours_n', 0) 
        cheapest_set_for_pin = set() 
        if n > 0: cheapest_set_for_pin = find_cheapest_hours(daily_prices_dict, n)
        for hour in range(24):
            price_for_hour = daily_prices_dict.get(hour) 
            simulated_state = simulate_pin_state(setting, hour, price_for_hour, cheapest_set_for_pin)
            schedule[identifier][hour] = simulated_state 
    print("Simulointi valmis.")

    # Kirjoitetaan tiedosto DATA_DIR hakemistoon (OUTPUT_FILE)
    output_abs_path = os.path.abspath(OUTPUT_FILE) 
    print(f"Kirjoitetaan aikataulutaulukko tiedostoon: {output_abs_path}")
    # ...(Tiedostoon kirjoituslogiikka pysyy samana)...
    try:
        with open(output_abs_path, 'w', encoding='utf-8') as f:
            f.write(f"--- Simuloitu GPIO Aikataulu (Data: Sahkotin /prices API) ---\n") 
            f.write(f"Päivämäärä: {target_date.isoformat()}\n")
            f.write(f"Luotu: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            hour_col_width = 7 
            max_id_len = max(len(id) for id in pin_identifiers) if pin_identifiers else 0
            state_col_width = max(5, max_id_len) + 2 
            header = f"{'Tunti':<{hour_col_width}}|"
            sorted_identifiers = sorted(pin_identifiers) 
            for identifier in sorted_identifiers: header += f"{identifier:<{state_col_width}}|" 
            f.write(header + "\n")
            separator = "-" * hour_col_width + "+"
            for _ in sorted_identifiers: separator += "-" * state_col_width + "+"
            f.write(separator + "\n")
            for hour in range(24):
                 row_str = f"  {hour:02d}:00{'':<{hour_col_width-7}}|" 
                 for identifier in sorted_identifiers: 
                     state = schedule[identifier].get(hour) 
                     if state is True: state_str = "ON"
                     elif state is False: state_str = "OFF"
                     else: state_str = "N/A" 
                     row_str += f"{state_str:<{state_col_width}}|"
                 f.write(row_str + "\n")
            print(f"Aikataulutaulukko kirjoitettu onnistuneesti tiedostoon: {output_abs_path}")
    except IOError as e: print(f"VIRHE: Tiedostoon '{output_abs_path}' kirjoittaminen epäonnistui: {e}", file=sys.stderr)
    except Exception as e: print(f"VIRHE: Odottamaton virhe taulukon kirjoituksessa: {e}", file=sys.stderr)
        
    print("-" * 50)
    print("--- Simulaattori Valmis ---")
    print("-" * 50)

# --- Komentoriviparametrien Käsittely ja Suoritus ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simuloi GPIO-ohjausta sähkön hinnan perusteella käyttäen Sahkotin /prices API:a ja luo aikataulutaulukon tiedostoon.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter 
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--today", action="store_true", help="Simuloi kuluvalle päivälle (oletus)")
    group.add_argument("--tomorrow", action="store_true", help="Simuloi seuraavalle päivälle")
    # Otettu --date käyttöön
    parser.add_argument("--date", type=str, help="Simuloi tietylle päivälle (muodossa VVVV-KK-PP)") 

    args = parser.parse_args()

    # Päivitetty päivämäärän määritys
    if args.date:
        try:
            sim_date = datetime.date.fromisoformat(args.date)
            print(f"Käytetään annettua päivämäärää: {sim_date.isoformat()}")
        except ValueError:
            print(f"VIRHE: Virheellinen päivämäärämuoto '{args.date}'. Käytä VVVV-KK-PP.", file=sys.stderr)
            sys.exit(1)
    elif args.tomorrow:
        sim_date = datetime.date.today() + datetime.timedelta(days=1)
        print(f"Käytetään huomista päivämäärää: {sim_date.isoformat()}")
    else: # Oletus tai --today
        sim_date = datetime.date.today()
        print(f"Käytetään tätä päivää: {sim_date.isoformat()}")
        
    # Tarkistetaan asetustiedoston olemassaolo käyttäen globaalia polkua
    settings_path_abs = os.path.abspath(SETTINGS_FILE) 
    if not os.path.exists(settings_path_abs):
         print(f"KRIITTINEN VIRHE: Asetustiedostoa '{settings_path_abs}' ei löydy.", file=sys.stderr); sys.exit(1)
         
    main(sim_date)
