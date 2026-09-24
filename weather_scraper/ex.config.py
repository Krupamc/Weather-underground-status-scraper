# Config for the Status checker
import os
from pathlib import Path

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

def get_float(name: str, default: float) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    return float(value)

def get_required_env(name: str):
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required enviromental variable: {name}")

    return value

# API:
api_post_url = get_required_env("API_POST_URL")
api_weather_post = get_required_env("API_WEATHER_POST")
api_base = get_required_env("API_BASE")
api_key = get_required_env("API_KEY")

# Weather Underground Base URL:
wu_base_url = get_required_env("WU_BASE_URL")

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
