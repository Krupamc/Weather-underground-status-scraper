import config as cfg
import requests
from requests.exceptions import HTTPError, RequestException
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

# Main scraping loop
def check_station(station_id):

    station_name = cfg.stations[station_id]

    now = get_time(station_id, station_name)
    if now is None:
        return

    for attempt in range(cfg.max_retries): # Try the scraping for configered 
        try:
            url = f"https://preview.wunderground.com/dashboard/pws/{station_id}" # Base url
            r = requests.get(url, timeout=10)
            r.raise_for_status()

            soup = bs(r.content, "html.parser")

            # Get station name and status
            
            status_header = soup.find("pws-status")
            if status_header is None:
                raise ValueError("pws-status tag not found") # logging scrap erro

            status = status_header["data-status"]
            
            if status == "offline":
                status2 = " offline "
            else: status2 = status
            print(f"[{status2.upper()}]: {station_name}")
            break
        
        # If there HTTP Error, save and email
        except HTTPError as e:
            last_error = f"HTTP error: {e}"
            wait_time = cfg.backoff_factor ** attempt
            print(f"[HTTP ERROR]: {e}\nRetrying in {wait_time} seconds")
            
            time.sleep(wait_time)
            continue
        
        except RequestException as e:
            last_error = f"Request error {e}"
            wait_time = cfg.backoff_factor ** attempt

            print(f"[REQUEST ERROR]: {e}\nRetrying in {wait_time} seconds")
            time.sleep(wait_time)
        
        # If there is another other error, save and email
        except Exception as e:
            last_error = f"Scraping error: {e}"
            print(f"[SCRAPING ERROR]: Failed to get data for {station_id}. Error: {e}")
            break
    else:
        data = read_json_file
        log_data(now.isoformat(), station_id, station_name, "error", data[station_id]["consecutive_offline"], "request_error", last_error)

        if not is_in_maintenance(station_id):
            email(
                subject=cfg.scrape_e_subject,
                body=cfg.scrape_e_body.format(err=last_error),
                recipients=cfg.admin
            )
        
        return
    
    # Logic for if a station is offline
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

    # Logic for if a station is connected
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
            
        # If not a recovered station: 
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

        # If there is a error, log and send email
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
        subject =cfg.r_subject.format(station_name=stat_name, station_id=stat_id, now=now),
        body = cfg.r_body.format(station_name=stat_name, station_id=stat_id, url=url, outage_start=start, outage_duration=duration, now=now),
        recipients = recipients
    )

    # Other alert method

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

    # Other alert methods

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

    # Other alert methods

#---Report/stats---

def send_report(now: datetime, period_start, period_end, stations_with_outages, longest_station_name, longest_hour, station_summary):
    report = read_report_file()
    recipients=cfg.report_users
    stations_num = len(cfg.stations)

    email(
        subject = cfg.m_subject.format(month = now.strftime("%B")),
        body = cfg.m_body.format(
            period_start=period_start,
            period_end=period_end, 
            stations_num=stations_num, 
            s_w_outages=stations_with_outages, 
            longest_station=longest_station_name,
            longest_hour=longest_hour,
            station_summary=station_summary
            ),
        recipients=recipients
    )

    report["last_report"] = now.isoformat()
    write_report_file(report)

def write_report(now: datetime):
    period_start, period_end = get_previous_month_period(now)
    stats, station_summary = compute_monthly_stats(period_start, period_end)
    stations_with_outages = sum(1 for s in stats.values() if s["outage_count"] > 0)

    # longest outage
    longest_station = None
    longest_duration = timedelta(0)
    for s in stats.values():
        if s["longest_outage"] > longest_duration:
            longest_duration = s["longest_outage"]
            longest_station = s

    longest_hour = 0.0
    longest_station_name = "No outages"
    if longest_station:
        longest_hour = longest_duration.total_seconds() / 3600.0
        longest_station_name = longest_station["station_name"]



    send_report(now, period_start.date(), period_end.date(), stations_with_outages, longest_station_name, longest_hour, station_summary)

def get_previous_month_period(now: datetime):
    first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_this_month - timedelta(seconds=1)

    period_end = last_month_end
    period_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    return period_start, period_end

def compute_monthly_stats(period_start: datetime, period_end: datetime):
    stats = {}

    # per station
    for station_id, station_name in cfg.stations.items():
        stats[station_id] = {
            "station_id": station_id,
            "station_name": station_name,
            "outages": [],
            "total_downtime": timedelta(0),
            "longest_outage": timedelta(0),
            "outage_count": 0,
        }

    path = Path("status_log.csv")
    if not path.exists():
        return stats, "No station data available.\n"
    
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        current_outage = {sid: None for sid in cfg.stations.keys()}

        for row in reader:
            ts_str = row["timestamp"]
            station_id = row["station_id"]
            status = row["status"]

            if not ts_str or station_id not in stats:
                continue

            ts = datetime.fromisoformat(ts_str)
            if ts < period_start or ts > period_end:
                continue

            # If there is offline, start outage
            if status == "OFFLINE":
                if current_outage[station_id] is None:
                    current_outage[station_id] = ts
                
            # End outage on recovered or connected
            elif status in ("RECOVERED", "CONNECTED"):
                start_ts = current_outage[station_id]
                if start_ts is not None:
                    end_ts = ts
                    duration = end_ts - start_ts
                    stats[station_id]["outages"].append({
                        "start": start_ts,
                        "end": end_ts,
                        "duration": duration,
                    })
                    stats[station_id]["outage_count"] += 1
                    stats[station_id]["total_downtime"] += duration
                    if duration > stats[station_id]["longest_outage"]:
                        stats[station_id]["longest_outage"] = duration
                    current_outage[station_id] = None

    for station_id, start_ts in current_outage.items():
        if start_ts is not None and start_ts <= period_end:
            end_ts = period_end
            duration = end_ts - start_ts
            stats[station_id]["outages"].append({
                "start": start_ts,
                "end": end_ts,
                "duration": duration,
            })
            stats[station_id]["outage_count"] += 1
            stats[station_id]["total_downtime"] += duration
            if duration > stats[station_id]["longest_outage"]:
                stats[station_id]["longest_outage"] = duration
    
    total_period = period_end - period_start
    for station_id, s in stats.items():
        downtime_hours = s["total_downtime"].total_seconds() / 3600.0
        total_hours = total_period.total_seconds() / 3600.0
        if total_hours > 0:
            uptime_pct = 100.0 * (total_hours - downtime_hours) / total_hours
        else:
            uptime_pct = 100.0
        s["uptime_pct"] = round(uptime_pct, 3)

    # per-station summary
    summary_lines = []
    for s in stats.values():
        summary_lines.append(
            f"- {s['station_name']} ({s['station_id']}): "
            f"{s['outage_count']} outages, "
            f"{s['total_downtime'].total_seconds() / 3600.0:.2f} hours downtime, "
            f"{s['uptime_pct']:.3f}% uptime"
        )
    
    station_summary = "\n".join(summary_lines)

    return stats, station_summary

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

# Read/write to file

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

# Check if a station is in maintenance
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
        print(f"\nJson Status File Created\n")
        write_json_file(data)
        

# Create Report json file:
def report_write_start(now: datetime):
    report_json = Path("report.json")

    if not report_json.exists():
        
        data = {
            "last_report": None
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
        
    else:
        return False
            
# Check if we had sent a report lately
def should_send_report(now: datetime):
    if not check_if_report_day(now):
        return False
    
    report = read_report_file()
    last_report = report.get("last_report")

    if last_report is None:
        return True
   
    try:
      last_dt = datetime.fromisoformat(last_report)
    except ValueError:
        return True

    return not (last_dt.year == now.year and last_dt.month == now.month)


#---Program---

# Intializers
maintenance_write_start()
write_start()
start_log()
now = get_time("Report", "Report")
if now is not None:
    report_write_start(now)


# Scrape/email/save loop
for station in cfg.stations:
    check_station(station)
# Monthy Report
if should_send_report(now):
    write_report(now)

# Print everything
print(f"\n\n\nSUMMARY:\n")
data = read_json_file()
for station, station_names in cfg.stations.items():
    if data[station]["last_status"] == "OFFLINE":
        print(f"[OFFLINE]: {station_names} ({station})")
    if data[station]["last_status"] == "RECOVERED":
        print(f"[RECOVERED]: {station_names} ({station})")

write_report(now)