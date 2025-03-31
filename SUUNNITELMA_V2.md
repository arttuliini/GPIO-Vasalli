# GPIO-Vasalli - Version 2 Suunnitelma

Tämä dokumentti kuvaa suunnitellut muutokset ja parannukset GPIO-Vasalli -projektiin versiossa 2. Tavoitteena on parantaa järjestelmän vankkuutta, joustavuutta ja laajennettavuutta.

## Arkkitehtuurimuutos: Kolmen Skriptin Malli

Nykyinen versio (v1.x) käyttää pääosin yhtä `hourly_control.py`-skriptiä, joka hoitaa sekä API-tarkistukset että GPIO-ohjauksen. Tämä on altis API-palveluiden häiriöille ja rajoituksille (kuten N=1..12 halvimmille tunneille).

Versiossa 2 siirrytään kolmen erillisen skriptin malliin:

1.  **`price_updater.py` (Datan Päivittäjä):**
    * **Ajo:** Ajastetusti harvemmin (esim. 4-6h välein tai kerran päivässä klo 14:15 jälkeen).
    * **Tehtävä:** Hakee hintatiedot luotettavasta lähteestä (esim. Sahkotin `/prices`), valmistelee ne (aikavyöhykkeet, yksiköt ct/kWh, `"HH:MM"`-avaimet datan tarkkuuden mukaan) ja tallentaa ne keskitettyyn välimuistitiedostoon (`price_cache.json`). Voi tulevaisuudessa hakea myös muuta dataa (lämpötila yms.) ja tallentaa sen omaan tiedostoonsa. Vastuussa kaikesta ulkoisesta API-kommunikaatiosta ja datan esikäsittelystä.

2.  **`schedule_builder.py` (Aikataulun Rakentaja):**
    * **Ajo:** Kerran päivässä (esim. klo 14:30), kun seuraavan päivän hinnat ovat todennäköisesti saatavilla `price_cache.json`:ssa.
    * **Tehtävä:** Lukee *seuraavan päivän* valmistellut hintatiedot välimuistista ja käyttäjän `settings.json`-asetukset. Laskee näiden perusteella **valmiiksi koko seuraavan päivän ON/OFF-aikataulun** jokaiselle pinnille, jokaiselle ajanjaksolle (tunti tai vartti). Toteuttaa varsinaisen ohjauslogiikan, mukaan lukien suunnitellut parannukset:
        * **Hystereesi:** Estää turhaa releiden kytkentää raja-arvojen lähellä (vaatii uuden `hysteresis_ct_kwh`-asetuksen).
        * **Käynnistyskulutuksen Huomiointi:** Käyttää `startup_factor`-kerrointa (asetuksista) painottamaan N halvimpien jaksojen valintaa niin, että käynnistyspiikit ohjautuvat edullisimmille hetkille.
        * **Laajennettavuus:** Voi tulevaisuudessa lukea myös sensoridataa (`sensor_data.json`) ja käyttää sitä päätöksenteossa (esim. lämpötilaohjaus).
    * Tallentaa valmiin aikataulun tiedostoon `control_schedule.json`.
    * **Ilmoitukset:** Voi lähettää ilmoituksen käyttäjälle, jos aikataulun luonti epäonnistuu.
    * **Manuaaliset Ohitukset:** Voi lukea erillisen `manual_override.json`-tiedoston ja yhdistää siinä määritellyt pakotetut ON/OFF-tilat lopulliseen aikatauluun.

3.  **`hourly_control.py` (Yksinkertaistettu Suorittaja):**
    * **Ajo:** Tiheästi, käyttäjän haluaman resoluution mukaan (tunnin tai 15 minuutin välein).
    * **Tehtävä:** Erittäin yksinkertainen:
        * Lukee nykyisen ajan ja päivämäärän.
        * Lukee **valmiin aikataulun** `control_schedule.json`-tiedostosta tälle päivälle.
        * Etsii aikataulusta nykyistä ajanjaksoa vastaavan tilan (ON/OFF) kullekin pinnille.
        * **Ohjaa GPIO-pinniä täsmälleen aikataulun mukaisesti.**
        * **Fallback:** Jos aikataulua ei löydy, asettaa pinnit turvalliseen OFF-tilaan.
        * Ei tee API-kutsuja, ei laske hintalogiikkaa.
    * **Hyödyt:** Erittäin vankka, kevyt ja vähemmän altis virheille.

## Suunnitellut Uudet Ominaisuudet (V2)

* Hystereesi hintarajoihin.
* Käynnistyskulutuspiikin huomioiminen halvimpien jaksojen valinnassa (heuristiikalla).
* Ennakoiva ilmoitusjärjestelmä aikataulun luonnin epäonnistumisesta.
* Mahdollisuus manuaalisille ohituksille.
* Arkkitehtuuri, joka mahdollistaa helpommin uusien tietolähteiden (esim. lämpötila) lisäämisen päätöksentekoon tulevaisuudessa.

## Toteutusaikataulu

Tämän version kehitys aloitetaan myöhemmin. Nykyinen v1.x pysyy päähaarassa toistaiseksi.
