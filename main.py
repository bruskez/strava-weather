import os
import requests

# ==========================
# CONFIGURAZIONE - da ENV
# ==========================

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
VC_API_KEY = os.getenv("VC_API_KEY")

# quante attività controllare ad ogni run
MAX_ACTIVITIES = 50
METEO_TAG = "Meteo (auto GitHub)"


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
        # Print status and Strava error payload for diagnosis (does not reveal our secrets)
        print(f"[ERROR] Strava token request failed: {r.status_code}")
        try:
            print("[ERROR] Strava response:", r.json())
        except Exception:
            print("[ERROR] Strava response text:", r.text)
        r.raise_for_status()
    return r.json()["access_token"]


def get_recent_activities(token, max_activities=MAX_ACTIVITIES):
    print(f"[INFO] Scarico fino a {max_activities} attività...")
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {token}"}
    activities = []
    page = 1

    while len(activities) < max_activities:
        params = {"per_page": 50, "page": page}
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        activities.extend(batch)
        page += 1

    return activities[:max_activities]


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
    lines.append("🔄 Fonte: Visual Crossing")
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

    for act in activities:
        act_id = act.get("id")
        name = act.get("name")
        desc = act.get("description") or ""
        start_latlng = act.get("start_latlng")
        start_date_local = act.get("start_date_local")

        print(f"\n→ Attività {act_id}: {name}")

        # se non c'è GPS (indoor) salto
        if not start_latlng or len(start_latlng) < 2:
            print("   Nessuna traccia GPS, salto.")
            continue

        # se abbiamo già aggiunto il meteo in passato, salto
        if METEO_TAG in desc:
            print("   Meteo già presente, salto.")
            continue

        lat, lon = start_latlng[0], start_latlng[1]
        date_str = start_date_local.split("T")[0]  # "YYYY-MM-DD"

        print(f"   Data: {date_str}  |  Posizione: {lat},{lon}")

        try:
            temp, feels, wind, cond = get_weather_for_activity(lat, lon, date_str)
        except Exception as e:
            print(f"   Errore meteo: {e}")
            continue

        print(f"   Meteo: temp={temp}, feels={feels}, wind={wind}, cond={cond}")

        weather_block = build_weather_block(temp, feels, wind, cond)
        new_desc = desc + weather_block

        try:
            update_strava_activity_description(token, act_id, new_desc)
            print("   ✔ Descrizione aggiornata.")
        except Exception as e:
            print(f"   Errore aggiornando Strava: {e}")


if __name__ == "__main__":
    main()
