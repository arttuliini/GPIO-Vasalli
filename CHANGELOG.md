# Muutosloki

## [1.0.2] - 2025-03-31 

### Korjattu (Fixed)
- Korjattu yksikkövirhe `simulate_schedule.py`:n `filter_and_prepare_prices`-funktiossa. Sahkotin API:sta (`/prices`) saatu hinta (`value`), joka on jo valmiiksi ct/kWh, käytetään nyt suoraan ilman tarpeetonta jakoa kymmenellä. Tämä korjaa simulointitaulukon virheelliset ON/OFF-tilat.


## [1.0.1] - 2025-03-31 

### Korjattu (Fixed)
- Korjattu yksikkövirhe `hourly_control.py`:n `check_price_limits`-funktiossa (`api.spot-hinta.fi/JustNow`-kutsu). API:lle lähetetään nyt hintarajat oikein ct/kWh-yksikössä pyöristettyinä kokonaislukuina aiemman virheellisen EUR/MWh-oletuksen sijaan. Tämä korjaa virheellisen toiminnan tilanteissa, joissa hinta oli lähellä alarajaa.
- **MUUTETTU:** Hintojen ylä- ja alarajat (`upper_limit_ct_kwh`, `lower_limit_ct_kwh`) käsitellään nyt kaikkialla **kokonaislukuina** (senttiä/kWh) desimaalilukujen sijaan. Tämä poistaa pyöristysongelmat ja vastaa paremmin `/JustNow`-API:n vaatimuksia. `configure_settings.py` päivitetty kysymään ja tallentamaan kokonaislukuja. *Huom: Vanhat desimaaliarvoja sisältävät `settings.json`-tiedostot tulee päivittää ajamalla `configure_settings.py`.*
### Lisätty (Added)
- `CHANGELOG.md` muutoshistorian seurantaan.
- `SUUNNITELMA_V2.md` kuvaamaan seuraavan version arkkitehtuuria.
### Muutettu (Changed)
- Päivitetty `README.md` vastaamaan korjauksia ja uutta rakennetta.

## [1.0.0] - 2025-03-27 
### Lisätty (Added)
- Ensimmäinen toiminnallinen versio skripteistä: `configure_settings.py`, `hourly_control.py`, `simulate_schedule.py`, `show_gpio_status.py`.
- CSV-historian ja JSON-tilatiedoston kirjoitus.
- Dynaaminen polkujen käsittely ja keskitetty datahakemisto.
