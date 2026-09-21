# Config for the Status checker

# API
api_post_url = "http://127.0.0.1:8000/status/stations"
api_base = "http://127.0.0.1:8000"
api_key = "test"
wu_base_url = "https://preview.wunderground.com/dashboard/pws/"

# Retry Logic
consecutive_offline = 3
max_retries = 5
backoff_factor = 3

pytz_timezone = "US/Eastern"

# Monthly Email Time/Day
monthly_email_day = 1
monthly_email_hour = 8
error_email_cooldown = 60 # Mins

# Reminders
days_before_remind = 7

#---Email Text---

# Offline Alerts
d_subject = "[OFFLINE] {station_name} Weather Station appears offline"
d_body = "Station {station_name} ({station_id}) appears OFFLINE on Weather Underground:\n\nURL: {url}\nChecked at: {now}\nConsecutive offline checks: {consecutive_offline}\n\n\n~ The Save Barnegat Bay Mesonet Notification System"

# Recover Alerts
r_subject = "[RECOVERED] {station_name} ({station_id} back online at {now})"
r_body = "Station {station_name} ({station_id}) appears to be back online:\n\nURL: {url}\nChecked at: {now}\nOutage start {outage_start}\nOutage duration: {outage_duration}\n\n\n~ The Save Barnegat Bay Mesonet Notification System"

# Offline Reminders
o_subject = "[OFFLINE REMINDER] {station_name} ({station_id}) Weather Station offline"
o_body = "This is your {days} day reminder that Station {station_name} appears OFFLINE on Weather Underground:\nURL: {url}\nChecked at: {now}\nConsecutive offline checks: {consecutive_offline}\n\n\n~ The Save Barnegat Bay Mesonet Notification System"

# Monthly Report
m_subject = "{month} Mesonet Reliability Report"
m_body = "Reliability Report:\n{period_start} to {period_end}\n\nOverview:\n- Stations monitored: {stations_num}\n- Stations with outages: {s_w_outages}\n- Longest outage: {longest_station} ({longest_hour} hours)\n\n\nPer-station Summary:\n{station_summary}\n\n\n~ The Save Barnegat Bay Mesonet Notification System"

# System Error Alerts
http_e_subject = "SBB WU Checker HTTP Error:"
scrape_e_subject = "SBB WU Checker Scrape Error:"
time_e_subject = "SBB WU Checker Time Error"
post_e_subject = "SBB WU Checker DB POST Error"
api_e_subject = "SBB WU Checker API Error"

e_body = "Error: {err}"
time_e_body = "Error (perhaps wifi issue?): {err}"

# Email Setup
server = "smtp.gmail.com"
port = 587
username = "theunknownboss1999@gmail.com"
password = "dpdlzimvidrstktv"
from_email = "Save Barnegat Bay Mesonet Notifications <theunknownboss1999@gmail.com>"