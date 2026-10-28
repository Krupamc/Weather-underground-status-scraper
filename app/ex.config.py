import os
import json

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

def get_json(name: str, default):
    value = os.getenv(name)

    if not value:
        return default

    try:
        return json.loads(value)

    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in {name}: {e}")

# System Name:
system_name = os.getenv("SYSTEM_NAME", "KrupamC's")

# DB:
postgres_db = os.getenv("POSTGRES_DB", "mesonet")
postgres_user = os.getenv("POSTGRES_USER", "mesonet")
postgres_password = get_required_env("POSTGRES_PASSWORD")
postgres_host = os.getenv("POSTGRES_HOST", "db")
postgres_port = get_int("POSTGRES_PORT", 5432)

database_url = (
    f"postgresql+psycopg://{postgres_user}:"
    f"{postgres_password}@{postgres_host}:"
    f"{postgres_port}/{postgres_db}"
)

# Security:
secret_key = get_required_env("SECRET_KEY")
postgres_password= get_required_env("POSTGRES_PASSWORD")
api_key = get_required_env("API_KEY")
scraper_api_key = get_required_env("SCRAPER_API_KEY")
access_token_expire_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
algorithm = os.getenv("ALGORITHM", "HS256")
cookie_secure = get_bool("COOKIE_SECURE", False)
cookie_samesite = os.getenv("COOKIE_SAMESITE", "lax").lower()

# Devloping Mode
develop = get_bool("DEVELOP", False)

# Time Info
timezone = os.getenv("TIME_ZONE", "America/New_York")
time_zone_name = os.getenv("TIME_ZONE_NAME", "EST")

# Weather Underground Base URL:
wu_base_url = os.getenv("WU_BASE_URL", "https://preview.wunderground.com/dashboard/pws/")

# Seed Stations:
stations = get_json("STATIONS_JSON", {})

# Station Status History Query Default Values:
default_history = get_int("DEFAULT_HISTORY", 20)
limit_history = get_int("LIMIT_HISTORY", 1000)

# Temperature Widget:
m_temp_max = get_int("M_TEMP_MAX", 40) # C
m_temp_min = get_int("M_TEMP_MIN", 0)
temp_max = get_int("TEMP_MAX", 120) # F
temp_min = get_int("TEMP_MIN", -10)

# Pressure Widget:
pressure_min = get_float("PRESSURE_MIN", 29.12)
pressure_mid = get_float("PRESSURE_MID", 29.92)
pressure_max = get_float("PRESSURE_MAX", 30.72)
angle_max = get_int("ANGLE_MAX", 120)
angle_min = get_int("ANGLE_MIN", -120)

# Scrape Intervals
status_scraper_interval_seconds = get_int("STATUS_SCRAPER_INTERVAL_SECONDS", 900)
weather_scraper_interval_seconds = get_int("WEATHER_SCRAPER_INTERNAL_SECONDS", 60)


# Check if Option is allowed
allowed_cookie_samesite = {"lax", "strict", "none"}
if cookie_samesite not in allowed_cookie_samesite:
    raise RuntimeError(
        "COOKIE_SAMESITE must be one of: lax, strict, none"
    )