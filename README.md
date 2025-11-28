# Strava Weather Auto

Automatically appends weather information to your recent Strava activities using the Strava API, Visual Crossing Weather API, and a GitHub Actions workflow.

## Repository structure

```
main.py                     # main script
requirements.txt            # Python dependencies
.github/workflows/*.yml     # GitHub Actions workflow
```

## Example weather block

```
🏷 Meteo
🌡 Temp: 14°C (feels like 12°C)
💨 Wind: 9 km/h
☁️ Conditions: Partly cloudy
```

## Configuration

Set the following GitHub Secrets in your repository:

* STRAVA_CLIENT_ID
* STRAVA_CLIENT_SECRET
* STRAVA_REFRESH_TOKEN
* VC_API_KEY

These values are not stored in the code.

## Automation

The workflow is configured to run automatically (e.g., every 30 minutes).
You can adjust the schedule in `.github/workflows/<workflow>.yml`.

## Privacy

* No GPS coordinates, activity names, or exact dates are logged.
* Secrets are handled via GitHub Secrets and never exposed.

