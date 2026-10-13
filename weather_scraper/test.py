
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
air = soup.find("temp-widget-view")           
temp = air.get('data-temp')
print(f"Temp: {temp}")

dew_air = soup.find("humidity-widget-view")
dew = dew_air.get("data-dew-point")
print(f"Dew: {dew}")
humd = dew_air.get("data-humidity")
print(f"Humidity: {humd}")
print()