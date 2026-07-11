from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint
from datetime import datetime
import web_config as cfg
import pytz

# Function to parse iso 8601 to datetime timezone
def parse_iso_to_zone(iso_str: str, tz_name: str = cfg.timezone) -> datetime:
    dt = datetime.fromisoformat(iso_str)

    # if no tzinfo, UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    
    # Else convert to selected timezone
    timezone = pytz.timezone(tz_name)
    return dt.astimezone(timezone)

def zoned_now(tz_name: str = cfg.timezone) -> datetime:
    utc_now = datetime.now(pytz.UTC)
    timezone = pytz.timezone(tz_name)
    return utc_now.astimezone(timezone)

# ---Station---

# Base Model
class StationBase(SQLModel):
    station_id: str = Field(index=True, unique=True)
    station_name: str = Field(index=True)
    is_in_maintenance: bool = Field(default=False)
    is_public: bool = Field(default=False)

# Model For Database (Table Model):
class Station(StationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

class StationPublic(StationBase):
    id: int

class StationCreate(StationBase):
    pass

# Update Model
class StationUpdate(SQLModel):
    station_name: str | None = None
    is_in_maintenance: bool | None = None
    is_public: bool | None = None

# ---Status---
class StatusBase(SQLModel):
    station_id: str = Field(index=True, unique=True, foreign_key="station.station_id")
    time_of_status: datetime = Field(index=True, default_factory=zoned_now)
    last_status: str = Field(default="UNKNOWN")
    consecutive_offline: int = Field(default=0)
    first_offline: datetime | None = Field(default=None)
    last_connected: datetime | None = Field(default=None)
    alert_sent: bool = Field(default=False)

class Status(StatusBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

class StatusPublic(StatusBase):
    id: int

class StatusCreate(StatusBase):
    pass

# ---Status History---

class StatusHistoryBase(SQLModel):
    station_id: str = Field(index=True, foreign_key="station.station_id")
    # Name? Most likely not neccesary
    time_of_status: datetime = Field(index=True, default_factory=zoned_now)  # Convert from iso 8601 to datetime
    last_status: str = Field(default="UNKNOWN")
    consecutive_offline: int = Field(default=0)
    first_offline: datetime | None = Field(default=None)
    last_connected: datetime | None = Field(default=None)
    alert_sent: bool = Field(default=False)

class StatusHistory(StatusHistoryBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

class StatusHistoryPublic(StatusHistoryBase):
    id: int

class StatusHistoryCreate(StatusHistoryBase):
    pass

# ---Weather---
class WeatherBase(SQLModel):
    station_id: str = Field(index=True, unique=True, foreign_key="station.station_id")
    observed_at: datetime = Field(index=True, default_factory=zoned_now)
    temp: float | None = None
    dewpoint: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    wind_gust: float | None = None
    wind_dir: float | None = None
    pressure: float | None = None
    precip_rate: float | None = None
    precip_accum: float | None = None
    uv: float | None = None
    solar: float | None = None

class Weather(WeatherBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    
class WeatherPublic(WeatherBase):
    id: int

class WeatherCreate(WeatherBase):
    pass

# ---Weather History---

class WeatherHistoryBase(SQLModel):
    station_id: str = Field(index=True, foreign_key="station.station_id")
    observed_at: datetime = Field(index = True, default_factory=zoned_now)
    # Name prob ain't needed
    temp: float | None = None
    dewpoint: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    wind_gust: float | None = None
    wind_dir: float | None = None
    pressure: float | None = None
    precip_rate: float | None = None
    precip_accum: float | None = None
    uv: float | None = None
    solar: float | None = None

class WeatherHistory(WeatherHistoryBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

class WeatherHistoryPublic(WeatherHistoryBase):
    id: int

class WeatherHistoryCreate(WeatherHistoryBase):
    pass



# ---User---

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    role: str = Field(index=True)

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password_hash: str

class UserPublic(UserBase):
    id: int

class UserCreate(SQLModel):
    username: str
    password: str
    role: str

class UserUpdate(SQLModel):
    password: str | None = None
    role: str

# ---User Access---

class UserAccessBase(SQLModel):
    user_id: int = Field(index=True, foreign_key="user.id")
    station_id: str = Field(index=True, foreign_key="station.station_id")
    can_view: bool = Field(default=False)
    can_toggle_maintenance: bool = Field(default = False)

class UserAccess(UserAccessBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    __table_args__ = (
        UniqueConstraint("user_id", "station_id", name="uq_user_station"),
    )

class UserAccessPublic(UserAccessBase):
    id: int

class UserAccessCreate(UserAccessBase):
    pass