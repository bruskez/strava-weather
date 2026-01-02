import os
import requests
import time
from datetime import datetime, timedelta

# ==========================
# CONFIGURAZIONE - da ENV
# ==========================

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
VC_API_KEY = os.getenv("VC_API_KEY")

# quante attività controllare ad ogni run
MAX_ACTIVITIES = 40

# quanti giorni indietro vuoi controllare
DAYS_BACK = 3

METEO_TAG = "Meteo"


def get_strava_access_token():
    url = "https://www.strava.com/oauth/token"
    data = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": STRAVA_REFRESH_TOKEN,
    }
    print("[INFO] Requesting Strava access token...")
    r = requests.post(url, data=data)
    if r.status_code != 200:
        # Messaggio di errore generico, senza dettagli sensibili
        print(f"[ERROR] Strava token request failed with status code: {r.status_code}")
        try:
            err = r.json()
            msg = err.get("message") or "No message"
            print(f"[ERROR] Strava error message: {msg}")
        except Exception:
            print("[ERROR] Strava returned a non-JSON error.")
        r.raise_for_status()
    return r.json()["access_token"]


def get_recent_activities(token, max_activities=MAX_ACTIVITIES):
    print(f"[INFO] Scarico fino a {max_activities} attività...")
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {token}"}
    activities = []
    page = 1
    retries = 3

    while True:
        params = {"per_page": 200, "page": page}
        for attempt in range(retries):
            try:
                r = requests.get(url, headers=headers, params=params, timeout=10)
                r.raise_for_status()
                break
            except requests.exceptions.HTTPError as e:
                if r.status_code >= 500:
                    print(f"[WARN] Server error (status {r.status_code}), retrying ({attempt + 1}/{retries})...")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    print(f"[ERROR] {e}")
                    raise  # Non-retryable error
        batch = r.json()
        if not batch:
            break
        activities.extend(batch)
        page += 1
        if len(activities) >= max_activities:
            break
    print(f"[INFO] Totale attività scaricate: {len(activities)}")
    return activities


def get_weather_for_activity(lat, lon, date_str):
    """
    Usa Visual Crossing per ottenere il meteo del giorno (YYYY-MM-DD)
    in una certa posizione (lat, lon).
    """
    base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    url = f"{base_url}/{lat},{lon}/{date_str}"
    params = {
        "unitGroup": "metric",
        "include": "days",
        "key": VC_API_KEY,
        "contentType": "json",
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    d = r.json()["days"][0]
    temp = d.get("temp")
    feels = d.get("feelslike")
    wind = d.get("windspeed")
    cond = d.get("conditions")
    return temp, feels, wind, cond


def build_weather_block(temp, feels, wind, cond):
    lines = []
    lines.append("")  # riga vuota di separazione
    lines.append(f"🏷 {METEO_TAG}")
    if temp is not None:
        if feels is not None:
            lines.append(f"🌡 Temp: {temp}°C (percepita {feels}°C)")
        else:
            lines.append(f"🌡 Temp: {temp}°C")
    if wind is not None:
        lines.append(f"💨 Vento: {wind} km/h")
    if cond:
        lines.append(f"☁️ Condizioni: {cond}")
    return "\n".join(lines)


def update_strava_activity_description(token, activity_id, new_description):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"description": new_description}
    r = requests.put(url, headers=headers, data=data)
    r.raise_for_status()
    return r.json()


def main():
    # Controllo che le variabili siano presenti
    for name, value in [
        ("STRAVA_CLIENT_ID", STRAVA_CLIENT_ID),
        ("STRAVA_CLIENT_SECRET", STRAVA_CLIENT_SECRET),
        ("STRAVA_REFRESH_TOKEN", STRAVA_REFRESH_TOKEN),
        ("VC_API_KEY", VC_API_KEY),
    ]:
        if not value:
            raise RuntimeError(f"Variabile d'ambiente mancante: {name}")

    token = get_strava_access_token()
    activities = get_recent_activities(token)

    print(f"[INFO] Attività trovate: {len(activities)}")

    # Calcolo data di cutoff (non processiamo attività più vecchie di DAYS_BACK)
    cutoff_date = datetime.now() - timedelta(days=DAYS_BACK)
    cutoff_str = cutoff_date.date().isoformat()
    print(f"[INFO] Considero solo attività degli ultimi {DAYS_BACK} giorni")

    for act in activities:
        act_id = act.get("id")
        desc = act.get("description") or ""
        start_latlng = act.get("start_latlng")
        start_date_local = act.get("start_date_local")  # es. 'YYYY-MM-DDTHH:MM:SSZ'

        if not start_date_local:
            print(f"\n→ Attività ID {act_id}: nessuna data, salto.")
            continue

        act_date_str = start_date_local.split("T")[0]  # "YYYY-MM-DD"

        # filtro per data: salto se l'attività è più vecchia della finestra DAYS_BACK
        if act_date_str < cutoff_str:
            print(f"\n→ Attività ID {act_id}: troppo vecchia rispetto alla finestra, salto.")
            continue

        print(f"\n→ Elaboro attività ID {act_id}")

        # se non c'è GPS (indoor) salto
        if not start_latlng or len(start_latlng) < 2:
            print("   Nessuna traccia GPS, salto.")
            continue

        # se abbiamo già aggiunto il meteo in passato, salto
        if METEO_TAG in desc:
            print("   Meteo già presente, salto.")
            continue

        lat, lon = start_latlng[0], start_latlng[1]
        date_str = act_date_str  # già "YYYY-MM-DD"

        # Non logghiamo le coordinate né la data specifica
        print("   Posizione: GPS OK (coordinate non loggate)")

        try:
            temp, feels, wind, cond = get_weather_for_activity(lat, lon, date_str)
        except Exception:
            print("   Errore meteo durante la richiesta, salto.")
            continue

        print("   Meteo recuperato con successo.")

        weather_block = build_weather_block(temp, feels, wind, cond)
        new_desc = desc + weather_block

        try:
            update_strava_activity_description(token, act_id, new_desc)
            print("   ✔ Descrizione aggiornata.")
            time.sleep(3)
        except Exception:
            print("   Errore aggiornando Strava, salto.")


if __name__ == "__main__":
    main()
