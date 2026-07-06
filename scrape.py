import config as cfg
import requests
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup as bs
from pathlib import Path
import smtplib
import ssl
from email.message import EmailMessage
import json
from datetime import datetime, timedelta
import pytz
import time
import csv

# monthly overview  + maintence mode/redo notific after 7 days

def check_station(station_id):

    station_name = cfg.stations[station_id]

    now = get_time(station_id, station_name)
    if now is None:
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
            if not is_in_maintenance(station_id):
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
            if not is_in_maintenance(station_id):
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
    
        # First Alert email
        if consec_offline >= cfg.consecutive_offline and not data[station_id]["alert_sent"] and not is_in_maintenance(station_id):
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
            data[station_id]["since_first_alert"] = now.isoformat()
            data[station_id]["alert_sent"] = True
            write_json_file(data)
            log_data(now.isoformat(), station_id, station_name, "OFFLINE", consec_offline, "offline_alert", "Threshold Reached, email sent")
        
        # Reminder Emails
        elif data[station_id]["alert_sent"] and should_send_reminder(data[station_id], now) and not is_in_maintenance(station_id):
            offline_remind(
                stat_id=station_id,
                stat_name=station_name,
                consec_offline=data[station_id]["consecutive_offline"],
                url=url,
                now=now
            )

            data[station_id]["last_reminder_sent"] = now.isoformat()
            write_json_file(data)

        else:
            log_data(now.isoformat(), station_id, station_name, "OFFLINE", consec_offline, "check", "ok")

    elif status == "connected":
        # Open json
        data = read_json_file()
        data[station_id]["last_status"] = "CONNECTED"
        
        # Recovery
        if data[station_id]["alert_sent"] and not is_in_maintenance(station_id):
            print(f"[RECOVERED] {station_name} ({station_id})")
            status = "recovered"
            outage_start_str = data[station_id]["first_offline"]

            if outage_start_str:
                outage_start = datetime.fromisoformat(outage_start_str)
                outage_dur = now - outage_start
            
            else:
                outage_start = None
                outage_dur = None

            recover_alert(
                stat_id=station_id, 
                stat_name=station_name, 
                url=url, 
                start=outage_start,
                duration=outage_dur,
                now=now
            )
            data[station_id]["last_status"] = "RECOVERED"
            log_data(now.isoformat(), station_id, station_name, "RECOVERED", data[station_id]["consecutive_offline"], "recovered", "Station_recovered")
            data[station_id]["last_reminder_sent"] = None
            data[station_id]["first_offline"] = None
            data[station_id]["last_connected"] = now.isoformat()
            data[station_id]["alert_sent"] = False
            data[station_id]["consecutive_offline"] = 0
            write_json_file(data)
            
        
        else:
            log_data(now.isoformat(), station_id, station_name, "CONNECTED", data[station_id]["consecutive_offline"], "check", "ok")
            data[station_id]["first_offline"] = None
            data[station_id]["last_status"] = "CONNECTED"
            data[station_id]["last_connected"] = now.isoformat()
            data[station_id]["alert_sent"] = False
            data[station_id]["consecutive_offline"] = 0
            write_json_file(data)
 
# time - error protected
def get_time(station_id, station_name) -> datetime:
    for attempt in range(cfg.max_retries):
        try:
            utc_now = datetime.now(pytz.UTC)
            eastern = pytz.timezone(cfg.pytz_timezone)
            now = utc_now.astimezone(eastern)
            return now

        except Exception as e:
            print(f"[TIME ERROR]: Failed to get time for {station_id}. Error: {e}")
           
            # Write to file
            data = read_json_file()
            e = str(e)
            log_data(None, station_id, station_name, "error", data[station_id]["consecutive_offline"], "Time_error", f"{e}")

            # Email
            if not is_in_maintenance(station_id):
                email(
                    subject=cfg.time_e_subject,
                    body=cfg.time_e_body.format(err = e),
                    recipients=cfg.admin
                )
    else:
        return
    
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

# Use alert functions
def offline_remind(stat_id, stat_name, consec_offline, url, now):
    station_recipient = cfg.recipients.get(stat_id, [])

    if station_recipient:
        recipients = station_recipient + cfg.global_recipients

    else:
        recipients = cfg.global_recipients
    
    email(
        subject = cfg.o_subject.format(station_name = stat_name, station_id = stat_id),
        body = cfg.o_body.format(days = cfg.days_before_remind, station_name = stat_name, station_id = stat_id, consecutive_offline = consec_offline, url=url, now=now),
        recipients=recipients
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

# Report/stats

def send_report(now: datetime, period_start, period_end):
    report = read_report_file()
    data = read_json_file()
    recipients=cfg.report_users

    email(
        subject = cfg.m_subject.format(month = now.month),
        body = cfg.m_body.format(last_report=period_start, period_end=period_end, stations_num=len(data), ),
        recipients=recipients
    )

def write_report(now: datetime):
    period_start, period_end = get_previous_month_period(now)
    

    send_report(now, period_start, period_end)
def get_previous_month_period(now: datetime):
    first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_this_month - timedelta(seconds=1)

    period_end = last_month_end
    period_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    return period_start, period_end
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

def read_json_file():
    with open("status.json", "r", encoding="utf-8") as file:
         data = json.load(file)
    return data

def write_json_file(data):
    with open("status.json", "w", encoding="utf-8") as file:
        json.dump(data, file, indent = 2)

def read_maintenance_file():
    with open("maintenance.json", "r", encoding="utf-8") as file:
        data = json.load(file)
    return data

def write_maintenance_file(data):
    with open("maintenance.json", "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

def read_report_file():
    with open("report.json", "r", encoding="utf-8") as file:
        data = json.load(file)
    return data

def write_report_file(data):
    with open("report.json", "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

def is_in_maintenance(station_id):
    data = read_maintenance_file()

    if data[station_id]["enabled"]:
        return True
    
    else:
        return False

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
    print(f"\nCSV Log Created\n")

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
                "last_connected": None,
                "first_offline": None,
                "since_first_alert": None,
                "last_reminder_sent": None,
                "http_e": None,
                "time_e": None,
                "error": None,
            }

        write_json_file(data)
        print(f"\nJson Status File Created\n")

# Create Report json file:
def report_write_start(now: datetime):
    report_json = Path("report.json")

    if not report_json.exists():
        
        data = {
            "last_report": now.isoformat()
        }
        
        write_report_file(data)
    print(f"\nReport File Created\n")

# Create maintence json status file:
def maintenance_write_start():
    maintenance_json_file = Path("maintenance.json")

    if not maintenance_json_file.exists():

        data = {}

        for station, station_name in cfg.stations.items():
            data[station] = {
                "station_id": station,
                "station_name": station_name,
                "enabled": False,
                "changed_at": None
            }
        write_maintenance_file(data)
    print(f"\nMaintenance File Created\n")

# Check if we should send a reminder
def should_send_reminder(station, now):
    last_reminder = station["last_reminder_sent"]

    if not station["alert_sent"]:
        return False

    if station["last_status"] != "OFFLINE":
        return False

    if last_reminder is None:
        return True

    last_reminder = datetime.fromisoformat(last_reminder)
    if (now - last_reminder) >= timedelta(days=cfg.days_before_remind):
        return True
    
    else:
        return False


# Check if it it 
def check_if_report_day(now: datetime):
    # Email send on the first of the month at 8 AM
    if now.day == cfg.monthly_email_day:
        if now.hour == cfg.monthly_email_hour:
            return True
    else:
        return False
            

#---Program---

# Intializers
maintenance_write_start()
write_start()
start_log()

# Scrape/email/save loop
for station in cfg.stations:
    check_station(station)
# Monthy Report
now = get_time("Report", "Report")

report_write_start(now.isoformat())
if check_if_report_day(now):
    write_report(now)


print(f"\n\n\nSUMMARY:\n")
data = read_json_file()
for station, station_names in cfg.stations.items():
    if data[station]["last_status"] == "OFFLINE":
        print(f"[OFFLINE]: {station_names} ({station})")
    if data[station]["last_status"] == "RECOVERED":
        print(f"[RECOVERED]: {station_names} ({station})")
print(len(data))