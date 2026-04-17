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

def main():
    print(f"Monitoring battery...")
    while True:
        level = get_battery_level()
        print(f"Current Battery: {level}%")

        if level >= UPPER_LIMIT:
            set_switch("turn_off")
        elif level <= LOWER_LIMIT:
            set_switch("turn_on")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()