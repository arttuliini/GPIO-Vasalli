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
Asetukset luetaan skriptin omasta hakemistosta.
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
    print("VIRHE: RPi.GPIO kirjastoa ei löytynyt. Asenna se (pip install RPi.GPIO) tai aja Raspberry Pi:llä.", file=sys.stderr)
    sys.exit(1)
except RuntimeError:
     print("VIRHE: Ei voitu ladata RPi.GPIO:ta, todennäköisesti ajetaan väärällä laitteella tai puuttuu oikeuksia.", file=sys.stderr)
     sys.exit(1)

# --- Konfiguraatio ja Polut ---

# Hakemisto, jossa tämä skriptitiedosto sijaitsee
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) 

# Asetustiedoston polku SUHTEESSA skriptin sijaintiin
SETTINGS_FILE = os.path.join(SCRIPT_DIR, 'settings.json') 

# Hakemisto datatiedostoille (luodaan tarvittaessa)
DATA_DIR = os.path.expanduser('~/gpio_pricer_data') 

# Loki-, status- ja historiatiedostojen polut datahakemistossa
LOG_FILE = os.path.join(DATA_DIR, 'gpio_control.log') 
STATUS_FILE = os.path.join(DATA_DIR, 'gpio_current_status.json') # Viimeisin tila JSON
CSV_LOG_FILE = os.path.join(DATA_DIR, 'gpio_history.csv')      # Historiatiedosto CSV

# Spot-Hinta API konfiguraatio
API_BASE_URL = 'https://api.spot-hinta.fi' # Juuripolku
API_V1_BASE_URL = 'https://api.spot-hinta.fi/v1' # /v1-polku (tarvittaessa)
API_TIMEOUT = 15 # Sekuntia

# GPIO Asetukset
GPIO_MODE = GPIO.BCM 
GPIO.setwarnings(False) 

# --- Lokituksen Asetukset ---
# (Sama kuin edellisessä versiossa, varmistaa logihakemiston olemassaolon)
try:
    log_dir_for_logging = os.path.dirname(LOG_FILE)
    if log_dir_for_logging: 
        os.makedirs(log_dir_for_logging, exist_ok=True) 
except OSError as e:
     print(f"KRIITTINEN VIRHE lokihakemiston '{log_dir_for_logging}' luonnissa/varmistuksessa: {e}.", file=sys.stderr)
try:
    logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
        filename=LOG_FILE, filemode='a' )
except PermissionError:
     logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
         stream=sys.stderr )
     logging.error(f"*** EI KIRJOITUSOIKEUTTA LOKITIEDOSTOON: {LOG_FILE}. Lokitetaan stderr:iin. ***")
except Exception as e:
     print(f"KRIITTINEN VIRHE lokituksen alustuksessa: {e}. Ohjelma lopetetaan.", file=sys.stderr)
     sys.exit(1)

# --- Apufunktiot ---

def load_settings():
    """Lataa asetukset JSON-tiedostosta (käyttää globaalia SETTINGS_FILE polkua)."""
    # Käytetään nyt globaalisti määriteltyä SETTINGS_FILE polkua
    settings_path = os.path.abspath(SETTINGS_FILE) 
    logging.info(f"Ladataan asetukset tiedostosta: {settings_path}")
    # ...(Loput funktiosta pysyy samana kuin edellisessä versiossa)...
    if not os.path.exists(settings_path):
        logging.error(f"Asetustiedostoa '{settings_path}' ei löydy.")
        return None
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings_list = json.load(f)
            if not isinstance(settings_list, list):
                 logging.error(f"Asetustiedosto '{settings_path}' ei sisältänyt listaa.")
                 return None
            valid_settings = []
            required_keys = {'gpio_pin', 'upper_limit_ct_kwh', 'lower_limit_ct_kwh', 'cheapest_hours_n'}
            for i, item in enumerate(settings_list):
                 is_valid = False
                 if isinstance(item, dict) and required_keys.issubset(item.keys()):
                      try:
                           n_value = int(item['cheapest_hours_n'])
                           if 0 <= n_value <= 12:
                                if 'identifier' not in item or not item['identifier']:
                                     item['identifier'] = f"Pin_{item['gpio_pin']}"
                                valid_settings.append(item)
                                is_valid = True
                           else:
                                logging.warning(f"Ohitetaan asetusrivi {i+1}, koska 'cheapest_hours_n' ({n_value}) ei ole välillä 0-12: {item}")
                      except (ValueError, TypeError):
                           logging.warning(f"Ohitetaan asetusrivi {i+1}, virheellinen 'cheapest_hours_n': {item.get('cheapest_hours_n')}")
                 if not is_valid and isinstance(item, dict): 
                      if not required_keys.issubset(item.keys()):
                           missing = required_keys - item.keys()
                           logging.warning(f"Ohitetaan asetusrivi {i+1} puuttuvien avainten vuoksi ({missing}): {item}")
            if not valid_settings:
                 logging.error("Asetustiedosto ei sisältänyt yhtään kelvollista pinnimääritystä (tai N oli > 12).")
                 return None
            logging.info(f"Löytyi {len(valid_settings)} kelvollista pinnin asetusta.")
            return valid_settings
    except FileNotFoundError:
        logging.error(f"Asetustiedostoa '{settings_path}' ei löytynyt (tarkistettu uudelleen).")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Asetustiedosto '{settings_path}' on virheellinen JSON: {e}")
        return None
    except IOError as e:
         logging.error(f"Asetustiedoston '{settings_path}' lukeminen epäonnistui: {e}")
         return None
    except Exception as e:
        logging.error(f"Odottamaton virhe ladattaessa asetuksia: {e}")
        return None

def setup_gpio():
    """Alustaa GPIO-kirjaston."""
    # ...(sisältö sama)...
    try:
        GPIO.setmode(GPIO_MODE)
        logging.info(f"GPIO-tila asetettu: {GPIO_MODE} (BCM)")
    except Exception as e:
        logging.error(f"GPIO-tilan ({GPIO_MODE}) asetus epäonnistui: {e}")
        raise RuntimeError(f"GPIO alustus epäonnistui: {e}")

def set_gpio_state(pin_number, state, identifier=""):
    """Asettaa annetun GPIO-pinnin tilan (True=ON, False=OFF)."""
    # ...(sisältö sama)...
    pin_id_str = f"Pinni {pin_number} ({identifier})" if identifier else f"Pinni {pin_number}"
    target_state_str = "ON (HIGH)" if state else "OFF (LOW)"
    gpio_value = GPIO.HIGH if state else GPIO.LOW
    try:
        GPIO.setup(pin_number, GPIO.OUT) 
        GPIO.output(pin_number, gpio_value)
        logging.info(f"{pin_id_str}: Tila asetettu -> {target_state_str}")
        return True
    except RuntimeError as e:
         logging.error(f"{pin_id_str}: GPIO Runtime Virhe tilaa {target_state_str} asettaessa: {e}. Tarkista pinnin numero ja oikeudet.")
         return False
    except ValueError as e:
         logging.error(f"{pin_id_str}: GPIO Value Virhe tilaa {target_state_str} asettaessa: {e}. Onko pinnin numero {pin_number} validi?")
         return False
    except Exception as e:
        logging.error(f"{pin_id_str}: Odottamaton GPIO-virhe tilaa {target_state_str} asettaessa: {e}")
        return False

# --- API-KUTSUFUNKTIOT ---

def check_price_limits(lower_limit_eur_mwh, upper_limit_eur_mwh):
    """Kutsuu API:a /JustNow/{lower}/{upper} tarkistaakseen hinnan suhteessa rajoihin."""
    # ...(sisältö sama)...
    try:
        lower_limit_int = int(round(lower_limit_eur_mwh)) 
        upper_limit_int = int(round(upper_limit_eur_mwh))
        url = f"{API_BASE_URL}/JustNow/{lower_limit_int}/{upper_limit_int}" 
        logging.info(f"API-KUTSU: {url}") 
        response = requests.get(url, timeout=API_TIMEOUT, headers={'accept': 'text/plain'}) 
        if response.status_code == 404:
             logging.error(f"API VIRHE: HTTP 404 kutsussa {url}. API ei löytänyt hintatietoja tälle hetkelle.")
             return None 
        elif response.status_code == 429:
             logging.error(f"API VIRHE: HTTP 429 kutsussa {url}. Liikaa pyyntöjä, hidasta.")
             return None
        response.raise_for_status() 
        try:
             result = int(response.text)
             logging.info(f"API VASTAUS: JustNow -> {result} ('0' <= alaraja, '1' välissä, '2' > yläraja)")
             if result not in [0, 1, 2]:
                 logging.warning(f"API VASTAUS: JustNow palautti odottamattoman arvon: {result}. Käsitellään virheenä.")
                 return None
             return result
        except ValueError:
             logging.error(f"API VIRHE: JustNow palautti ei-numeerisen vastauksen: '{response.text}'")
             return None
    except requests.exceptions.Timeout: logging.error(f"API VIRHE: Aikakatkaisu kutsussa {url}"); return None
    except requests.exceptions.ConnectionError: logging.error(f"API VIRHE: Yhteysvirhe kutsussa {url}"); return None
    except requests.exceptions.HTTPError as e: logging.error(f"API VIRHE: HTTP Virhe {e.response.status_code} kutsussa {url}. Vastaus: {e.response.text}"); return None
    except requests.exceptions.RequestException as e: logging.error(f"API VIRHE: Yleinen Request-virhe kutsussa {url}: {e}"); return None
    except Exception as e: logging.error(f"Odottamaton virhe check_price_limits funktiossa: {e}"); return None

def check_if_cheapest_hour(num_hours):
    """Kutsuu API:a /CheapestPeriodTodayCheck/{hours} tarkistaakseen, kuuluuko tunti N halvimpiin (1-12)."""
    # ...(sisältö sama)...
    if not 1 <= num_hours <= 12:
        logging.warning(f"API /CheapestPeriodTodayCheck tukee vain 1-12 tunnin tarkistusta, pyydetty N={num_hours}. Palautetaan None.")
        return None 
    url = f"{API_BASE_URL}/CheapestPeriodTodayCheck/{num_hours}"
    logging.info(f"API-KUTSU: {url}")
    try:
        response = requests.get(url, timeout=API_TIMEOUT)
        status_code = response.status_code
        logging.info(f"API VASTAUS: CheapestPeriodTodayCheck -> Status {status_code}")
        if status_code == 200: return True 
        elif status_code == 400:
            logging.info(f"API Info: CheapestPeriodTodayCheck (N={num_hours}) palautti 400 - tunti ei ole N halvimpien joukossa.")
            return False 
        elif status_code == 404: logging.error(f"API VIRHE: HTTP 404 kutsussa {url}. Hintatietoja ei löytynyt."); return None 
        elif status_code == 429: logging.error(f"API VIRHE: HTTP 429 kutsussa {url}. Liikaa pyyntöjä, hidasta."); return None 
        else: response.raise_for_status(); return None 
    except requests.exceptions.Timeout: logging.error(f"API VIRHE: Aikakatkaisu kutsussa {url}"); return None 
    except requests.exceptions.ConnectionError: logging.error(f"API VIRHE: Yhteysvirhe kutsussa {url}"); return None 
    except requests.exceptions.HTTPError as e: logging.error(f"API VIRHE: HTTP Virhe {e.response.status_code} kutsussa {url}. Vastaus: {e.response.text}"); return None 
    except requests.exceptions.RequestException as e: logging.error(f"API VIRHE: Yleinen Request-virhe kutsussa {url}: {e}"); return None 
    except Exception as e: logging.error(f"Odottamaton virhe check_if_cheapest_hour funktiossa: {e}"); return None 

# --- Pääohjelma ---

def main():
    """Pääohjelma, joka ajetaan tunneittain."""
    start_time = datetime.datetime.now(datetime.timezone.utc).astimezone() 
    logging.info("===== Ohjausohjelma Käynnistyy =====")
    
    pin_final_statuses = {} 

    # Varmistetaan datahakemiston olemassaolo
    try:
        # DATA_DIR on nyt määritelty globaalisti
        os.makedirs(DATA_DIR, exist_ok=True) 
        logging.info(f"Varmistettu datahakemiston olemassaolo: {DATA_DIR}")
    except OSError as e:
        logging.critical(f"KRIITTINEN VIRHE datahakemiston '{DATA_DIR}' luonnissa/varmistuksessa: {e}. Ohjelma lopetetaan.")
        sys.exit(1)

    # Alusta GPIO
    try:
        setup_gpio()
    except RuntimeError as e:
        logging.critical(f"GPIO alustus epäonnistui kriittisesti: {e}. Ohjelma lopetetaan.")
        sys.exit(1) 

    # Lataa asetukset (käyttää globaalia SETTINGS_FILE polkua)
    settings_list = load_settings()
    if not settings_list:
        logging.error("Asetuksia ei voitu ladata tai ne ovat tyhjät/virheellisiä. Ohjelma lopetetaan.")
        sys.exit(1) 

    # Käy läpi jokainen asetettu pinni
    for setting in settings_list:
        try:
            # ... (asetusten luku ja validointi kuten edellisessä versiossa) ...
            pin = setting['gpio_pin'] 
            identifier = setting.get('identifier', f'Pinni_{pin}') 
            upper_limit_ct = setting['upper_limit_ct_kwh'] 
            lower_limit_ct = setting['lower_limit_ct_kwh'] 
            try: rank_n = int(setting.get('cheapest_hours_n', 0)); assert 0 <= rank_n <= 12
            except: rank_n = 0 # Nollaus jos virheellinen

            logging.info(f"--- Käsitellään: {identifier} (GPIO {pin}) ---")
            logging.info(f"Asetukset: Yläraja={upper_limit_ct} ct/kWh, Alaraja={lower_limit_ct} ct/kWh, N={rank_n} (0-12)")

            lower_eur = float(lower_limit_ct) * 10.0
            upper_eur = float(upper_limit_ct) * 10.0

            desired_state = None 
            reason_string = "Tuntematon syy" 

            # 1. Tarkista hintarajat API:sta
            limit_check_result = check_price_limits(lower_eur, upper_eur)

            # Päätöksenteko ja syyn tallennus (sama logiikka)
            if limit_check_result is None: reason_string = "API-virhe hintarajatarkistuksessa"; desired_state = False 
            elif limit_check_result == 2: reason_string = f"Hinta > Yläraja ({upper_limit_ct} ct/kWh)"; desired_state = False 
            elif limit_check_result == 0: reason_string = f"Hinta <= Alaraja ({lower_limit_ct} ct/kWh)"; desired_state = True 
            elif limit_check_result == 1: 
                base_reason = f"Hinta välillä ({lower_limit_ct} - {upper_limit_ct}] ct/kWh"
                if rank_n > 0: # N:n pitäisi olla jo 1-12 tässä haarassa load_settings/rank_n tarkistuksen takia
                    is_cheap = check_if_cheapest_hour(rank_n) 
                    if is_cheap is None: reason_string = f"{base_reason}, N-tarkistus epäonnistui (API-virhe)"; desired_state = False 
                    elif is_cheap is True: reason_string = f"{base_reason}, kuuluu {rank_n} halvimpiin"; desired_state = True 
                    else: reason_string = f"{base_reason}, EI kuulu {rank_n} halvimpiin"; desired_state = False 
                else: reason_string = f"{base_reason}, N=0, ei tarkistusta"; desired_state = False 
            else: reason_string = f"Odottamaton API-tulos ({limit_check_result})"; desired_state = False
            if desired_state is None: reason_string = "Kriittinen logiikkavirhe"; desired_state = False

            # Tallenna lopullinen tila ja syy dictionaryyn
            pin_final_statuses[identifier] = { "pin": pin, "state": "ON" if desired_state else "OFF",
                "reason": reason_string, "timestamp": start_time.isoformat() }

            # Aseta GPIO-pinnin tila
            set_gpio_state(pin, desired_state, identifier)

        # Virheenkäsittelyt kuten ennen
        except KeyError as e: logging.error(f"Virheellinen asetusrivi: Avainta {e} ei löytynyt asetuksesta: {setting}. Ohitetaan."); continue 
        except (ValueError, TypeError) as e: logging.error(f"Virheellinen arvo asetuksessa {setting}: {e}. Ohitetaan."); continue
        except Exception as e: logging.error(f"Odottamaton virhe käsitellessä asetusta {setting}: {e}"); continue 

    # --- KIRJOITETAAN TIEDOSTOT AJON LOPUKSI ---

    # 1. KIRJOITA TILA HISTORIATIEDOSTOON (CSV)
    try:
        # Käytetään DATA_DIR polkua (CSV_LOG_FILE)
        csv_file_path = os.path.abspath(CSV_LOG_FILE) 
        file_exists = os.path.isfile(csv_file_path)
        needs_header = not file_exists or os.path.getsize(csv_file_path) == 0
        logging.info(f"Kirjoitetaan tilahistoriaa CSV-tiedostoon: {csv_file_path}")
        with open(csv_file_path, 'a', newline='', encoding='utf-8') as f_csv:
            csv_writer = csv.writer(f_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            if needs_header:
                header = ['Timestamp', 'PinNumber', 'Identifier', 'State', 'Reason']
                csv_writer.writerow(header)
            run_timestamp_iso = start_time.isoformat() 
            for identifier in sorted(pin_final_statuses.keys()):
                status_info = pin_final_statuses[identifier]
                row_data = [ run_timestamp_iso, status_info.get('pin', 'N/A'), identifier, 
                             status_info.get('state', 'N/A'), status_info.get('reason', 'N/A') ]
                csv_writer.writerow(row_data)
    except IOError as e: logging.error(f"VIRHE: CSV-historiatiedoston '{csv_file_path}' kirjoittaminen epäonnistui: {e}")
    except Exception as e: logging.error(f"VIRHE: Odottamaton virhe CSV-historiatiedoston kirjoituksessa: {e}")

    # 2. PÄIVITÄ VIIMEISIMMÄN TILAN JSON-TIEDOSTO
    try:
        # Käytetään DATA_DIR polkua (STATUS_FILE)
        status_file_path = os.path.abspath(STATUS_FILE) 
        logging.info(f"Päivitetään viimeisin tilatiedosto (JSON): {status_file_path}")
        with open(status_file_path, 'w', encoding='utf-8') as f_status:
            json.dump(pin_final_statuses, f_status, indent=4, ensure_ascii=False, sort_keys=True) 
    except IOError as e: logging.error(f"VIRHE: Tilatiedoston (JSON) '{status_file_path}' kirjoittaminen epäonnistui: {e}")
    except Exception as e: logging.error(f"VIRHE: Odottamaton virhe tilatiedoston (JSON) kirjoituksessa: {e}")
            
    end_time = datetime.datetime.now(datetime.timezone.utc).astimezone()
    duration = end_time - start_time
    logging.info(f"===== Ohjausohjelma Valmis (Kesto: {duration.total_seconds():.2f} s) =====")

# --- Pääohjelman Suoritus ---
if __name__ == "__main__":
    main()
