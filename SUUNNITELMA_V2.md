# GPIO-Vasalli - Version 2 Suunnitelma (Päivitetty)

Tämä dokumentti kuvaa suunnitellut muutokset ja parannukset GPIO-Vasalli -projektiin versiossa 2. Tavoitteena on parantaa järjestelmän vankkuutta, joustavuutta, laajennettavuutta ja käyttäjän kontrollia verrattuna versioon 1.x.

## Arkkitehtuurimuutos: Modulaarinen Malli (V2)

Nykyinen versio (v1.x) käyttää pääosin yhtä `hourly_control.py`-skriptiä, joka hoitaa sekä API-tarkistukset (`api.spot-hinta.fi`) että GPIO-ohjauksen. Tämä malli on altis API-palveluiden häiriöille ja rajoituksille (kuten N=1..12 halvimmille tunneille) ja sen simulointi on epätarkkaa eri datalähteen (`sahkotin.fi`) vuoksi.

Versiossa 2 siirrytään modulaarisempaan arkkitehtuuriin, jossa vastuut on jaettu selkeämmin useammalle komponentille. **Ydinautomaatio koostuu kolmesta ajastetusti ajettavasta skriptistä**, joiden lisäksi kokonaisuuteen kuuluu manuaalisesti ajettavia työkaluja ja konfiguraatiotiedostoja:

### 1. `price_updater.py` (Datan Päivittäjä)

* **Ajo:** Ajastetusti harvemmin (esim. `cron` avulla 4-12h välein tai kerran päivässä n. klo 14:15 jälkeen).
* **Tehtävä:**
    * Hakee hintatiedot luotettavasta lähteestä (oletus: Sahkotin `/prices` API, joka palauttaa ct/kWh).
    * Valmistelee datan: käsittelee aikaleimat ja aikavyöhykkeet (UTC -> paikallinen), varmistaa datan eheyden.
    * Tallentaa valmiiksi käsitellyn datan päivämääräkohtaisesti välimuistitiedostoon (`price_cache.json`), käyttäen avaimia, jotka vastaavat datan tarkkuutta (esim. `"HH:MM"`).
    * Tulevaisuudessa voi hakea ja tallentaa myös muuta dataa (lämpötila, sääennuste) omaan tiedostoonsa (`sensor_data.json` tms.).
    * Vastuussa kaikesta ulkoisesta API-kommunikaatiosta ja datan esikäsittelystä.
    * Sisältää oman lokituksensa (`price_updater.log` tms.).

### 2. `schedule_builder.py` (Aikataulun Rakentaja)

* **Ajo:**
    * **Automaattisesti:** Kerran päivässä (`cron`, esim. klo 14:30) laskemaan **seuraavan päivän** aikataulun (käyttäen `--tomorrow`-parametria).
    * **Manuaalisesti:** Käyttäjä voi ajaa tämän skriptin komentoriviltä **päivittääkseen kuluvan (`--today`), seuraavan (`--tomorrow`) tai tietyn päivän (`--date VVVV-KK-PP`) aikataulun** esimerkiksi asetusten muuttamisen jälkeen.
* **Tehtävä:**
    * Lukee kohdepäivän valmistellut hintatiedot `price_cache.json`:sta.
    * Lukee käyttäjän `settings.json`-asetukset (sis. pinnit, tunnisteet, kokonaislukurajat L/U, N=0-24, `hysteresis_ct_kwh`, `startup_factor`).
    * Lukee mahdolliset manuaaliset ohitukset `manual_override.json`:sta.
    * **Laskee valmiin ON/OFF-aikataulun** kohdepäivälle toteuttaen varsinaisen ohjauslogiikan:
        * **Hystereesi:** Estää turhaa releiden kytkentää raja-arvojen lähellä käyttäen `hysteresis_ct_kwh`-asetusta ja edellisen jakson tilaa.
        * **N Halvinta Jaksoa & Käynnistyskulutus:** Laskee päivän N halvinta jaksoa käyttäen `find_cheapest_intervals_with_startup_cost`-funktiota, joka painottaa hintoja `startup_factor`-kertoimella arvioiduissa käynnistyskohdissa.
        * **Päätöksenteko:** Soveltaa hintavertailua (hystereesillä) ja N halvimpien jaksojen logiikkaa jokaiselle jaksolle ja pinnille.
    * Yhdistää lasketun aikataulun `manual_override.json`:sta luettuihin pakotettuihin tiloihin (manuaalinen ohitus ylikirjoittaa hintaperusteisen).
    * Tallentaa lopullisen, valmiin aikataulun **sekä tilan että syyn** `control_schedule.json`-tiedostoon. Tiedoston rakenne mahdollistaa useamman päivän aikataulujen tallentamisen, mutta oletuksena käsitellään yhtä päivää kerrallaan.
    * **Ilmoitukset:** Jos hintojen luku välimuistista epäonnistuu tai aikataulun laskenta ei onnistu, lokittaa kriittisen virheen ja voi tulevaisuudessa lähettää ilmoituksen käyttäjälle.

### 3. `hourly_control.py` (Yksinkertaistettu Suorittaja)

* **Ajo:** Tiheästi (`cron` tai `systemd timer`), käyttäjän haluaman resoluution mukaan (tunnin tai 15 minuutin välein – **ajovälin tulee vastata datan ja halutun ohjauksen tarkkuutta!**).
* **Tehtävä:** Erittäin yksinkertainen ja vankka:
    * Lukee nykyisen ajan ja päivämäärän. Määrittää nykyisen ajanjakson avaimen (`"HH:MM"`).
    * Lukee **valmiin aikataulun ja syyn** `control_schedule.json`-tiedostosta tälle päivälle ja nykyiselle ajanjaksolle.
    * **Ohjaa GPIO-pinniä täsmälleen aikataulussa määritellyn `state`-arvon ("ON" / "OFF") mukaisesti.**
    * **Fallback:** Jos aikataulua (`control_schedule.json`), kuluvan päivän dataa tai nykyisen jakson tietoa ei löydy, asettaa kaikki pinnit turvalliseen OFF-tilaan ja lokittaa kriittisen virheen.
    * Ei tee API-kutsuja, ei laske hintalogiikkaa.
    * Päivittää `gpio_current_status.json`- ja `gpio_history.csv`-tiedostot luetun aikataulun ja syyn perusteella.

### 4. `find_cheapest_window.py` (Ajanjakson Optimointityökalu)

* **Ajo:** Manuaalisesti komentoriviltä tarvittaessa.
* **Tehtävä:** Auttaa käyttäjää varmistamaan tietyn määrän ajoa ennen määräaikaa (esim. "LVV:lle 3h ajoa ennen klo 07:00").
* **Syötteet:** Pinnin tunniste (`--identifier`), tarvittavien **jaksojen** määrä (`--intervals N`), määräaika (`--until VVVV-KK-PPTHH:MM`), lippu (`--output-override`).
* **Toiminta:**
    * Lukee hinnat `price_cache.json`:sta kohdepäivälle.
    * Suodattaa jaksot väliltä 00:00 - annettu määräaika.
    * Etsii suodatetusta joukosta N halvinta jaksoa (voi käyttää samaa `find_cheapest_intervals_with_startup_cost`-funktiota startup-kertoimella 1.0).
    * Tulostaa löydetyt jaksot käyttäjälle.
    * Jos `--output-override` annettu, lisää/päivittää `manual_override.json`-tiedostoon merkinnän, joka pakottaa nämä löydetyt jaksot tilaan "ON" kyseiselle pinni/päivä-parille.

### Muut Komponentit

* **`configure_settings.py`:** Kuten V1, mutta hallitsee `settings.json`:ia, johon lisätty `hysteresis_ct_kwh` ja `startup_factor`. Ei enää käynnistä aikataulun rakentajaa.
* **`show_gpio_status.py`:** Kuten V1, lukee `gpio_current_status.json`:ia.
* **`settings.json`:** Määrittelee pinnikohtaiset säännöt: `gpio_pin`, `identifier`, `upper_limit_ct_kwh` (int), `lower_limit_ct_kwh` (int), `cheapest_periods_n` (0-24 tai 0-96), `hysteresis_ct_kwh` (float), `startup_factor` (float).
* **`price_cache.json`:** Välimuisti haetuille ja käsitellyille hintatiedoille (`{päivä_str: {"HH:MM": hinta_ct}}`).
* **`control_schedule.json`:** Valmis aikataulu, jonka `schedule_builder.py` luo ja `hourly_control.py` suorittaa (`{päivä_str: {"pin_id": {"pin": X, "schedule": {"HH:MM": {"state": "ON/OFF", "reason": "..."}, ...}}}}`).
* **`manual_override.json`:** Käyttäjän määrittelemät pakotetut ON/OFF-jaksot `schedule_builder.py`:lle.

## Suunnitellut Uudet Ominaisuudet (V2 Yhteenveto)

* **Vankka Modulaarinen Arkkitehtuuri:** Selkeä vastuunjako skriptien välillä.
* **Paikallinen Päätöksentekologiikka:** Vähentää API-riippuvuuksia ja mahdollistaa monipuolisemmat säännöt.
* **Hystereesi:** Vähentää turhaa kytkentää hintarajojen lähellä.
* **Käynnistyskulutuksen Huomiointi:** Optimoi halvimpien jaksojen valintaa.
* **Joustava Asetusmuutosten Aktivointi:** Käyttäjä kontrolloi, milloin muutokset lasketaan aikatauluun (manuaalinen `schedule_builder.py` -ajo).
* **Manuaaliset Ohitukset:** Helppo tapa pakottaa laitteita päälle/pois tarvittaessa.
* **Ajanjakson Optimointityökalu:** `find_cheapest_window.py` erityistarpeisiin.
* **Ennakoiva Virheilmoitus:** `schedule_builder.py` voi varoittaa, jos aikataulua ei voida luoda.
* **Valmius 15min Resoluutioon:** Rakenne tukee siirtymistä natiivisti.
* **Laajennettavuus:** Selkeä paikka lisätä tulevaisuudessa esim. lämpötilaohjaus (`schedule_builder.py`:n logiikkaan).

## Toteutusaikataulu

Tämän version kehitys aloitetaan myöhemmin. Nykyinen v1.x pysyy päähaarassa toistaiseksi.

