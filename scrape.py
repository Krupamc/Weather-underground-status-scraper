import config as cfg
import requests
from bs4 import BeautifulSoup as bs
from pathlib import Path
import json

station_id = "KNJMANAH7"

def check_station(station_id):
    url = f"https://preview.wunderground.com/dashboard/pws/{station_id}"

    r = requests.get(url, timeout=10)
    r.raise_for_status

    soup = bs(r.content, "html.parser")

    station_name = soup.find("h1").get_text()
    status_header = soup.find("pws-status")

    status = status_header['data-status']

    print(f"Station: {station_name} [{status.upper()}]")

    if status == "offline":
        

def read_json_file():
    with open("status.json", "r") as file:
        json.load()

def write_json_file(data):
    with open("status.json", "rw") as file:
        json.dump(data, file, indent=4)

def write_start()
    status_json_file = Path("status.json")
    status_json_file.touch(exist_ok=True)

for station in cfg.stations:
    check_station(station)




