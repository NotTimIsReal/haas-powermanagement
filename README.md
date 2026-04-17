# HAAS Power Management

Small Python service that watches the local machine battery and toggles a Home Assistant switch when the battery crosses configured thresholds.

It is designed for a Linux host that exposes battery state through `/sys/class/power_supply/BAT0/capacity` or `/sys/class/power_supply/BAT1/capacity`.

## What it does

- Polls the battery level every 60 seconds.
- Turns the configured switch off when the battery reaches 80%.
- Turns the switch back on when the battery falls to 20%.
- Logs battery samples and calculated charge/discharge rates to a CSV file.
- Persists rate history between runs so averages continue from the last sample.

## Requirements

- Python 3.11+ recommended.
- Access to a Home Assistant instance.
- A valid Home Assistant long-lived access token.
- A Linux system with a readable battery capacity file.

## Configuration

Set these environment variables before running the service:

- `API_KEY`: Home Assistant bearer token.
- `HAAS_URL`: Base URL for Home Assistant, for example `http://homeassistant.local:8123`.
- `ENTITY_ID`: Switch entity to control, for example `switch.charger`.
- `BATTERY_LOG_FILE`: Optional path for the CSV history file. Defaults to `battery_history.csv`.

You can place them in a local `.env` file because the app loads environment variables with `python-dotenv`.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
export API_KEY="your-home-assistant-token"
export HAAS_URL="http://homeassistant.local:8123"
export ENTITY_ID="switch.charger"
python main.py
```

The service runs continuously until stopped.

## Docker

Build and run the container with:

```bash
docker build -f dockerfile -t haas-powermanagement .
docker run --rm \
	-e API_KEY="your-home-assistant-token" \
	-e HAAS_URL="http://homeassistant.local:8123" \
	-e ENTITY_ID="switch.charger" \
	haas-powermanagement
```

Mount a volume if you want the CSV log to persist outside the container.

## Data format

The CSV log includes:

- `timestamp`
- `battery_level`
- `avg_charge_rate`
- `avg_discharge_rate`
- `charge_rate_sum`
- `charge_rate_count`
- `discharge_rate_sum`
- `discharge_rate_count`

## Testing

```bash
python -m unittest discover -s tests
```

## Notes

- The first battery sample is used to initialize the history and does not produce a rate.
- Samples closer than five minutes apart are ignored when calculating average charge and discharge rates.
- If the app cannot read battery data or reach Home Assistant, it logs the failure and keeps running.
