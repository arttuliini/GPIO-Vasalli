# GPIO-Vasalli

**Python-työkalut Raspberry Pi:lle GPIO-lähtöjen (esim. releiden) automaattiseen ohjaukseen Suomen spot-sähkönhintojen perusteella. Sisältää tuntiohjauksen, simuloinnin ja asetusten hallinnan.**
**Tämä on tehty ja kehitetty harrastepohjalta omaan käyttöön. Kopioi ja plagioi ihan vapaasti, niin teki tämän kirjoittajakin (pääosin tekoäly)**

**Enemmän vakavasti otettavia kehityshankkeita varten kannattaa kurkistaa tänne: https://www.vasalli.fi**
---

**TÄRKEÄÄ: VASTUUVAPAUSLAUSEKE / DISCLAIMER**

* **KÄYTTÖ OMALLA VASTUULLA:** Tämän ohjelmiston ja sen ohjeiden käyttö tapahtuu täysin käyttäjän omalla vastuulla. Kehittäjä ei vastaa mistään ohjelmiston käytöstä aiheutuvista suorista tai epäsuorista vahingoista.
* **KOODATTU JA KIRJOITETTU TEKOÄLYLLÄ:** Kukaan ihminen ei ole edes lukenut, eikä varmaan tule lukemaankaan koko koodia itse - saati kommentteja tai näitä ohjeita. *(Huom: Tämä on käyttäjän alkuperäinen lisäys, kannattaa harkita sen sanamuotoa virallisemmassa julkaisussa)*
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

* Ohjaa GPIO-pinnejä ON/OFF perustuen asetettuihin ylä- ja alarajahintoihin (**kokonaislukuina**, ct/kWh).
* `hourly_control.py` käyttää `api.spot-hinta.fi` -palvelun `/JustNow/{alaraja_ct}/{ylaraja_ct}` -kutsua hintarajojen tarkistukseen (lähettää rajat ct/kWh kokonaislukuina).
* Tukee ohjausta myös N halvimpien tunnin perusteella, kun hinta on rajojen välissä (käyttäen `api.spot-hinta.fi` `/CheapestPeriodTodayCheck/{hours}` -kutsua, rajoitus N=1..12).
* Simulointityökalu tulevan tai menneen päivän ohjauksen ennustamiseen/tarkasteluun (`simulate_schedule.py`, käyttäen `sahkotin.fi` dataa, N=0..24).
* Interaktiivinen asetustyökalu (`configure_settings.py`), joka kysyy rajat kokonaislukuina.
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
    # git clone [https://github.com/arttuliini/GPIO-Vasalli.git](https://github.com/arttuliini/GPIO-Vasalli.git) ~/Ohjaus 
    # cd ~/Ohjaus
    ```
    Tai kopioi skriptit manuaalisesti tähän hakemistoon.

4.  **Asetusten Määritys:** Tämä projekti käyttää paikallista `settings.json`-tiedostoa, jota **ei tallenneta Git-versionhallintaan** (`.gitignore` estää tämän).
    * **Kopioi ensin mallitiedosto:** Luo oma asetustiedostosi kopioimalla projektin mukana tuleva esimerkki:
      ```bash
      # Varmista, että olet projektin pääkansiossa (esim. ~/Ohjaus)
      cp settings.example.json settings.json
      ```
    * **Muokkaa asetuksia:** Aja asetustyökalu muokataksesi juuri luotua `settings.json`-tiedostoa omilla pinninumeroillasi ja ohjaussäännöilläsi (alaraja, yläraja, N jne.):
      ```bash
      python configure_settings.py
      # Tai python3 configure_settings.py
      ```
    Noudata ohjelman valikoita ja ohjeita. Tallenna muutokset valinnalla `0`.

5.  **GPIO Oikeudet:** Varmista, että käyttäjällä, joka ajaa `hourly_control.py`-skriptiä, on oikeus käyttää GPIO-pinnejä:
    ```bash
    sudo adduser $USER gpio 
    # Reboot tai logout/login tämän jälkeen
    ```

## Hakemistorakenne

* **Skriptit + Asetukset:** `configure_settings.py`, `hourly_control.py`, `simulate_schedule.py`, `show_gpio_status.py`, `settings.json` sijaitsevat oletuksena samassa hakemistossa (esim. `~/Ohjaus/`).
* **Data ja Lokit:** Kaikki skriptien tuottamat tiedostot tallennetaan hakemistoon `~/gpio_pricer_data/`. Tämä hakemisto luodaan automaattisesti.
    * `gpio_control.log`: Tuntiohjausskriptin lokitiedosto.
    * `gpio_current_status.json`: Viimeisin pinnien tila JSON-muodossa.
    * `gpio_history.csv`: Jatkuva historia pinnien tiloista CSV-muodossa.
    * `simulation_schedule.txt`: Simulointityökalun tulostama aikataulutaulukko.


## Skriptien Käyttö

### `configure_settings.py`

* **Tarkoitus:** Asetusten hallinta. Kysyy nyt rajat **kokonaislukuina** (ct/kWh).
* **Ajo:** Manuaalisesti komentoriviltä skriptihakemistossa:
    ```bash
    python configure_settings.py
    ```
* **Toiminta:** Seuraa valikkoa ja ohjeita lisätäksesi, muokataksesi, poistaaksesi tai näyttääksesi pinnien asetuksia. Tallenna ja lopeta valinnalla `0`.

### `hourly_control.py`

* **Tarkoitus:** Varsinainen ohjausskripti.
* **Ajo:** Ajastetusti tunnin välein (suositus). **Älä aja tätä jatkuvassa silmukassa!**
    * **Cron:** Esimerkki:
        ```crontab
        5 * * * * /usr/bin/python3 /home/arttuli/Ohjaus/hourly_control.py 
        ```
        *(Muista korvata polku oikeaksi)*
    * **Manuaalinen Testaus:** `python hourly_control.py`.
* **Toiminta:** Lukee `settings.json`, tekee API-kutsut (käyttäen kokonaislukurajoja `/JustNow`-kutsussa), ohjaa GPIO-pinnejä, kirjoittaa lokin, JSON-statuksen ja CSV-historian `~/gpio_pricer_data/`-hakemistoon.

### `simulate_schedule.py`

* **Tarkoitus:** Simuloi ohjausta halutulle päivälle.
* **TÄRKEÄ HUOMIO (V1):** Tämä simulaattori käyttää eri datalähdettä (`sahkotin.fi`) ja paikallista logiikkaa verrattuna `hourly_control.py` (v1.x) -skriptiin, joka käyttää `api.spot-hinta.fi`-palvelun tarkistuksia. Simuloinnin tulos **ei siis välttämättä täysin vastaa** `hourly_control.py`:n todellista toimintaa tässä versiossa, mutta se antaa hyvän suunnan ja toimii työkaluna asetusten vaikutusten arviointiin. Tämä ero korjataan suunnitellussa V2-arkkitehtuurissa (ks. [SUUNNITELMA_V2.md](SUUNNITELMA_V2.md)).
* **Ajo:** Manuaalisesti komentoriviltä skriptihakemistossa:
    * `python simulate_schedule.py` tai `--today`
    * `python simulate_schedule.py --tomorrow`
    * `python simulate_schedule.py --date VVVV-KK-PP`
* **Toiminta:** Hakee hintaennusteen Sahkotin API:sta, lukee `settings.json` (käyttää sieltä kokonaislukurajoja), laskee paikallisesti pinnien tilat ja kirjoittaa tulostaulukon tiedostoon `~/gpio_pricer_data/simulation_schedule.txt`.

### `show_gpio_status.py`

* **Tarkoitus:** Näyttää viimeisimmän tunnetun tilan pinneille.
* **Ajo:** Manuaalisesti komentoriviltä skriptihakemistossa:
    ```bash
    python show_gpio_status.py
    ```
* **Toiminta:** Lukee `~/gpio_pricer_data/gpio_current_status.json` -tiedoston ja tulostaa sen sisällön selkeänä taulukkona.

## Konfiguraatio (`settings.json`)

Tiedosto `settings.json` sisältää käyttäjäkohtaiset ohjausasetukset. Sitä **ei tallenneta Git-versionhallintaan**, vaan käyttäjän tulee luoda se kopioimalla `settings.example.json` ja muokata sitä `configure_settings.py`-työkalulla (ks. Asennus-osio). Tiedosto on lista JSON-objekteja, joista jokainen kuvaa yhden pinnin asetukset:

`configure_settings.py` luo ja muokkaa tätä tiedostoa. Se on lista JSON-objekteja. **HUOM:** Raja-arvot (`*_limit_ct_kwh`) ovat nyt **kokonaislukuja!**

```json
[
    {
        "gpio_pin": 16, 
        "identifier": "LVV_Esimerkki",
        "upper_limit_ct_kwh": 8,  
        "lower_limit_ct_kwh": 2,  
        "cheapest_hours_n": 3 
    },
    {
        "gpio_pin": 20,
        "identifier": "Lattia_Esimerkki",
        "upper_limit_ct_kwh": 5,
        "lower_limit_ct_kwh": 0,
        "cheapest_hours_n": 5
    }
]

```markdown
* `gpio_pin`: Ohjattavan pinnin numero (BCM-numeroinnilla).
* `identifier`: Vapaamuotoinen nimi pinnille.
* `upper_limit_ct_kwh`: Hinnan yläraja (**kokonaisluku**, senttiä/kWh sis. ALV), jonka ylittyessä pinni on POIS.
* `lower_limit_ct_kwh`: Hinnan alaraja (**kokonaisluku**, senttiä/kWh sis. ALV), jonka alittuessa pinni on PÄÄLLÄ.
* `cheapest_hours_n`: Kuinka monen halvimmista tunnista pinni on PÄÄLLÄ, jos hinta on rajojen välissä (**0-12** `hourly_control.py`:ssä API-rajoituksen vuoksi, **0-24** `simulate_schedule.py`:ssä). 0 = toiminto pois käytöstä.

## Generoidut Tiedostot (`~/gpio_pricer_data/`)

* `gpio_control.log`: Yksityiskohtainen loki `hourly_control.py`:n ajoista.
* `gpio_current_status.json`: Viimeisin pinnien tila JSON-muodossa.
* `gpio_history.csv`: Jatkuva historia pinnien tiloista CSV-muodossa.
* `simulation_schedule.txt`: Simulointityökalun tulostama aikataulutaulukko.

## Huomioitavaa

* **Relelogiikka:** Koodi olettaa `GPIO.LOW` = POIS, `GPIO.HIGH` = PÄÄLLÄ. Varmista oma kytkentäsi!
* **N:n Rajoitus (1-12):** Koskee vain `hourly_control.py`:tä `/CheapestPeriodTodayCheck`-API-kutsun vuoksi.
* **Kokonaislukurajat:** Hintarajat käsitellään nyt kokonaislukuina (ct/kWh) kautta linjan. Päivitä `settings.json` tarvittaessa ajamalla `configure_settings.py`.
* **Lokien Hallinta:** `gpio_control.log` ja `gpio_history.csv` kasvavat. Harkitse rotaatiota/siivousta.
* **Virhetilanteet:** Seuraa lokeja ja harkitse erillistä ilmoitusjärjestelmää.
* **API Yksikkökorjaus:** `hourly_control.py` lähettää nyt hintarajat `/JustNow`-kutsussa oikein ct/kWh-yksikössä (kokonaislukuina).

## Muutoshistoria (Changelog)

Katso tarkemmat tiedot muutoksista tiedostosta [CHANGELOG.md](CHANGELOG.md). *(Lisää tämä linkki, kun olet luonut CHANGELOG.md-tiedoston)*

* **[1.0.1] - 2025-03-31 (Oikea pvm)**
    * Korjattu yksikkövirhe `/JustNow` API-kutsussa (`hourly_control.py`).
    * Muutettu hintarajat kokonaisluvuiksi (ct/kWh) kaikissa skripteissä.
* **[1.0.0] - 2025-03-XX (Arvioitu pvm)**
    * Ensimmäinen julkaistu versio.

## Tuleva Kehitys / Suunnitelma Versio 2 (Future Development / Plan V2)

Seuraavassa versiossa suunnitellaan arkkitehtuurin muuttamista joustavammaksi ja vankemmaksi jakamalla toiminnallisuus kolmeen erilliseen skriptiin (datan päivitys, aikataulun laskenta, suoritus). Tavoitteena on parantaa virheensietoa, mahdollistaa ennakoivat ilmoitukset ja helpottaa tulevia laajennuksia (esim. lämpötilaohjaus, hystereesi, käynnistyspiikin huomiointi).

**Lue yksityiskohtainen suunnitelma täältä: [SUUNNITELMA_V2.md](SUUNNITELMA_V2.md)** *(Linkki lisätään, kun luot tiedoston)*

## Yhteystiedot

* GitHub Repository: https://github.com/arttuliini/GPIO-Vasalli/
* Kehittäjä: https://www.vasalli.fi
* Arttu Kotilainen

---
