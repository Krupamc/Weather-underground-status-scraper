
# Web Server for Mesonet System
from dotenv import load_dotenv, find_dotenv
# Developer mode (allows env variables in desktop) 
load_dotenv(find_dotenv(), override=False)

from bs4 import BeautifulSoup as bs 
import requests
from requests import RequestException
from requests.exceptions import HTTPError
import convert_metric as cv
from pathlib import Path
import csv
from datetime import datetime
import config as cfg
import pytz
import time


url = "https://preview.wunderground.com/dashboard/pws/KNJBAYHE18"

# Load webpage
r = requests.get(url, timeout=10)
r.raise_for_status()

# Convert to bs object
soup = bs(r.content, "html.parser")

#--Station Info--
info = soup.find("pws-info").find("ol")

print(f"Info: {info}")

for li in info.select("li"):
    label = li.select_one("span:nth-of-type(1)")
    value = li.select_one("span:nth-of-type(2)")

    if label and value and label.get_text(strip=True) == "Latitude:":
        lat = value.get_text(strip=True)
        lat = float(lat.replace("°", "").replace("N", "").replace("S", "").strip())
        
    if label and value and label.get_text(strip=True) == "Longitude:":
        long = value.get_text(strip=True)
        cleaned_long = long.replace("°", "").strip()

        direction = cleaned_long[-1]
        long_num = float(cleaned_long.replace("W", "").replace("E", "").strip())
        if direction in ['S', 'W']:
            long =  -long_num

    if label and value and label.get_text(strip=True) == "Elevation:":
        elevation = value.get_text(strip=True)
        elevation = int(elevation.replace("ft", "").strip())

    if label and value and label.get_text(strip=True) == "State:":
        state = value.get_text(strip=True)

    if label and value and label.get_text(strip=True) == "Country:":
        country = value.get_text(strip=True)

    if label and value and label.get_text(strip=True) == "Hardware:":
        hardware = value.get_text(strip=True)
        
print(lat)
print(long)
print(elevation)
print(state)
print(country)
print(hardware)