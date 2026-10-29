# Config for the Status checker
import os


# Get functions
def get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}

def get_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    return int(value)

def get_float(name: str, default: float) -> float:
    value = os.getenv(name)

    if value is None:
        return default

    return float(value)

def get_required_env(name: str):
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required enviromental variable: {name}")

    return value

develop = get_bool("DEVELOP", False)

# API:
api_post_url = get_required_env("API_POST_URL")
api_weather_post = get_required_env("API_WEATHER_POST")
if develop is True:
    api_base = "http://127.0.0.1:8000"
else:
    api_base = get_required_env("API_BASE")

api_key = get_required_env("API_KEY")

# Weather Underground Base URL:
wu_base_url = get_required_env("WU_BASE_URL")
website_url = os.getenv("WEBSITE_URL", "https://sbb.krupamlab.com")

# Retry Logic:
consecutive_offline = get_int("CONSECTUIVE_OFFLINE", 3)
max_retries = get_int("MAX_RETRIES", 5)
backoff_factor = get_int("BACKOFF_FACTOR", 3)

# Time:
pytz_timezone = os.getenv("PYTZ_TIMEZONE", "America/New_York")

# Reminders:
days_before_remind = get_int("DAYS_BEFORE_REMIN", 7)

# System Name:
system_name = os.getenv("SYSTEM_NAME", "KrupamC's Mesonet")

# Email Setup:
server = get_required_env("SERVER") # Email Server
port = get_required_env("PORT")
username = get_required_env("USERNAME") # Email
password = get_required_env("PASSWORD") # If Gmail account, then "App Password"
from_email = get_required_env("FROM_EMAIL") # What the email will appear as. Ex: "KrupamC's Mesonet Notifications <example@example.com"

# Emailing
error_email_cooldown = get_int("ERROR_EMAIL_COOLDOWN", 60)
monthly_email_day = get_int("MONTHLY_EMAIL_DAY", 1)
monthly_email_hour = get_int("MONTHLY_EMAIL_HOUR", 8)
monthly_weather_url = os.getenv("MONTHLY_WEATHER_URL", "/graph/analysis/month")

#---Email Text---

# Offline Alerts
d_subject = "[OFFLINE] {station_name} Weather Station appears offline"
d_body = (
    "Station {station_name} ({station_id}) appears OFFLINE on Weather Underground:\n\n"
    "URL: {url}\n"
    "Checked at: {now}\n"
    "Consecutive offline checks: {consecutive_offline}\n\n"
    f"~ {system_name} Mesonet Notification System"
)

# Recover Alerts
r_subject = "[RECOVERED] {station_name} ({station_id}) back online at {now}"
r_body = (
    "Station {station_name} ({station_id}) appears to be back online:\n\n"
    "URL: {url}\n"
    "Checked at: {now}\n"
    "Outage start: {outage_start}\n"
    "Outage duration: {outage_duration}\n\n"
    f"~ {system_name} Bay Mesonet Notification System"
)

# Offline Reminders
o_subject = "[OFFLINE REMINDER] {station_name} ({station_id}) Weather Station offline"
o_body = (
    "This is your {days} day reminder that Station {station_name} appears OFFLINE "
    "on Weather Underground:\n"
    "URL: {url}\n"
    "Checked at: {now}\n"
    "Consecutive offline checks: {consecutive_offline}\n\n"
    f"~ {system_name} Mesonet Notification System"
)

# Monthly Report
m_subject = "{month} Mesonet Reliability Report"
m_body = (
    "Reliability Report:\n"
    "{period_start} to {period_end}\n\n"
    "Overview:\n"
    "- Stations monitored: {stations_num}\n"
    "- Stations with outages: {s_w_outages}\n"
    "- Longest outage: {longest_station} ({longest_hour} hours)\n\n"
    "Per-station Summary:\n"
    "{station_summary}\n\n"
    f"~ {system_name} Mesonet Notification System"
)

# Weather Report
w_subject = "{month} Save Barnegat Bay Mesonet Monthly Summary"
w_body = (
    "Monthly Weather Summary:\n"
    "Reporting window: Past 30 Days\n"
    "Generated {generated_at}\n"
    "Station with available data: {row_len}"
)

# System Error Alerts
http_e_subject = f"{system_name} Checker HTTP Error"
scrape_e_subject = f"{system_name} Checker Scrape Error"
time_e_subject = f"{system_name} Checker Time Error"
post_e_subject = f"{system_name} Checker DB POST Error"
api_e_subject = f"{system_name} Checker API Error"

e_body = (
    "Error: {err}\n\n"
    f"~ {system_name} Mesonet Notification System"
)

time_e_body = (
    "Error (perhaps wifi issue?): {err}\n\n"
    f"~ {system_name} Mesonet Notification System"
)