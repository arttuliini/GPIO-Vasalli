#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
configure_settings.py

Interaktiivinen työkalu GPIO-ohjauksen asetusten (pinnit, rajahinnat, N) 
luomiseen ja muokkaamiseen. Tallentaa asetukset settings.json-tiedostoon
skriptin omaan ajohakemistoon.
"""

import json
import os
import sys

# --- Konfiguraatio ja Polut ---

# Hakemisto, jossa tämä skriptitiedosto sijaitsee
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) 

# Asetustiedoston polku SUHTEESSA skriptin sijaintiin
SETTINGS_FILE = os.path.join(SCRIPT_DIR, 'settings.json') 

# --- Funktiot ---

def load_settings():
    """Lataa asetukset JSON-tiedostosta (käyttää globaalia SETTINGS_FILE polkua)."""
    # Käytetään nyt globaalisti määriteltyä SETTINGS_FILE polkua
    settings_path = os.path.abspath(SETTINGS_FILE) 
    if not os.path.exists(settings_path):
        print(f"Asetustiedostoa '{settings_path}' ei löytynyt. Luodaan uusi.")
        return {} 
    print(f"Ladataan asetukset tiedostosta: {settings_path}")
    # ...(Loput funktiosta pysyy samana kuin edellisessä versiossa)...
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings_list = json.load(f)
            if not isinstance(settings_list, list):
                 print(f"VAROITUS: Asetustiedosto '{settings_path}' ei sisältänyt listaa. Aloitetaan tyhjästä.")
                 return {}
            settings_dict = {}
            valid_pins_found = 0
            for i, item in enumerate(settings_list):
                if isinstance(item, dict) and 'gpio_pin' in item:
                    pin_num = item['gpio_pin']
                    try:
                        pin_num_int = int(pin_num)
                        if pin_num_int <= 0: raise ValueError("Pinninumeron tulee olla positiivinen")
                        n_val = item.get('cheapest_hours_n', 0)
                        if not (0 <= int(n_val) <= 12):
                            print(f"VAROITUS: Pinnin {pin_num_int} 'cheapest_hours_n' ({n_val}) tiedostossa ei ole välillä 0-12. Korjaa asetukset.")
                            item['cheapest_hours_n'] = 0 
                        if 'identifier' not in item or not item['identifier']: item['identifier'] = f"Pin_{pin_num_int}"
                        settings_dict[pin_num_int] = item
                        valid_pins_found += 1
                    except (ValueError, TypeError) as e: print(f"VAROITUS: Ohitetaan virheellinen asetusrivi {i+1}: {item}, Virhe: {e}")
                else: print(f"VAROITUS: Ohitetaan virheellinen tai puutteellinen asetusrivi {i+1}: {item}")
            if valid_pins_found > 0: print(f"Ladattu {valid_pins_found} pinnin asetukset.")
            else: print("Asetustiedosto oli tyhjä tai ei sisältänyt kelvollisia asetuksia.")
            return settings_dict
    except json.JSONDecodeError: print(f"VIRHE: Asetustiedosto '{settings_path}' on virheellisessä muodossa."); return None 
    except IOError as e: print(f"VIRHE: Asetustiedoston '{settings_path}' lukeminen epäonnistui: {e}", file=sys.stderr); return None
    except Exception as e: print(f"VIRHE: Odottamaton virhe ladattaessa asetuksia: {e}"); return None

def save_settings(settings_dict):
    """Tallentaa asetukset JSON-tiedostoon (käyttää globaalia SETTINGS_FILE polkua)."""
    # Käytetään nyt globaalisti määriteltyä SETTINGS_FILE polkua
    settings_path = os.path.abspath(SETTINGS_FILE) 
    settings_list = list(settings_dict.values())
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings_list, f, indent=4, ensure_ascii=False, sort_keys=True) 
        print(f"\nAsetukset tallennettu tiedostoon '{settings_path}'.")
        return True
    except IOError as e: print(f"VIRHE: Tallentaminen tiedostoon '{settings_path}' epäonnistui: {e}"); return False
    except Exception as e: print(f"VIRHE: Odottamaton virhe tallennettaessa asetuksia: {e}"); return False

# get_validated_input, display_settings, edit_or_add_pin, delete_pin pysyvät samoina
def get_validated_input(prompt, default=None, value_type=str, condition=None, error_msg="Virheellinen syöte.", allow_empty=False):
    while True:
        prompt_full = f"{prompt}"
        valid_default = None
        if default is not None:
            try: value_type(default); valid_default = default; prompt_full += f" [Oletus: {valid_default}]"
            except: pass 
        prompt_full += ": "
        user_input = input(prompt_full).strip()
        if not user_input and valid_default is not None:
            try:
                 default_value_typed = value_type(valid_default)
                 if condition is None or condition(default_value_typed): return default_value_typed
                 else: print(f"Oletusarvo {valid_default} ei täytä ehtoa."); default = None; valid_default = None; continue
            except: print(f"Sisäinen virhe oletusarvon '{valid_default}' käsittelyssä."); default = None; valid_default = None; continue
        if not user_input and allow_empty: return "" 
        if not user_input and not allow_empty and valid_default is None: print("Syöte ei voi olla tyhjä."); continue
        try:
            if value_type == str and allow_empty and user_input == "": value = user_input
            else: value = value_type(user_input)
            if condition is None or condition(value): return value
            else: print(error_msg) 
        except ValueError:
            type_name_map = {int: "kokonaisluku", float: "desimaaliluku", str: "merkkijono"}
            expected_type = type_name_map.get(value_type, value_type.__name__)
            print(f"Virheellinen syöte. Anna arvo tyyppiä {expected_type}.")
        except Exception as e: print(f"Odottamaton virhe syötteen käsittelyssä: {e}")

def display_settings(settings_dict):
    print("\n--- Nykyiset Asetukset ---")
    if not settings_dict: print("Ei määriteltyjä pinnejä."); return
    sorted_pins = sorted(settings_dict.keys())
    for pin_num in sorted_pins:
        setting = settings_dict[pin_num]
        print(f" Pin {pin_num}:\n  Tunniste: {setting.get('identifier', 'N/A')}\n  Yläraja: {setting.get('upper_limit_ct_kwh', 'N/A')} ct/kWh\n  Alaraja: {setting.get('lower_limit_ct_kwh', 'N/A')} ct/kWh\n  N (halvimmat): {setting.get('cheapest_hours_n', 'N/A')} (0-12)\n" + "-" * 20)

def edit_or_add_pin(settings_dict):
    print("\n--- Muokkaa tai lisää pinni ---")
    gpio_pin = get_validated_input("Anna muokattavan/lisättävän GPIO-pinnin numero (BCM, > 0)", value_type=int, condition=lambda x: x > 0, error_msg="Anna positiivinen kokonaisluku.")
    existing_setting = settings_dict.get(gpio_pin)
    is_editing = existing_setting is not None
    if is_editing: print(f"Muokataan pinnin {gpio_pin} asetuksia.")
    else: print(f"Lisätään uusi pinni {gpio_pin}."); existing_setting = {} 
    identifier = get_validated_input(f"Anna tunniste pinniä {gpio_pin} varten", default=existing_setting.get('identifier'), value_type=str, allow_empty=False)
    upper_limit = get_validated_input(f"Anna hinnan yläraja (senttiä/kWh)", default=existing_setting.get('upper_limit_ct_kwh'), value_type=float, condition=lambda x: x >= 0, error_msg="Rajahinnan tulee olla >= 0.")
    lower_limit = get_validated_input(f"Anna hinnan alaraja (senttiä/kWh)", default=existing_setting.get('lower_limit_ct_kwh'), value_type=float, condition=lambda x: x >= 0 and x <= upper_limit, error_msg=f"Alarajan tulee olla >= 0 ja <= {upper_limit}.")
    print(f"\nHalvimpien tuntien ohjaus (N) aktivoituu, kun hinta on välillä ({lower_limit} - {upper_limit}] ct/kWh.\nHUOM: API tukee N arvoja vain välillä 1-12. N=0 ei käytä tätä toimintoa.")
    cheapest_hours_n = get_validated_input(f"Anna N (halvimpien tuntien määrä)", default=existing_setting.get('cheapest_hours_n', 0), value_type=int, condition=lambda x: 0 <= x <= 12, error_msg="Anna luku väliltä 0-12 (API-rajoitus)." )
    settings_dict[gpio_pin] = { "gpio_pin": gpio_pin, "identifier": identifier, "upper_limit_ct_kwh": upper_limit, "lower_limit_ct_kwh": lower_limit, "cheapest_hours_n": cheapest_hours_n }
    print(f"Pinnin {gpio_pin} ({identifier}) tiedot päivitetty muistiin.")

def delete_pin(settings_dict):
    print("\n--- Poista pinnin asetus ---")
    if not settings_dict: print("Ei määriteltyjä pinnejä poistettavaksi."); return
    display_settings(settings_dict) 
    gpio_pin_to_delete = get_validated_input("Anna poistettavan GPIO-pinnin numero", value_type=int, condition=lambda x: x > 0, error_msg="Anna positiivinen kokonaisluku.")
    if gpio_pin_to_delete in settings_dict:
        identifier = settings_dict[gpio_pin_to_delete].get('identifier', f'Pinni {gpio_pin_to_delete}')
        confirmation = get_validated_input(f"Haluatko varmasti poistaa pinnin {gpio_pin_to_delete} ({identifier}) asetukset? (k/e)", default='e', value_type=str, condition=lambda x: x.lower() in ['k', 'e'], error_msg="Vastaa 'k' tai 'e'." )
        if confirmation.lower() == 'k': del settings_dict[gpio_pin_to_delete]; print(f"Pinni {gpio_pin_to_delete} poistettu muistista.")
        else: print("Poisto peruutettu.")
    else: print(f"Pinniä {gpio_pin_to_delete} ei löytynyt asetuksista.")

def main():
    """Pääohjelma asetusten hallintaan valikon kautta."""
    print("--- GPIO Ohjaus Sähkön Hinnalla - Asetusten Hallinta ---")
    # Käytetään globaalia SETTINGS_FILE polkua
    settings = load_settings() 
    if settings is None: sys.exit(1) 
    while True:
        print("\n--- Päävalikko ---")
        print("1. Muokkaa tai lisää pinnin asetuksia\n2. Poista pinnin asetus\n3. Näytä nykyiset asetukset\n0. Tallenna muutokset ja lopeta")
        choice = get_validated_input("Valitse toiminto (0-3)", value_type=int, condition=lambda x: 0 <= x <= 3, error_msg="Virheellinen valinta.")
        if choice == 1: edit_or_add_pin(settings)
        elif choice == 2: delete_pin(settings)
        elif choice == 3: display_settings(settings)
        elif choice == 0:
            # Käytetään globaalia SETTINGS_FILE polkua
            if save_settings(settings): print("Muutokset tallennettu. Lopetetaan.")
            else:
                confirm_exit = get_validated_input("Tallennus epäonnistui. Haluatko silti lopettaa tallentamatta? (k/e)", default='e', value_type=str, condition=lambda x: x.lower() in ['k','e'])
                if confirm_exit.lower() == 'k': print("Lopetetaan tallentamatta.")
                else: print("Palataan valikkoon."); continue 
            break 
    print("\nAsetusten hallinta päättyi.")

if __name__ == "__main__":
    main()
