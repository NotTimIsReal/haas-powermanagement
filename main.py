import requests
import time
import os
from dotenv import load_dotenv
load_dotenv()
UPPER_LIMIT = 80  # Turn off at 80%
LOWER_LIMIT = 20  # Turn back on at 20% to keep it cycling
CHECK_INTERVAL = 60  # Seconds between checks

HEADERS = {
    "Authorization": f"Bearer {os.getenv('API_KEY')}",
    "Content-Type": "application/json",
}

def get_battery_level():
    # Standard path for most Linux distributions
    try:
        with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        # Some devices use BAT1
        with open("/sys/class/power_supply/BAT1/capacity", "r") as f:
            return int(f.read().strip())

def set_switch(state):
    """state should be 'turn_on' or 'turn_off'"""
    url = f"{os.getenv('HAAS_URL')}/api/services/switch/{state}"
    data = {"entity_id": os.getenv("ENTITY_ID")}
    try:
        response = requests.post(url, headers=HEADERS, json=data)
        if response.status_code == 200:
            print(f"Successfully sent {state} command.")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Connection failed: {e}")


def update_average_rates(
    previous_level,
    previous_time,
    level,
    now,
    charge_rate_sum,
    charge_rate_count,
    discharge_rate_sum,
    discharge_rate_count,
):
    if previous_level is None or previous_time is None:
        return (
            charge_rate_sum,
            charge_rate_count,
            discharge_rate_sum,
            discharge_rate_count,
        )

    hours_elapsed = (now - previous_time) / 3600
    if hours_elapsed <= 0:
        return (
            charge_rate_sum,
            charge_rate_count,
            discharge_rate_sum,
            discharge_rate_count,
        )

    rate = (level - previous_level) / hours_elapsed
    if rate > 0:
        charge_rate_sum += rate
        charge_rate_count += 1
    elif rate < 0:
        discharge_rate_sum += abs(rate)
        discharge_rate_count += 1

    return (
        charge_rate_sum,
        charge_rate_count,
        discharge_rate_sum,
        discharge_rate_count,
    )

def main():
    print(f"Monitoring battery...")
    previous_level = None
    previous_time = None
    charge_rate_sum = 0.0
    charge_rate_count = 0
    discharge_rate_sum = 0.0
    discharge_rate_count = 0

    while True:
        level = get_battery_level()
        print(f"Current Battery: {level}%")

        now = time.time()
        (
            charge_rate_sum,
            charge_rate_count,
            discharge_rate_sum,
            discharge_rate_count,
        ) = update_average_rates(
            previous_level,
            previous_time,
            level,
            now,
            charge_rate_sum,
            charge_rate_count,
            discharge_rate_sum,
            discharge_rate_count,
        )

        avg_charge = (
            charge_rate_sum / charge_rate_count if charge_rate_count else 0.0
        )
        avg_discharge = (
            discharge_rate_sum / discharge_rate_count if discharge_rate_count else 0.0
        )
        print(
            f"Average charge rate: {avg_charge:.2f}%/hr | "
            f"Average discharge rate: {avg_discharge:.2f}%/hr"
        )

        if level >= UPPER_LIMIT:
            set_switch("turn_off")
        elif level <= LOWER_LIMIT:
            set_switch("turn_on")

        previous_level = level
        previous_time = now
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()