import requests
import time
import os
import csv
from dotenv import load_dotenv
load_dotenv()
UPPER_LIMIT = 80  # Turn off at 80%
LOWER_LIMIT = 20  # Turn back on at 20% to keep it cycling
CHECK_INTERVAL = 60  # Seconds between checks
MIN_RATE_SAMPLE_SECONDS = 300  # Avoid spiky rates from 1-minute integer changes
LOG_FILE = os.getenv("BATTERY_LOG_FILE", "battery_history.csv")

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
    min_sample_seconds=MIN_RATE_SAMPLE_SECONDS,
):
    if previous_level is None or previous_time is None:
        return (
            charge_rate_sum,
            charge_rate_count,
            discharge_rate_sum,
            discharge_rate_count,
            level,
            now,
        )

    elapsed_seconds = now - previous_time
    if elapsed_seconds <= 0:
        return (
            charge_rate_sum,
            charge_rate_count,
            discharge_rate_sum,
            discharge_rate_count,
            previous_level,
            previous_time,
        )

    level_delta = level - previous_level
    if level_delta == 0 or elapsed_seconds < min_sample_seconds:
        return (
            charge_rate_sum,
            charge_rate_count,
            discharge_rate_sum,
            discharge_rate_count,
            previous_level,
            previous_time,
        )

    hours_elapsed = elapsed_seconds / 3600
    rate = level_delta / hours_elapsed
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
        level,
        now,
    )


def persist_battery_data(
    file_path,
    timestamp,
    level,
    avg_charge,
    avg_discharge,
    charge_rate_sum,
    charge_rate_count,
    discharge_rate_sum,
    discharge_rate_count,
):
    file_exists = os.path.exists(file_path)
    with open(file_path, "a", encoding="utf-8") as log_file:
        if not file_exists:
            log_file.write(
                "timestamp,battery_level,avg_charge_rate,avg_discharge_rate,"
                "charge_rate_sum,charge_rate_count,discharge_rate_sum,discharge_rate_count\n"
            )
        log_file.write(
            f"{int(timestamp)},{level},{avg_charge:.2f},{avg_discharge:.2f},"
            f"{charge_rate_sum:.2f},{charge_rate_count},"
            f"{discharge_rate_sum:.2f},{discharge_rate_count}\n"
        )


def load_persisted_state(file_path):
    if not os.path.exists(file_path):
        return None, None, 0.0, 0, 0.0, 0

    try:
        with open(file_path, "r", encoding="utf-8") as log_file:
            reader = csv.DictReader(log_file)
            last_row = None
            for row in reader:
                last_row = row

            if not last_row:
                return None, None, 0.0, 0, 0.0, 0

            previous_time = float(last_row["timestamp"])
            previous_level = int(last_row["battery_level"])

            # Backward compatibility for older logs that only have averages.
            charge_rate_sum = float(last_row.get("charge_rate_sum") or last_row.get("avg_charge_rate") or 0.0)
            charge_rate_count = int(last_row.get("charge_rate_count") or (1 if charge_rate_sum > 0 else 0))
            discharge_rate_sum = float(last_row.get("discharge_rate_sum") or last_row.get("avg_discharge_rate") or 0.0)
            discharge_rate_count = int(last_row.get("discharge_rate_count") or (1 if discharge_rate_sum > 0 else 0))

            return (
                previous_level,
                previous_time,
                charge_rate_sum,
                charge_rate_count,
                discharge_rate_sum,
                discharge_rate_count,
            )
    except Exception:
        return None, None, 0.0, 0, 0.0, 0

def main():
    print(f"Monitoring battery...")
    (
        previous_level,
        previous_time,
        charge_rate_sum,
        charge_rate_count,
        discharge_rate_sum,
        discharge_rate_count,
    ) = load_persisted_state(LOG_FILE)

    while True:
        level = get_battery_level()
        print(f"Current Battery: {level}%")

        now = time.time()
        (
            charge_rate_sum,
            charge_rate_count,
            discharge_rate_sum,
            discharge_rate_count,
            previous_level,
            previous_time,
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

        try:
            persist_battery_data(
                LOG_FILE,
                now,
                level,
                avg_charge,
                avg_discharge,
                charge_rate_sum,
                charge_rate_count,
                discharge_rate_sum,
                discharge_rate_count,
            )
        except Exception as e:
            print(f"Failed to persist battery data: {e}")

        if level >= UPPER_LIMIT:
            set_switch("turn_off")
        elif level <= LOWER_LIMIT:
            set_switch("turn_on")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()