#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
hourly_control.py

Ajetaan tunneittain (esim. cronilla). Hakee sähkön hinnan, vertaa sitä
asetuksiin ja ohjaa Raspberry Pi:n GPIO-pinnejä käyttäen 
api.spot-hinta.fi -palvelun API-kutsuja.

Kirjoittaa ajon päätteeksi yhteenvedon pinnien tiloista JSON-tiedostoon 
(viimeisin tila) sekä lisää tilatiedot jatkuvaan CSV-historiatiedostoon.
Molemmat tiedostot tallennetaan DATA_DIR-hakemistoon. 
Asetukset (kokonaislukurajat ct/kWh) luetaan skriptin omasta hakemistosta.
"""

import json
import requests
import logging
import sys
import os
import datetime
import csv 
try:
    import RPi.GPIO as GPIO
except ImportError:
    print("VIRHE: RPi.GPIO kirjastoa ei löytynyt...", file=sys.stderr)
    sys.exit(1)
except RuntimeError:
     print("VIRHE: Ei voitu ladata RPi.GPIO:ta...", file=sys.stderr)
     sys.exit(1)

# --- Konfiguraatio ja Polut ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) 
SETTINGS_FILE = os.path.join(SCRIPT_DIR, 'settings.json') 
DATA_DIR = os.path.expanduser('~/gpio_pricer_data') 
LOG_FILE = os.path.join(DATA_DIR, 'gpio_control.log') 
STATUS_FILE = os.path.join(DATA_DIR, 'gpio_current_status.json') 
CSV_LOG_FILE = os.path.join(DATA_DIR, 'gpio_history.csv')      
API_BASE_URL = 'https://api.spot-hinta.fi' 
API_V1_BASE_URL = 'https://api.spot-hinta.fi/v1' 
API_TIMEOUT = 15 
GPIO_MODE = GPIO.BCM 
GPIO.setwarnings(False) 

# --- Lokituksen Asetukset ---
try:
    log_dir_for_logging = os.path.dirname(LOG_FILE)
    if log_dir_for_logging: os.makedirs(log_dir_for_logging, exist_ok=True) 
except OSError as e:
     print(f"KRIITTINEN VIRHE lokihakemiston luonnissa: {e}", file=sys.stderr)
try:
    logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=LOG_FILE, filemode='a' )
except Exception as e: # Laajennettu virheenkäsittely, jos PermissionError ei ole ainoa mahdollinen
     logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr )
     logging.error(f"*** VIRHE LOKITIEDOSTOON KIRJOITTAMISESSA ({LOG_FILE}), syy: {e}. Lokitetaan stderr:iin. ***")

# --- Apufunktiot ---

def load_settings():
    """Lataa asetukset JSON-tiedostosta ja varmistaa rajojen olevan kokonaislukuja."""
    settings_path = os.path.abspath(SETTINGS_FILE) 
    logging.info(f"Ladataan asetukset tiedostosta: {settings_path}")
    if not os.path.exists(settings_path): logging.error(f"Asetustiedostoa '{settings_path}' ei löydy."); return None
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings_list = json.load(f)
            if not isinstance(settings_list, list): logging.error(f"Asetustiedosto '{settings_path}' ei sisältänyt listaa."); return None
            
            valid_settings = []
            required_keys = {'gpio_pin', 'upper_limit_ct_kwh', 'lower_limit_ct_kwh', 'cheapest_hours_n'}
            
            for i, item in enumerate(settings_list):
                 is_valid_entry = False
                 if isinstance(item, dict) and required_keys.issubset(item.keys()):
                      try:
                           # --- MUUTOS: Varmista ja muunna rajat kokonaisluvuiksi ---
                           pin = int(item['gpio_pin'])
                           upper_limit = int(item['upper_limit_ct_kwh'])
                           lower_limit = int(item['lower_limit_ct_kwh'])
                           n_value = int(item['cheapest_hours_n'])

                           # Tee lisätarkistuksia
                           if not (0 <= n_value <= 12): raise ValueError(f"N ({n_value}) ei ole välillä 0-12")
                           if not (lower_limit <= upper_limit): raise ValueError("Alarajan tulee olla <= yläraja")
                           if pin <= 0: raise ValueError("Pinninumeron tulee olla positiivinen")

                           # Tallenna kokonaislukuina (vaikka configure_settings tallentaakin jo näin)
                           item['upper_limit_ct_kwh'] = upper_limit
                           item['lower_limit_ct_kwh'] = lower_limit
                           item['cheapest_hours_n'] = n_value
                           item['gpio_pin'] = pin
                           # --- MUUTOS LOPPUU ---

                           if 'identifier' not in item or not item['identifier']: item['identifier'] = f"Pin_{pin}"
                           valid_settings.append(item)
                           is_valid_entry = True

                      except (ValueError, TypeError, KeyError) as e:
                           logging.warning(f"Ohitetaan asetusrivi {i+1} virheellisen arvon vuoksi: {item}. Virhe: {e}")
                 
                 if not is_valid_entry and isinstance(item, dict): 
                      if not required_keys.issubset(item.keys()): logging.warning(f"Ohitetaan asetusrivi {i+1} puuttuvien avainten vuoksi")
                      # Muita mahdollisia virheitä logattu jo ylempänä try-exceptissä

            if not valid_settings: logging.error("Asetustiedosto ei sisältänyt yhtään kelvollista pinnimääritystä."); return None
            logging.info(f"Löytyi {len(valid_settings)} kelvollista pinnin asetusta.")
            return valid_settings
            
    except json.JSONDecodeError as e: logging.error(f"Asetustiedosto '{settings_path}' on virheellinen JSON: {e}"); return None
    except IOError as e: logging.error(f"Asetustiedoston '{settings_path}' lukeminen epäonnistui: {e}"); return None
    except Exception as e: logging.error(f"Odottamaton virhe ladattaessa asetuksia: {e}"); return None

def setup_gpio():
    """Alustaa GPIO-kirjaston."""
    try: GPIO.setmode(GPIO_MODE); logging.info(f"GPIO-tila asetettu: {GPIO_MODE} (BCM)")
    except Exception as e: logging.error(f"GPIO-tilan ({GPIO_MODE}) asetus epäonnistui: {e}"); raise RuntimeError(f"GPIO alustus epäonnistui: {e}")

def set_gpio_state(pin_number, state, identifier=""):
    """Asettaa annetun GPIO-pinnin tilan (True=ON, False=OFF)."""
    pin_id_str = f"Pinni {pin_number} ({identifier})" if identifier else f"Pinni {pin_number}"
    target_state_str = "ON (HIGH)" if state else "OFF (LOW)"
    gpio_value = GPIO.HIGH if state else GPIO.LOW
    try:
        GPIO.setup(pin_number, GPIO.OUT) 
        GPIO.output(pin_number, gpio_value)
        logging.info(f"{pin_id_str}: Tila asetettu -> {target_state_str}")
        return True
    except Exception as e: logging.error(f"{pin_id_str}: GPIO-virhe tilaa {target_state_str} asettaessa: {e}"); return False

# --- API-KUTSUFUNKTIOT ---

# ===== MUUTETTU FUNKTIO =====
def check_price_limits(lower_limit_ct_int, upper_limit_ct_int):
    """
    MUUTETTU: Kutsuu API:a /JustNow/{lower}/{upper} käyttäen KOKONAISLUKU ct/kWh rajoja.
    Parametrien tulee olla jo kokonaislukuja.
    Palauttaa: 0 (hinta <= alaraja), 1 (hinta välissä), 2 (hinta > yläraja) tai None (virhe).
    """
    try:
        # Varmistetaan varmuudeksi tyypit kokonaisluvuiksi
        lower_limit_int_checked = int(lower_limit_ct_int)
        upper_limit_int_checked = int(upper_limit_ct_int)
        
        if lower_limit_int_checked > upper_limit_int_checked:
             logging.warning(f"check_price_limits sai alarajan ({lower_limit_int_checked}), joka on suurempi kuin yläraja ({upper_limit_int_checked}). Käytetään ylärajaa molemmissa.")
             lower_limit_int_checked = upper_limit_int_checked

        url = f"{API_BASE_URL}/JustNow/{lower_limit_int_checked}/{upper_limit_int_checked}" 
        logging.info(f"API-KUTSU: {url} (Rajat ct/kWh kokonaislukuina)") 
        response = requests.get(url, timeout=API_TIMEOUT, headers={'accept': 'text/plain'}) 
        
        if response.status_code == 404: logging.error(f"API VIRHE: HTTP 404 kutsussa {url}. API ei löytänyt hintatietoja."); return None 
        elif response.status_code == 429: logging.error(f"API VIRHE: HTTP 429 kutsussa {url}. Liikaa pyyntöjä."); return None
        response.raise_for_status() 

        try:
             result = int(response.text)
             logging.info(f"API VASTAUS: JustNow -> {result} (verrattu rajoihin <= {lower_limit_int_checked} ct/kWh ja > {upper_limit_int_checked} ct/kWh)")
             if result not in [0, 1, 2]: logging.warning(f"API VASTAUS: JustNow palautti odottamattoman arvon: {result}."); return None
             return result
        except ValueError: logging.error(f"API VIRHE: JustNow palautti ei-numeerisen vastauksen: '{response.text}'"); return None

    except requests.exceptions.Timeout: logging.error(f"API VIRHE: Aikakatkaisu kutsussa {url}"); return None
    except requests.exceptions.ConnectionError: logging.error(f"API VIRHE: Yhteysvirhe kutsussa {url}"); return None
    except requests.exceptions.HTTPError as e: logging.error(f"API VIRHE: HTTP Virhe {e.response.status_code} kutsussa {url}. Vastaus: {e.response.text}"); return None
    except requests.exceptions.RequestException as e: logging.error(f"API VIRHE: Yleinen Request-virhe kutsussa {url}: {e}"); return None
    except Exception as e: logging.error(f"Odottamaton virhe check_price_limits funktiossa: {e}"); return None
# ===== MUUTOS LOPPUU =====

def check_if_cheapest_hour(num_hours):
    """Kutsuu API:a /CheapestPeriodTodayCheck/{hours} tarkistaakseen, kuuluuko tunti N halvimpiin (1-12)."""
    # ...(sisältö sama kuin edellisessä versiossa)...
    if not 1 <= num_hours <= 12: logging.warning(f"API /CheapestPeriodTodayCheck tukee vain 1-12h, pyydetty N={num_hours}."); return None 
    url = f"{API_BASE_URL}/CheapestPeriodTodayCheck/{num_hours}"
    logging.info(f"API-KUTSU: {url}")
    try:
        response = requests.get(url, timeout=API_TIMEOUT); status_code = response.status_code
        logging.info(f"API VASTAUS: CheapestPeriodTodayCheck -> Status {status_code}")
        if status_code == 200: return True 
        elif status_code == 400: logging.info(f"API Info: (N={num_hours}) palautti 400 - tunti ei halvin."); return False 
        elif status_code == 404: logging.error(f"API VIRHE: HTTP 404 kutsussa {url}. Hintatietoja ei löytynyt."); return None 
        elif status_code == 429: logging.error(f"API VIRHE: HTTP 429 kutsussa {url}. Liikaa pyyntöjä."); return None 
        else: response.raise_for_status(); return None 
    except requests.exceptions.Timeout: logging.error(f"API VIRHE: Aikakatkaisu kutsussa {url}"); return None 
    except requests.exceptions.ConnectionError: logging.error(f"API VIRHE: Yhteysvirhe kutsussa {url}"); return None 
    except requests.exceptions.HTTPError as e: logging.error(f"API VIRHE: HTTP Virhe {e.response.status_code} kutsussa {url}."); return None 
    except requests.exceptions.RequestException as e: logging.error(f"API VIRHE: Yleinen Request-virhe kutsussa {url}: {e}"); return None 
    except Exception as e: logging.error(f"Odottamaton virhe check_if_cheapest_hour funktiossa: {e}"); return None 

# --- Pääohjelma ---

def main():
    """Pääohjelma, joka ajetaan tunneittain."""
    start_time = datetime.datetime.now(datetime.timezone.utc).astimezone() 
    logging.info("===== Ohjausohjelma Käynnistyy =====")
    pin_final_statuses = {} 
    try: os.makedirs(DATA_DIR, exist_ok=True); logging.info(f"Varmistettu datahakemiston olemassaolo: {DATA_DIR}")
    except OSError as e: logging.critical(f"KRIITTINEN VIRHE datahakemiston '{DATA_DIR}' luonnissa: {e}. Lopetetaan."); sys.exit(1)
    try: setup_gpio()
    except RuntimeError as e: logging.critical(f"GPIO alustus epäonnistui: {e}. Lopetetaan."); sys.exit(1) 
    
    # Lataa asetukset (joiden pitäisi nyt sisältää kokonaislukurajat)
    settings_list = load_settings()
    if not settings_list: logging.error("Asetuksia ei voitu ladata. Lopetetaan."); sys.exit(1) 

    for setting in settings_list:
        try:
            # Luetaan arvot ja varmistetaan tyypit (erityisesti rajat kokonaislukuina)
            pin = int(setting['gpio_pin']) 
            identifier = setting.get('identifier', f'Pinni_{pin}') 
            upper_limit_ct = int(setting['upper_limit_ct_kwh']) 
            lower_limit_ct = int(setting['lower_limit_ct_kwh']) 
            rank_n = int(setting.get('cheapest_hours_n', 0)) 
            # Varmistetaan vielä N:n arvo (0-12)
            if not (0 <= rank_n <= 12): rank_n = 0

            logging.info(f"--- Käsitellään: {identifier} (GPIO {pin}) ---")
            # Tulostetaan nyt kokonaislukurajat lokiin selkeyden vuoksi
            logging.info(f"Asetukset: Yläraja={upper_limit_ct} ct/kWh, Alaraja={lower_limit_ct} ct/kWh, N={rank_n} (0-12)")

            # === MUUTOS: Annetaan check_price_limits funktiolle suoraan kokonaisluvut ===
            limit_check_result = check_price_limits(lower_limit_ct, upper_limit_ct) 

            desired_state = None 
            reason_string = "Tuntematon syy" 

            # Päätöksenteko (käyttää API:n palauttamaa tulosta 0, 1, 2)
            # Logiikka sama, mutta syy-teksteissä viitataan kokonaislukurajoihin
            if limit_check_result is None:
                reason_string = "API-virhe hintarajatarkistuksessa"
                desired_state = False 
            elif limit_check_result == 2: # Hinta > Yläraja (kokonaisluku)
                reason_string = f"Hinta > Yläraja ({upper_limit_ct} ct/kWh)" 
                desired_state = False 
            elif limit_check_result == 0: # Hinta <= Alaraja (kokonaisluku)
                reason_string = f"Hinta <= Alaraja ({lower_limit_ct} ct/kWh)" 
                desired_state = True 
            elif limit_check_result == 1: # Hinta rajojen välissä
                base_reason = f"Hinta välillä ({lower_limit_ct} - {upper_limit_ct}] ct/kWh"
                if rank_n > 0:
                    is_cheap = check_if_cheapest_hour(rank_n) 
                    if is_cheap is None:
                        reason_string = f"{base_reason}, N-tarkistus epäonnistui (API-virhe)"
                        desired_state = False 
                    elif is_cheap is True:
                        reason_string = f"{base_reason}, kuuluu {rank_n} halvimpiin"
                        desired_state = True 
                    else: 
                        reason_string = f"{base_reason}, EI kuulu {rank_n} halvimpiin"
                        desired_state = False 
                else: 
                     reason_string = f"{base_reason}, N=0, ei tarkistusta"
                     desired_state = False 
            else: 
                 reason_string = f"Odottamaton API-tulos ({limit_check_result})"
                 desired_state = False

            if desired_state is None: 
                 reason_string = "Kriittinen logiikkavirhe" 
                 desired_state = False

            # Tallenna lopullinen tila ja syy dictionaryyn
            pin_final_statuses[identifier] = { "pin": pin, "state": "ON" if desired_state else "OFF",
                "reason": reason_string, "timestamp": start_time.isoformat() }

            # Aseta GPIO-pinnin tila
            set_gpio_state(pin, desired_state, identifier)

        except KeyError as e: logging.error(f"Asetusvirhe: Avainta {e} ei löytynyt: {setting}. Ohitetaan."); continue 
        except (ValueError, TypeError) as e: logging.error(f"Asetusvirhe: Virheellinen arvo: {setting}: {e}. Ohitetaan."); continue
        except Exception as e: logging.error(f"Odottamaton virhe: {setting}: {e}"); continue 

    # --- KIRJOITETAAN TIEDOSTOT AJON LOPUKSI ---
    # (CSV ja JSON kirjoitus sama kuin edellisessä versiossa)
    try:
        csv_file_path = os.path.abspath(CSV_LOG_FILE); file_exists = os.path.isfile(csv_file_path)
        needs_header = not file_exists or os.path.getsize(csv_file_path) == 0
        logging.info(f"Kirjoitetaan tilahistoriaa CSV: {csv_file_path}")
        with open(csv_file_path, 'a', newline='', encoding='utf-8') as f_csv:
            csv_writer = csv.writer(f_csv); 
            if needs_header: csv_writer.writerow(['Timestamp', 'PinNumber', 'Identifier', 'State', 'Reason'])
            run_timestamp_iso = start_time.isoformat() 
            for identifier in sorted(pin_final_statuses.keys()):
                info = pin_final_statuses[identifier]
                csv_writer.writerow([ run_timestamp_iso, info.get('pin'), identifier, info.get('state'), info.get('reason') ])
    except Exception as e: logging.error(f"VIRHE CSV-kirjoituksessa: {e}")
    try:
        status_file_path = os.path.abspath(STATUS_FILE) 
        logging.info(f"Päivitetään JSON-status: {status_file_path}")
        with open(status_file_path, 'w', encoding='utf-8') as f_status:
            json.dump(pin_final_statuses, f_status, indent=4, ensure_ascii=False, sort_keys=True) 
    except Exception as e: logging.error(f"VIRHE JSON-kirjoituksessa: {e}")
            
    end_time = datetime.datetime.now(datetime.timezone.utc).astimezone()
    duration = end_time - start_time
    logging.info(f"===== Ohjausohjelma Valmis (Kesto: {duration.total_seconds():.2f} s) =====")

# --- Pääohjelman Suoritus ---
if __name__ == "__main__":
    main()
