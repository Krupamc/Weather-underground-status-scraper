import config as cfg
import requests
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup as bs
from pathlib import Path
import smtplib
import ssl
from email.message import EmailMessage
import json
from datetime import datetime
import pytz
import time
import csv

# monthly overview + maintence mode/redo notific after 7 days

def check_station(station_id):

    station_name = cfg.stations[station_id]

    # time - error protected
    for attempt in range(cfg.max_retries):
        try:
            utc_now = datetime.now(pytz.UTC)
            eastern = pytz.timezone(cfg.pytz_timezone)
            now = utc_now.astimezone(eastern)
            break

        except Exception as e:
            print(f"[TIME ERROR]: Failed to get time for {station_id}. Error: {e}")
           
            # Write to file
            data = read_json_file()
            e = str(e)
            log_data(None, station_id, station_name, "error", data[station_id]["consecutive_offline"], "Time_error", f"{e}")

            # Email
            email(
                subject=cfg.time_e_subject,
                body=cfg.time_e_body.format(err = e),
                recipients=cfg.admin
            )
    else:
        return

    for attempt in range(cfg.max_retries): # Try the scraping
        try:
            url = f"https://preview.wunderground.com/dashboard/pws/{station_id}" # Base url
            r = requests.get(url, timeout=10)
            r.raise_for_status()

            soup = bs(r.content, "html.parser")

            # Get station name and status
            
            status_header = soup.find("pws-status")

            status = status_header["data-status"]

            if status == "offline":
                status2 = " offline "
            else: status2 = status
            print(f"[{status2.upper()}]: {station_name}")
            break
        
        except HTTPError as e:
            wait_time = cfg.backoff_factor ** attempt
            print(f"[HTTP ERROR]: {e}\nRetrying in {wait_time} seconds")
            
            # Write error to file
            data = read_json_file()
            e = str(e)
            log_data(now.isoformat(), station_id, station_name, "error", data[station_id]["consecutive_offline"], "HTTP_error", f"{e}")
            
            # Email the error:
            email(
                subject=cfg.http_e_subject,
                body=cfg.e_body.format(err=e),
                recipients=cfg.admin
            )

            time.sleep(wait_time)
            continue

        except Exception as e:
            print(f"[SCRAPING ERROR]: Failed to get data for {station_id}. Error: {e}")
            
            # Write Error to file
            data = read_json_file()
            e = str(e)
            log_data(now.isoformat(), station_id, station_name, "error", data[station_id]["consecutive_offline"], "Scraping_error", f"{e}")
            
            # Email it
            email(
                subject=cfg.scrape_e_subject,
                body=cfg.time_e_body.format(err=e),
                recipients=cfg.admin
            )
    else:
        return
    
    if status == "offline":
        # Increment offlines
        data = read_json_file()
        data[station_id]["consecutive_offline"] += 1
        if data[station_id]["last_status"] != "OFFLINE":
            data[station_id]["first_offline"] = now.isoformat()
        data[station_id]["last_status"] = "OFFLINE"
        write_json_file(data)

        data = read_json_file()
        consec_offline = data[station_id]["consecutive_offline"]
        if consec_offline >= cfg.consecutive_offline and not data[station_id]["alert_sent"]:
            stat_name = cfg.stations[station_id]
            stat_id = station_id
            offline_alert(
                stat_id,
                stat_name, 
                consec_offline, 
                url, 
                now
            )
        
            # Set these
            data[station_id]["since_sent"] = now.isoformat()
            data[station_id]["alert_sent"] = True
            write_json_file(data)
            log_data(now.isoformat(), station_id, station_name, status, consec_offline, "offline_alert", "Threshold Reached, email sent")
        
        else:
            log_data(now.isoformat(), station_id, station_name, status, consec_offline, "check", "ok")

    elif status == "online":
        # Open json
        data = read_json_file()
        data[station_id]["last_status"] = "ONLINE"
        
        # Recovery
        if data[station_id]["alert_sent"]:
            print(f"[RECOVERED] {station_name} ({station_id})")
            status = "recovered"
            outage_start = data[station_id]["first_offline"]
            outage_start = datetime.fromisoformat(outage_start)
            outage_dur = now - outage_start

            recover_alert(
                stat_id=station_id, 
                stat_name=station_name, 
                url=url, 
                start=outage_start,
                duration=outage_dur,
                now=now
            )
            data[station_id]["last_status"] = "RECOVERED"
            log_data(now.isoformat(), station_id, station_name, status, data[station_id]["consecutive_offline"], "recovered", "Station_recovered")
            data[station_id]["first_offline"] = None
            data[station_id]["last_online"] = now.isoformat()
            data[station_id]["alert_sent"] = False
            data[station_id]["consecutive_offline"] = 0
            write_json_file(data)
            
        
        else:
            log_data(now.isoformat(), station_id, station_name, status, data[station_id]["consecutive_offline"], "online", "ok")
            data[station_id]["first_offline"] = None
            data[station_id]["last_status"] = "ONLINE"
            data[station_id]["last_online"] = now.isoformat()
            data[station_id]["alert_sent"] = False
            data[station_id]["consecutive_offline"] = 0
            write_json_file(data)
    


def read_json_file():
    with open("status.json", "r", encoding="utf-8") as file:
         data = json.load(file)
    return data

def write_json_file(data):
    with open("status.json", "w", encoding="utf-8") as file:
        json.dump(data, file, indent = 2)

# Use all alert funcs.
def recover_alert(stat_id, stat_name, url, start, duration, now):

    station_recipient = cfg.recipients.get(stat_id, [])

    if station_recipient:
        recipients = station_recipient + cfg.global_recipients

    else:
        recipients = cfg.global_recipients

    email(
        subject =cfg.r_subject.format(station_name=stat_name, station_id=stat_id),
        body = cfg.r_body.format(station_name=stat_name, station_id=stat_id, url=url, outage_start=start, outage_duration=duration, now=now),
        recipients = recipients
    )

# Use all alert functions
def offline_alert(stat_id, stat_name, consec_offline, url, now):

    station_recipient = cfg.recipients.get(stat_id, [])

    if station_recipient:
        recipients = station_recipient + cfg.global_recipients
    
    else:
        recipients = cfg.global_recipients

    email(
        subject = cfg.d_subject.format(station_name = stat_name, station_id = stat_id),
        body = cfg.d_body.format(station_name = stat_name, station_id = stat_id, consecutive_offline = consec_offline, url=url, now=now),
        recipients = recipients
    )

# Send an email
def email(subject: str, body: str, recipients: list[str]) -> None:
    
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.from_email
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(cfg.server, cfg.port) as server:
        server.starttls(context=context)
        server.login(cfg.username, cfg.password)
        server.send_message(msg)

# Log the data
def log_data(now: str, station_id, station_name, status, consec_offline, event_type: str, message: str):
    path = Path("status_log.csv")
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            now, station_id, station_name,
            status, consec_offline,
            event_type, message
        ])

# Create base csv data file
def start_log():
    path = Path("status_log.csv")
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                "timestamp", "station_id", "station_name",
                "status", "consecutive_offline",
                "event_type", "message"
            ])

# Create base json status file
def write_start():

    status_json_file = Path("status.json")
    
    if not status_json_file.exists():

        data = {}

        for station, station_name in cfg.stations.items():

            data[station] = {
                "station_id": station,
                "station_name": station_name,
                "last_status": "Not Checked",
                "consecutive_offline": 0,
                "alert_sent": False,
                "last_online": None,
                "first_offline": None,
                "since_sent": None,
                "http_e": None,
                "time_e": None,
                "error": None,
            }

        write_json_file(data)
        print(f"\nJson Status File Made\n")

# Program

write_start()
start_log()

for station in cfg.stations:
    check_station(station)

print(f"\n\n\nSUMMARY:\n")
data = read_json_file()
for station, station_names in cfg.stations.items():
    if data[station]["last_status"] == "OFFLINE":
        print(f"[OFFLINE]: {station_names} ({station})")
    if data[station]["last_status"] == "RECOVERED":
        print(f"[RECOVERED]: {station_names} ({station})")