# Config for the Status checker

consecutive_offline = 3
max_retries = 5
backoff_factor = 3
pytz_timezone = "US/Eastern"

# Monthly Email Time/Day
monthly_email_day = 1
monthly_email_hour = 8

# Reminders
days_before_remind = 7

# Email Addresses
admin = ["example@example.com"]
report_users = ["example@example.com"]
global_recipients = ["example@example.com"]

# Email Addresses to recieve alerts
recipients = {
    #"KNJEXAMPLE1": [""],  #(Only global will get emails)
    #"KNJEXAMPLE3": ["example@example.com"]
}

# Weather Stations
stations = {
    "KNJEXAMPLE1": "Example Station",
    "KNEXAMPLE2": "Example Station 3"
}

#---Emails---

# Offline Alerts
d_subject = "[OFFLINE] {station_name} Weather Station appears offline"
d_body = "Station {station_name} ({station_id}) appears OFFLINE on Weather Underground:\n\nURL: {url}\nChecked at: {now}\nConsecutive offline checks: {consecutive_offline}\n\n\n~ Krupamc Mesonet Notification System\nFind the project at https://github.com/Krupamc/Weather-underground-status-scraper"

# Recover Alerts
r_subject = "[RECOVERED] {station_name} ({station_id} back online at {now})"
r_body = "Station {station_name} ({station_id}) appears to be back online:\n\nURL: {url}\nChecked at: {now}\nOutage start {outage_start}\nOutage duration: {outage_duration}\n\n\n~ Krupamc Mesonet Notification System\nFind the project at https://github.com/Krupamc/Weather-underground-status-scraper"

# Offline Reminders
o_subject = "[OFFLINE REMINDER] {station_name} ({station_id}) Weather Station offline"
o_body = "This is your {days} day reminder that Station {station_name} appears OFFLINE on Weather Underground:\nURL: {url}\nChecked at: {now}\nConsecutive offline checks: {consecutive_offline}\n\n\n~ Krupamc Mesonet Notification System\nFind the project at https://github.com/Krupamc/Weather-underground-status-scraper"

# Monthly Report
m_subject = "{month} Mesonet Reliability Report"
m_body = "Reliability Report:\n{period_start} to {period_end}\n\nOverview:\n- Stations monitored: {stations_num}\n- Stations with outages: {s_w_outages}\n- Longest outage: {longest_station} ({longest_hour} hours)\n\n\nPer-station Summary:\n{station_summary}\n\n\n~ Krupamc Mesonet Notification System\nFind the project at https://github.com/Krupamc/Weather-underground-status-scraper"

# System Error Alerts
http_e_subject = "Krupamc WU Checker HTTP Error:"
scrape_e_subject = "Krupamc WU Checker Scrape Error:"
time_e_subject = "Krupamc WU CHecker Time Error"

e_body = "Error: {err}"
time_e_body = "Error (perhaps wifi issue?): {err}"

# Email Setup
server = "smtp.example.com" # or other servers
port = 587
username = "example@gmail.com"
password = "password"
from_email = "Krupamc Mesonet Notifications <example@example.com>"