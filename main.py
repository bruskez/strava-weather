"""
Strava Weather - Add weather information to Strava activities.

This script fetches recent activities from Strava, retrieves weather data
for the activity time and location, and updates the activity description
with weather information.
"""

import os
import sys
import requests
from datetime import datetime


def refresh_strava_token(client_id, client_secret, refresh_token):
    """Refresh the Strava access token using the refresh token."""
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_recent_activities(access_token, per_page=10):
    """Fetch recent activities from Strava."""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers=headers,
        params={"per_page": per_page},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_activity_details(access_token, activity_id):
    """Get detailed information about a specific activity."""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_weather_data(latitude, longitude, timestamp):
    """
    Get weather data from Open-Meteo API for a specific location and time.
    
    Open-Meteo is a free weather API that doesn't require an API key.
    """
    # Parse the timestamp
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    date_str = dt.strftime("%Y-%m-%d")
    hour = dt.hour

    response = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "start_date": date_str,
            "end_date": date_str,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    # Extract the weather data for the specific hour
    hourly = data.get("hourly", {})
    if not hourly:
        return None

    return {
        "temperature": hourly.get("temperature_2m", [None] * 24)[hour],
        "humidity": hourly.get("relative_humidity_2m", [None] * 24)[hour],
        "wind_speed": hourly.get("wind_speed_10m", [None] * 24)[hour],
        "weather_code": hourly.get("weather_code", [None] * 24)[hour],
    }


def weather_code_to_description(code):
    """Convert WMO weather code to human-readable description."""
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return weather_codes.get(code, "Unknown")


def format_weather_string(weather_data):
    """Format weather data into a readable string."""
    if not weather_data:
        return None

    parts = []
    
    if weather_data.get("weather_code") is not None:
        description = weather_code_to_description(weather_data["weather_code"])
        parts.append(f"🌤️ {description}")
    
    if weather_data.get("temperature") is not None:
        parts.append(f"🌡️ {weather_data['temperature']:.1f}°C")
    
    if weather_data.get("humidity") is not None:
        parts.append(f"💧 {weather_data['humidity']}%")
    
    if weather_data.get("wind_speed") is not None:
        parts.append(f"💨 {weather_data['wind_speed']:.1f} km/h")

    return " | ".join(parts) if parts else None


def update_activity_description(access_token, activity_id, weather_string, existing_description):
    """Update the activity description with weather information."""
    # Check if weather info already exists
    if existing_description and "🌡️" in existing_description:
        print(f"Activity {activity_id} already has weather info, skipping...")
        return False

    # Append weather info to existing description
    if existing_description:
        new_description = f"{existing_description}\n\n{weather_string}"
    else:
        new_description = weather_string

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.put(
        f"https://www.strava.com/api/v3/activities/{activity_id}",
        headers=headers,
        data={"description": new_description},
        timeout=30,
    )
    response.raise_for_status()
    return True


def main():
    """Main function to add weather info to Strava activities."""
    # Get environment variables
    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("Error: Missing required environment variables.")
        print("Please set STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, and STRAVA_REFRESH_TOKEN")
        sys.exit(1)

    # Refresh the access token
    print("Refreshing Strava access token...")
    token_data = refresh_strava_token(client_id, client_secret, refresh_token)
    access_token = token_data["access_token"]
    print("Token refreshed successfully.")

    # Get recent activities
    print("Fetching recent activities...")
    activities = get_recent_activities(access_token, per_page=5)
    print(f"Found {len(activities)} recent activities.")

    # Process each activity
    for activity in activities:
        activity_id = activity["id"]
        activity_name = activity["name"]
        start_date = activity["start_date"]
        
        print(f"\nProcessing: {activity_name} ({start_date})")

        # Get detailed activity info for coordinates
        details = get_activity_details(access_token, activity_id)
        
        # Get start coordinates
        start_latlng = details.get("start_latlng")
        if not start_latlng or len(start_latlng) < 2:
            print(f"  No GPS data for activity {activity_id}, skipping...")
            continue

        latitude, longitude = start_latlng

        # Get weather data
        print(f"  Getting weather for {latitude:.4f}, {longitude:.4f}...")
        weather_data = get_weather_data(latitude, longitude, start_date)
        
        if not weather_data:
            print(f"  Could not fetch weather data, skipping...")
            continue

        # Format weather string
        weather_string = format_weather_string(weather_data)
        if not weather_string:
            print(f"  No weather data available, skipping...")
            continue

        print(f"  Weather: {weather_string}")

        # Update activity description
        existing_description = details.get("description", "")
        if update_activity_description(access_token, activity_id, weather_string, existing_description):
            print(f"  ✅ Updated activity description")
        
    print("\nDone!")


if __name__ == "__main__":
    main()
