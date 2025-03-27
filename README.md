# GPIO-Vasalli

**Python-työkalut Raspberry Pi:lle GPIO-lähtöjen (esim. releiden) automaattiseen ohjaukseen Suomen spot-sähkönhintojen perusteella. Sisältää tuntiohjauksen, simuloinnin ja asetusten hallinnan.**
**Tämä on tehty ja kehitetty harrastepohjalta omaan käyttöön. Kopioi ja plagioi ihan vapaasti, niin teki tämän kirjoittajakin (pääosin tekoäly)**

**Enemmän vakavasti otettavia kehityshankkeita varten kannattaa kurkistaa tänne: https://www.vasalli.fi**
---

**TÄRKEÄÄ: VASTUUVAPAUSLAUSEKE / DISCLAIMER**

* **KÄYTTÖ OMALLA VASTUULLA:** Tämän ohjelmiston ja sen ohjeiden käyttö tapahtuu täysin käyttäjän omalla vastuulla. Kehittäjä ei vastaa mistään ohjelmiston käytöstä aiheutuvista suorista tai epäsuorista vahingoista.
* **KOODATTU JA KIRJOITETTU TEKOÄLYLLÄ:** Kukaan ihminen ei ole edes lukenut, eikä varmaan tule lukemaankaan koko koodia itse - saati kommentteja tai näitä ohjeita.
* **EI TAKUUTA:** Ohjelmisto toimitetaan "sellaisenaan" ilman minkäänlaista takuuta, suoraa tai epäsuoraa, mukaan lukien, mutta ei rajoittuen, takuut soveltuvuudesta tiettyyn tarkoitukseen.
* **SÄHKÖTURVALLISUUS:** Verkkojännitteen (230V) kanssa työskentely on **HENGENVAARALLISTA**. Virheelliset kytkennät voivat aiheuttaa tulipalon, sähköiskun tai laitevaurioita. Vain pätevä sähköalan ammattilainen saa tehdä verkkojännitteeseen liittyviä asennuksia ja kytkentöjä. Älä tee itse kytkentöjä, jos et ole varma osaamisestasi!
* **LAITTEISTOYHTEENSOPIVUUS:** Ohjelmisto on kehitetty Raspberry Pi -laitteistolle ja olettaa tietynlaisen releen toimintalogiikan (oletuksena `GPIO.LOW`-signaali katkaisee virran). Toimivuutta muilla laitteistoilla tai releillä ei taata, ja koodi saattaa vaatia muutoksia.
* **API-RIIPPUVUUS:** Ohjelmisto hyödyntää ulkopuolisia API-palveluita (`api.spot-hinta.fi`, `sahkotin.fi`). Nämä palvelut voivat muuttua, lakata toimimasta tai palauttaa virheellistä tietoa ilman ennakkovaroitusta, mikä vaikuttaa ohjelmiston toimintaan. Käyttäjä on vastuussa APIen tilan seuraamisesta ja koodin päivittämisestä tarvittaessa. Virheellinen tai puuttuva API-data voi johtaa virheelliseen ohjaustoimintaan.
* **EI TALOUDELLISTA TAKUUTA:** Vaikka ohjelmiston tavoitteena on auttaa optimoimaan sähkönkäyttöä hinnan perusteella, sen käytöstä ei anneta takuuta taloudellisista säästöistä.
* **EI AMMATILLISTA NEUVONTAA:** Tämä ohjelmisto ja sen dokumentaatio eivät korvaa ammattimaista sähkösuunnittelua, asennusta tai taloudellista neuvontaa.
* **VASTUUNRAJOITUS:** Kehittäjä tai tämän työnantaja ei ole vastuussa mistään vahingoista (mukaan lukien laitevauriot, taloudelliset menetykset tai muut vahingot), jotka johtuvat tämän ohjelmiston tai sen dokumentation käytöstä tai kyvyttömyydestä käyttää sitä.

---

## Yleiskatsaus

GPIO-Vasalli on kokoelma Python-skriptejä, jotka on suunniteltu Raspberry Pi:lle ohjaamaan sen GPIO-pinnejä sähkön pörssihinnan (spot-hinta) mukaan. Sen avulla voit esimerkiksi automatisoida lämmityksen, latauksen tai muiden sähkölaitteiden käyttöä niin, että ne toimivat pääasiassa edullisimpien tuntien aikana.

Projekti sisältää seuraavat osat:

1.  **`configure_settings.py`:** Työkalu ohjausasetusten helppoon määrittelyyn.
2.  **`hourly_control.py`:** Tunnin välein ajettava pääskripti, joka tekee varsinaisen ohjauksen API-kutsujen perusteella.
3.  **`simulate_schedule.py`:** Työkalu, joka simuloi tulevien tai menneiden päivien ohjausaikataulun Sahkotin API:n hintadatan perusteella.
4.  **`show_gpio_status.py`:** Työkalu, joka näyttää nopeasti pinnien viimeisimmän tunnetun tilan ja syyn sille.

## Ominaisuudet

* Ohjaa GPIO-pinnejä ON/OFF perustuen asetettuihin ylä- ja alarajahintoihin (ct/kWh).
* Tukee ohjausta myös N halvimpien tunnin perusteella, kun hinta on rajojen välissä (käyttäen `api.spot-hinta.fi`, rajoitus N=1..12 `hourly_control.py`:ssä).
* Simulointityökalu tulevan tai menneen päivän ohjauksen ennustamiseen/tarkasteluun (käyttäen `sahkotin.fi` dataa, N=0..24).
* Interaktiivinen asetustyökalu (`configure_settings.py`).
* Tilan tarkistustyökalu (`show_gpio_status.py`).
* Luo automaattisesti keskitetyn hakemiston (`~/gpio_pricer_data/`) lokeille ja datatiedostoille.
* Tallentaa jatkuvaa historiaa CSV-tiedostoon Exceliä varten (`gpio_history.csv`).
* Tallentaa viimeisimmän tilan JSON-tiedostoon (`gpio_current_status.json`).

## Asennus

1.  **Vaatimukset:**
    * Raspberry Pi (testattu Raspberry Pi OS:llä) tai muu Linux-ympäristö Python 3 -tuella.
    * Python 3 (suositeltu versio 3.9 tai uudempi `zoneinfo`-tuen vuoksi).
    * Internet-yhteys API-kutsuja varten.

2.  **Kirjastojen Asennus:** Asenna tarvittavat Python-kirjastot `pip`-työkalulla:
    ```bash
    pip install requests RPi.GPIO pytz tzdata
    # Tai jos käytät Python 3.9+ et tarvitse välttämättä pytz/tzdata:
    # pip install requests RPi.GPIO 
    ```
    *(`pytz` ja `tzdata` ovat fallback aikavyöhykekäsittelyyn, jos `zoneinfo` ei ole saatavilla)*

3.  **Koodin Hankkiminen:** Kloonaa tämä repository tai lataa skriptitiedostot haluamaasi hakemistoon Raspberry Pi:lle (esim. `~/Ohjaus/`).
    ```bash
    # Esimerkki git clone -komennolla (korvaa <repositoryn_url> oikealla osoitteella)
    # git clone <repositoryn_url> ~/Ohjaus 
    # cd ~/Ohjaus
    ```
    Tai kopioi skriptit manuaalisesti tähän hakemistoon.

4.  **Asetusten Määritys:** Aja asetustyökalu ensimmäisen kerran määrittääksesi ohjattavat pinnit ja säännöt:
    ```bash
    python configure_settings.py
    # Tai python3 configure_settings.py
    ```
    Noudata ohjelman ohjeita. Tämä luo `settings.json`-tiedoston tähän samaan hakemistoon.

5.  **GPIO Oikeudet:** Varmista, että käyttäjällä, joka ajaa `hourly_control.py`-skriptiä, on oikeus käyttää GPIO-pinnejä. Helpoin tapa on lisätä käyttäjä `gpio`-ryhmään ja käynnistää Raspi uudelleen tai kirjautua ulos ja takaisin sisään:
    ```bash
    sudo adduser $USER gpio 
    # tai sudo adduser <käyttäjänimi> gpio
    # Reboot tai logout/login tämän jälkeen
    ```

## Hakemistorakenne

* **Skriptit + Asetukset:** `configure_settings.py`, `hourly_control.py`, `simulate_schedule.py`, `show_gpio_status.py`, `settings.json` sijaitsevat oletuksena samassa hakemistossa (esim. `~/Ohjaus/`).
* **Data ja Lokit:** Kaikki skriptien tuottamat tiedostot tallennetaan hakemistoon `~/gpio_pricer_data/`. Tämä hakemisto luodaan automaattisesti ensimmäisellä ajokerralla, jos sitä ei ole.
    * `gpio_control.log`: Tuntiohjausskriptin lokitiedosto.
    * `gpio_current_status.json`: Viimeisin pinnien tila JSON-muodossa.
    * `gpio_history.csv`: Jatkuva historia pinnien tiloista CSV-muodossa (Excel-yhteensopiva).
    * `simulation_schedule.txt`: Simulointityökalun tulostama aikataulutaulukko.

 ## Skriptien Käyttö

### `configure_settings.py`

* **Tarkoitus:** Asetusten hallinta.
* **Ajo:** Manuaalisesti komentoriviltä skriptihakemistossa:
    ```bash
    python configure_settings.py
    ```
* **Toiminta:** Seuraa valikkoa ja ohjeita lisätäksesi, muokataksesi, poistaaksesi tai näyttääksesi pinnien asetuksia. Tallenna ja lopeta valinnalla `0`.

### `hourly_control.py`

* **Tarkoitus:** Varsinainen ohjausskripti.
* **Ajo:** Ajastetusti tunnin välein (suositus). **Älä aja tätä jatkuvassa silmukassa!**
    * **Cron:** Lisää `crontab -e` -komennolla rivi (aja esim. minuutille 5):
        ```crontab
        5 * * * * /usr/bin/python3 /home/arttuli/Ohjaus/hourly_control.py 
        ```
        *(Muista korvata polku oikeaksi)*
    * **Systemd Timer:** (Vaatii service- ja timer-tiedostojen luomisen, edistyneempi tapa)
    * **Manuaalinen Testaus:** Voit ajaa kerran komennolla `python hourly_control.py`.
* **Toiminta:** Lukee `settings.json`, tekee API-kutsut, ohjaa GPIO-pinnejä, kirjoittaa lokin, JSON-statuksen ja CSV-historian `~/gpio_pricer_data/`-hakemistoon.

### `simulate_schedule.py`

* **Tarkoitus:** Simuloi ohjausta halutulle päivälle.
* **Ajo:** Manuaalisesti komentoriviltä skriptihakemistossa:
    * `python simulate_schedule.py` tai `python simulate_schedule.py --today` (Tälle päivälle)
    * `python simulate_schedule.py --tomorrow` (Huomiselle)
    * `python simulate_schedule.py --date VVVV-KK-PP` (Tietylle päivälle)
* **Toiminta:** Hakee hintaennusteen Sahkotin API:sta, lukee `settings.json`, laskee paikallisesti pinnien tilat jokaiselle tunnille ja kirjoittaa tulostaulukon tiedostoon `~/gpio_pricer_data/simulation_schedule.txt`.

### `show_gpio_status.py`

* **Tarkoitus:** Näyttää viimeisimmän tunnetun tilan pinneille.
* **Ajo:** Manuaalisesti komentoriviltä skriptihakemistossa:
    ```bash
    python show_gpio_status.py
    ```
* **Toiminta:** Lukee `~/gpio_pricer_data/gpio_current_status.json` -tiedoston ja tulostaa sen sisällön selkeänä taulukkona komentoriville. Näyttää myös, milloin tila on viimeksi päivitetty.

## Konfiguraatio (`settings.json`)

`configure_settings.py` luo ja muokkaa tätä tiedostoa. Se on lista JSON-objekteja, joista jokainen kuvaa yhden pinnin asetukset:

```json
[
    {
        "gpio_pin": 16, 
        "identifier": "LVV_Esimerkki",
        "upper_limit_ct_kwh": 8.0,
        "lower_limit_ct_kwh": 1.0,
        "cheapest_hours_n": 3 
    },
    {
        "gpio_pin": 20,
        "identifier": "Lattia_Esimerkki",
        "upper_limit_ct_kwh": 5.0,
        "lower_limit_ct_kwh": 0.0,
        "cheapest_hours_n": 5
    }
]
``` 

* `gpio_pin`: Ohjattavan pinnin numero (BCM-numeroinnilla).
* `identifier`: Vapaamuotoinen nimi pinnille (näkyy lokeissa ja tulosteissa).
* `upper_limit_ct_kwh`: Hinnan yläraja (senttiä/kWh sis. ALV), jonka ylittyessä pinni on POIS.
* `lower_limit_ct_kwh`: Hinnan alaraja (senttiä/kWh sis. ALV), jonka alittuessa pinni on PÄÄLLÄ.
* `cheapest_hours_n`: Kuinka monen halvimmista tunnista pinni on PÄÄLLÄ, jos hinta on rajojen välissä (**0-12** `hourly_control.py`:ssä API-rajoituksen vuoksi, **0-24** `simulate_schedule.py`:ssä). 0 = toiminto pois käytöstä.

## Generoidut Tiedostot (`~/gpio_pricer_data/`)

* `gpio_control.log`: Yksityiskohtainen loki `hourly_control.py`:n ajoista. Hyödyllinen vianetsinnässä.
* `gpio_current_status.json`: JSON-tiedosto, joka sisältää *vain viimeisimmän* tilan ja syyn kullekin pinnille. `show_gpio_status.py` käyttää tätä.
* `gpio_history.csv`: CSV-tiedosto, johon `hourly_control.py` lisää rivin kullekin pinnille jokaisen ajon yhteydessä. Sisältää aikaleiman, pinnin numeron, tunnisteen, tilan (ON/OFF) ja syyn. Sopii historian tarkasteluun ja esim. Exceliin tuotavaksi.
* `simulation_schedule.txt`: `simulate_schedule.py`:n tuottama tekstitiedosto, joka sisältää simuloidun tuntikohtaisen ON/OFF-aikataulutaulukon.

## Huomioitavaa

* **Relelogiikka:** Koodi olettaa, että `GPIO.LOW` (0V) signaali aktivoi releen katkaisemaan virran (lämmitys POIS) ja `GPIO.HIGH` (3.3V) tai kelluva tila päästää virran läpi (lämmitys PÄÄLLÄ). Varmista releesi ja kytkentöjesi toiminta!
* **N:n Rajoitus (1-12):** `hourly_control.py` käyttää `api.spot-hinta.fi`:n `/CheapestPeriodTodayCheck`-kutsua, joka tukee vain N=1..12. Jos N=0 tai N>12, halvimpien tuntien logiikkaa ei suoriteta, ja pinni on POIS, jos hinta on rajojen välissä. `simulate_schedule.py` laskee N halvinta tuntia paikallisesti ja tukee N=0..24.
* **Lokien Hallinta:** `gpio_control.log` ja `gpio_history.csv` kasvavat jatkuvasti. Harkitse lokien rotaation (`logrotate` tai Pythonin `RotatingFileHandler`) tai CSV-tiedoston säännöllisen tyhjennyksen/arkistoinnin käyttöönottoa pitkäaikaisessa käytössä.
* **Virhetilanteet:** Seuraa lokitiedostoja (`gpio_control.log`) varmistaaksesi, että skripti toimii luotettavasti. Harkitse erillisen virheilmoitusjärjestelmän lisäämistä, jos ohjaus on kriittistä.

## Kehitys (Ideoita)

* Lokien automaattinen rotaatio/hallinta.
* Aktiivinen ilmoitusjärjestelmä virhetilanteista.
* Web-käyttöliittymä asetusten hallintaan ja tilan seurantaan.
* Monimutkaisempi ohjauslogiikka (esim. ennakoiva ohjaus, sääennusteiden huomiointi).
* Tuki useammille API-lähteille.

## Yhteystiedot
* https://github.com/arttuliini/GPIO-Vasalli/
* https://www.vasalli.fi
* Arttu Kotilainen

---

