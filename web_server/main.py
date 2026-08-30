# Web Deployment using sqlite:

from fastapi import FastAPI, Cookie, HTTPException, Query, Depends, status, Request, Header, Form, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Annotated
from scipy import stats
from sqlmodel import select
import database as db
import model as m
import web_config as cfg
import security as s
import pytz, csv, io, jwt, statistics
from jwt import InvalidTokenError
from datetime import datetime, timedelta, date, time
import convert_metric as cv
import matplotlib
import numpy as np
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import matplotlib.dates as mdates


app = FastAPI(title="SBB Mesonet Notification System")

# Turn off docs
#app = FastAPI(title="SBB Mesonet Notification System", docs_url=None, redoc_url=None, openapi_url=None)

# Graph text
roboto_path = "web_server/static/fonts/Roboto-Regular.ttf"
fm.fontManager.addfont(roboto_path)
plt.rcParams["font.family"] = fm.FontProperties(fname=roboto_path).get_name()


# Security using JWT
#oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Make sure only stations in the config are in server:
def seed_stations(): # perhaps add auto delete if not in dict?
    with db.Session(db.engine) as session:
        db_station = session.exec(select(m.Station)).all()
        
        db_ids = {station.station_id for station in db_station}
        config_ids = set(cfg.stations.keys())
        
        # If a station is in the config but not the db, add it
        for station_id, station_name in sorted(cfg.stations.items(), key=lambda item: item[1].lower()):
            if station_id not in db_ids:
                session.add(
                    m.Station(
                        station_id=station_id,
                        station_name=station_name,
                        is_in_maintenance=False
                    )
                )
        
        # If there is a extra station in the db, delete it
        #for station in db_station:
        #    if station.station_id not in config_ids:
        #        session.delete(station)
        #        # make it delet its other models...

        session.commit()

# Passes user into each template
def template_context(request: Request):
    
    # Read cookie from heaer
    access_token = request.cookies.get("access_token")
    current_user = None

    if access_token:
        try:
            # Decode cookie and get username
            payload = jwt.decode(access_token, s.secret_key, algorithms=[s.algorithm])
            username = payload.get("sub")

            # Select user from username
            if username:
                with db.Session(db.engine) as session:
                    current_user = session.exec(select(m.User).where(m.User.username == username)).first()
        except InvalidTokenError:
            current_user = None
    
    return {"current_user": current_user}

# Check what user
def get_current_user(session: db.SessionDep, access_token: str | None = Cookie(default=None)):

    # Setup the exception
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated; login")

    # If no cookie
    if access_token is None:
        raise credentials_exception
    
    try:
        # Decode cookie for username
        payload = jwt.decode(access_token, s.secret_key, algorithms=[s.algorithm],)
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    # Get user from username
    user = session.exec(select(m.User).where(m.User.username == username)).first()

    if user is None:
        raise credentials_exception

    return user
    
# Check if someone is signed in, NOT REQUIRED
def get_current_user_op(session: db.SessionDep, access_token: str | None = Cookie(default=None)):
    if access_token is None:
        return None
    
    try: 
        # Decode key
        payload = jwt.decode(access_token, s.secret_key, algorithms=[s.algorithm])
        username = payload.get("sub")
        if username is None:
            return None
    except InvalidTokenError:
        return None
    
    return session.exec(select(m.User).where(m.User.username == username)).first()

# Static and Templates
templates = Jinja2Templates(directory="web_server/templates", context_processors=[template_context])
app.mount("/static", StaticFiles(directory="web_server/static"), name="static")

# Force admin
def require_admin(current_user: Annotated[m.User, Depends(get_current_user)]):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Enough Permissions")
    return current_user

# Force user having access to a station
def require_station_access(station_id: str, current_user: Annotated[m.User, Depends(get_current_user)], session: db.SessionDep):

    # Open Station
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    
    if not station:
        raise HTTPException(status_code=404, detail="Station Does Not Exist")

    # Admin override
    if current_user.role == "admin":
        return station

    # Where user can access station
    access = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == current_user.id, m.UserAccess.station_id == station_id, m.UserAccess.can_view == True)).first()

    if not access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Enough Permissions")
    
    return station

# Convert wind directions to their labels
def degree_to_label(degree: int | None) -> str | None:
    if degree is None:
        return None
    
    map = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW",
    ]

    degree2 = degree % 360
    index = round(degree2 / 22.5) % 16

    return map[index]

# Convert date/time to selected timezone (can be configered to not be eastern in config)
def get_date_and_time(input_time):

    if input_time is None:
        return None, None

    timee = m.to_eastern(input_time)
    # Format
    r_date = datetime.strftime(timee, "%B %d, %Y")
    r_time = datetime.strftime(timee, "%I:%M %p")

    return r_date, r_time

#----Actual Web App-----

# What to do on startup
@app.on_event("startup")
def on_startup():
    db.create_db_table()
    seed_stations()


# Homepage
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with db.Session(db.engine) as session:
            stations = session.exec(select(m.Station)).all()
    return templates.TemplateResponse(request, "home.html", {"request": request, "stations": stations, "num_of_stations": len(stations)})

# Manually go to 404 error
@app.get("/404", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "404.html", {"request": request, "title": "404"})

# For any http error, send them to a specific error page
@app.exception_handler(StarletteHTTPException)
async def not_found(request: Request, exc: StarletteHTTPException):
    # HTTP Errors
    if exc.status_code == 404:
        return templates.TemplateResponse(request, "404.html", {"request": request, "title": "404", "detail": exc.detail})
    elif exc.status_code == 403:
        return templates.TemplateResponse(request, "403.html", {"request": request, "title": "403", "detail": exc.detail})
    elif exc.status_code == 401:
        return templates.TemplateResponse(request, "401.html", {"request": request, "title": "401", "detail": exc.detail})
    elif exc.status_code == 400:
        return templates.TemplateResponse(request, "400.html", {"request": request, "title": "400", "detail": exc.detail})
    elif exc.status_code == 500:
        return templates.TemplateResponse(request, "500.html", {"request": request, "title": "500", "detail": exc.detail})
    
    return await http_exception_handler(request, exc)

# List of Stations
@app.get("/stations", response_class=HTMLResponse)
def stations(request: Request):
    with db.Session(db.engine) as session:
        stations = session.exec(select(m.Station)).all()
    return templates.TemplateResponse(request, "stations.html", context={"request": request, "title": "Weather Stations", "active_page": "stations", "stations": stations})

# Stations owned
@app.get("/my-stations", response_class=HTMLResponse)
def my_stations(request: Request, session: db.SessionDep, current_user: Annotated[m.User, Depends(get_current_user)]):
    # Admin pass
    if current_user.role == "admin":
        stations = session.exec(select(m.Station).order_by(m.Station.station_name)).all()
        return templates.TemplateResponse(request, "my_stations.html", context={"request": request, "title": "My Stations", "active_page": "my_stations", "station_rows": stations})

    # Load stations
    stations = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == current_user.id, m.UserAccess.can_view == True).order_by(m.Station.station_name)).all()

    # Add names to list
    station_rows = []
    for access in stations:
        station = session.exec(select(m.Station).where(m.Station.station_id == access.station_id)).first()
        if station:
            station_rows.append({
                "station_id": access.station_id,
                "station_name": station.station_name
            })

    # Send list to html to render
    return templates.TemplateResponse(request, "my_stations.html", context={"request": request, "title": "My Stations", "active_page": "my_stations", "station_rows": station_rows})

# Public dashboard for the station:
@app.get("/stations/public/{station_id}", response_class=HTMLResponse)
def public_station(request: Request, session: db.SessionDep, station_id: str, selected_date: str | None = None):

    # Check units:
    units = request.query_params.get("units", "imperial")

    # Open DB tables
    status = session.exec(select(m.Status).where(m.Status.station_id == station_id)).first()
    weather = session.exec(select(m.Weather).where(m.Weather.station_id == station_id)).first()
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()

    if not status or not station or not weather:
        raise HTTPException(status_code=404, detail="Station Not Found")

    # Time Expressions convert
    if weather is not None:
        d_date, d_time = get_date_and_time(weather.observed_at)

        # Wind dir label
        wind_label = degree_to_label(weather.wind_dir)

    # - Table -
    local_tz = pytz.timezone(cfg.timezone)

    if not selected_date or selected_date == "None":
        day_local = datetime.now(local_tz).date()
    else:
        try:
            day_local = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            day_local = datetime.now(local_tz).date()

    prev_day = (day_local - timedelta(days=1)).isoformat()
    next_day = (day_local + timedelta(days=1)).isoformat()

    day_start_local = local_tz.localize(datetime.combine(day_local, time.min))
    day_end_local = local_tz.localize(datetime.combine(day_local, time.max))

    day_start_utc = day_start_local.astimezone(pytz.UTC)
    day_end_utc = day_end_local.astimezone(pytz.UTC)

    # Get the history
    history = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_id, m.WeatherHistory.observed_at >= day_start_utc, m.WeatherHistory.observed_at <= day_end_utc).order_by(m.WeatherHistory.observed_at)).all()

    # Make the rows
    table_rows = []

    for row in history:
        observed_at = row.observed_at

        if observed_at.tzinfo is None:
            observed_at = pytz.UTC.localize(observed_at)

        local_time = observed_at.astimezone(local_tz)

        # Convert
        if units == "metric":
            table_rows.append({
                "time": local_time.strftime("%I:%M %p"),
                "temp": row.temp,
                "dewpoint": row.dewpoint,
                "humidity": row.humidity,
                "pressure": cv.inhg_to_hpa(row.pressure) if row.pressure is not None else None,
                "wind_speed": row.wind_speed,
                "wind_gust": row.wind_gust,
                "wind_dir": row.wind_dir,
                "precip_rate": cv.in_to_mm(row.precip_rate) if row.precip_rate is not None else None,
                "precip_accum": cv.in_to_mm(row.precip_accum) if row.precip_accum is not None else None,
                "uv": row.uv,
                "solar": row.solar
            })
        else:
            table_rows.append({
                "time": local_time.strftime("%I:%M %p"),
                "temp": cv.c_to_f(row.temp) if row.temp is not None else None,
                "dewpoint": cv.c_to_f(row.dewpoint) if row.dewpoint is not None else None,
                "humidity": row.humidity,
                "pressure": row.pressure,
                "wind_speed": cv.knots_to_mph(row.wind_speed) if row.wind_speed is not None else None,
                "wind_gust": cv.knots_to_mph(row.wind_gust) if row.wind_gust is not None else None,
                "wind_dir": row.wind_dir,
                "precip_rate": row.precip_rate,
                "precip_accum": row.precip_accum,
                "uv": row.uv,
                "solar": row.solar
            })

    # Get CSV
    csv_url = None

    if day_local:
        csv_url = f"/stations/weather/csv/{station_id}?selected_date={day_local.isoformat()}&units={units}"

    # Imperial
    if units == "metric":

        # Temp Percent fill
        temp_pct = 0
        if weather and weather.temp is not None:
            temp_pct = ((weather.temp - cfg.m_temp_min) / (cfg.m_temp_max - cfg.m_temp_min)) * 100
            temp_pct = max(0, min(100, temp_pct)) 

        # Pressure dial
        pressure_angle = 180
        if weather and weather.pressure is not None:

            pressure = cv.inhg_to_hpa(weather.pressure)
            pressure_min = cv.inhg_to_hpa(cfg.pressure_min)
            pressure_mid = cv.inhg_to_hpa(cfg.pressure_mid)
            pressure_max = cv.inhg_to_hpa(cfg.pressure_max)


            pressure_angle_1 = ((pressure - pressure_min) / (pressure_max - pressure_min)) * (cfg.angle_max - cfg.angle_min) + cfg.angle_min
            pressure_angle = round(max(cfg.angle_min, min(cfg.angle_max, pressure_angle_1)), 2)
        
        # Precip
        precip_r = cv.in_to_mm(weather.precip_rate)
        precip_a = cv.in_to_mm(weather.precip_accum)


        pressure_labels = {
            "low": pressure_min,
            "mid": pressure_mid,
            "high": pressure_max
        }

        w_units = {
            "temp": "°C",
            "precip_r": "mm/hr",
            "precip_a": "mm",
            "wind": "knots",
            "pressure": "hPa"
        }

        converted = {
            "pressure": pressure,
            "precip_r": precip_r,
            "precip_a": precip_a,
            "temp": weather.temp,
            "dew_p": weather.dewpoint,
            "wind_speed": weather.wind_speed,
            "wind_gust": weather.wind_gust
        }

    else:

        # Thermometer percent fill
        temp = cv.c_to_f(weather.temp)
        dew_p = cv.c_to_f(weather.dewpoint)

        temp_pct = 0
        if weather and weather.temp is not None:
            temp_pct = ((temp - cfg.temp_min) / (cfg.temp_max - cfg.temp_min)) * 100
            temp_pct = max(0, min(100, temp_pct))

        
        # Pressure dial
        pressure_angle = 180
        if weather and weather.pressure is not None:
            pressure_angle_1 = ((weather.pressure - cfg.pressure_min) / (cfg.pressure_max - cfg.pressure_min)) * (cfg.angle_max - cfg.angle_min) + cfg.angle_min
            pressure_angle = round(max(cfg.angle_min, min(cfg.angle_max, pressure_angle_1)), 2)

        # Knots - mph
        wind_speed = cv.knots_to_mph(weather.wind_speed)
        wind_gust = cv.knots_to_mph(weather.wind_gust)

        pressure_labels = {
            "low": cfg.pressure_min,
            "mid": cfg.pressure_mid,
            "high": cfg.pressure_max,
        }

        w_units = {
            "temp": "°F",
            "precip_r": "in/hr",
            "precip_a": "in",
            "wind": "mph",
            "pressure": "inHg",
        }

        converted = {
            "temp": temp,
            "dew_p": dew_p,
            "pressure": weather.pressure,
            "precip_r": weather.precip_rate,
            "precip_a": weather.precip_accum,
            "wind_speed": wind_speed,
            "wind_gust": wind_gust,
        }

    return templates.TemplateResponse(request, "public_dash.html", context={
        "request": request, 
        "title": f"{station.station_name} Station Dashboard", 
        "active_page": "stations", 
        "station": station, 
        "station_id": station_id,
        "weather": weather, 
        "status": status, 
        "date": d_date, 
        "time": d_time,
        "units": units,
        "pressure_labels": pressure_labels,
        "wind_label": wind_label, 
        "temp_pct": temp_pct, 
        "pressure_angle": pressure_angle,
        "w_units": w_units,
        "converted": converted,
        "timezone": cfg.time_zone_name,
        "wu_base_url": cfg.wu_base_url,
        "table_rows": table_rows,
        "selected_date": day_local.isoformat(),
        "prev_day": prev_day,
        "next_day": next_day,
        "csv_url": csv_url
    })

# Download CSV for Selected Date
@app.get("/stations/weather/csv/{station_id}")
def stations_csv(station_id: str, session: db.SessionDep, units: str = "imperial", selected_date: str | None = None):
    # Get Data
    local_tz = pytz.timezone(cfg.timezone)

    if not selected_date or selected_date == "None":
        day_local = datetime.now(local_tz).date()
    else:
        try:
            day_local = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            day_local = datetime.now(local_tz).date()

    day_start_local = local_tz.localize(datetime.combine(day_local, time.min))
    day_end_local = local_tz.localize(datetime.combine(day_local, time.max))

    day_start_utc = day_start_local.astimezone(pytz.UTC)
    day_end_utc = day_end_local.astimezone(pytz.UTC)

    # Set Units:
    if units == "metric":
        labels = {
            "temp": "°C",
            "dewpoint": "°C",
            "humidity": "%",
            "pressure": "hPa",
            "wind_speed": "knots",
            "wind_gust": "knots",
            "wind_dir": "°",
            "precip_rate": "mm/hr",
            "precip_accum": "mm",
            "uv": "index",
            "solar": "watts/m²"
        }

    else:
        labels = {
            "temp": "°F",
            "dewpoint": "°F",
            "humidity": "%",
            "pressure": "inHg",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "wind_dir": "°",
            "precip_rate": "in/hr",
            "precip_accum": "in",
            "uv": "index",
            "solar": "watts/m²"
        }

    fields = [
        "temp",
        "dewpoint",
        "humidity",
        "pressure",
        "wind_speed",
        "wind_gust",
        "wind_dir",
        "precip_rate",
        "precip_accum",
        "uv",
        "solar",
    ]

    # Get the history
    history = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_id, m.WeatherHistory.observed_at >= day_start_utc, m.WeatherHistory.observed_at <= day_end_utc).order_by(m.WeatherHistory.observed_at)).all()

    if not history:
        raise HTTPException(status_code=404, detail="No Weather History Found")

    # Convert
    def convert_row_value(var, value):
        if value is None:
            return None

        if units == "metric":
            if var == "pressure":
                return cv.inhg_to_hpa(value)
            if var in ["precip_rate", "precip_accum"]:
                return cv.in_to_mm(value)
            return value

        if var in ["temp", "dewpoint"]:
            return cv.c_to_f(value)
        if var in ["wind_speed", "wind_gust"]:
            return cv.knots_to_mph(value)
        return value
    
    # Write CSV
    output = io.StringIO()
    fieldnames = ["station_id", f"observed_at_{cfg.time_zone_name}"] + fields
    writer = csv.DictWriter(output, fieldnames=fieldnames)

    writer.writeheader()

    # Print units
    unit_row = {
        "station_id": station_id,
        f"observed_at_{cfg.time_zone_name}": "units",
    }

    for var in fields:
        unit_row[var] = labels[var]
    writer.writerow(unit_row)

    wrote_rows = False

    for row in history:
        # Get time and convert to timezone
        observed_at = row.observed_at
        if observed_at is None:
            continue

        if observed_at.tzinfo is None:
            observed_at = pytz.UTC.localize(observed_at)

        local_time = observed_at.astimezone(local_tz)

        csv_row = {
            "station_id": station_id,
            f"observed_at_{cfg.time_zone_name}": local_time.isoformat()
        }

        has_value = False

        for var in fields:
            value = getattr(row, var, None)
            value = convert_row_value(var, value)
            csv_row[var] = value
            if value is not None:
                has_value = True

        if has_value:
            writer.writerow(csv_row)
            wrote_rows = True

    if not wrote_rows:
        raise HTTPException(status_code=404, detail="No Explortable Data Found")

    csv_data = output.getvalue()
    output.close()

    date_part = day_local.isoformat()
    filename = f"{station_id}_weather_data_{day_local.isoformat()}_{units}.csv"
    filename = filename.replace(" ", "_")

    # Download titles
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return Response(content=csv_data, media_type="text/csv", headers=headers)

#---Login---

# Gives direct token for docs login
@app.post("/token")
def login_for_access_token(session: db.SessionDep, form_data: OAuth2PasswordRequestForm = Depends()):
    # Open user using creds
    user = session.exec(select(m.User).where(m.User.username == form_data.username)).first()

    # If user is right give token if not 401
    if not user or not s.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = s.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Page for people
@app.get("/login", response_class=HTMLResponse)
def load_login(request: Request):
    return templates.TemplateResponse(request, "login.html", context={"request": request, "title": "Login", "active_page": "login"})

# From Response with creds.
@app.post("/login")
def login_page_submit(request: Request, session: db.SessionDep, form_data: OAuth2PasswordRequestForm = Depends()):
    # Open user with form creds
    user = session.exec(select(m.User).where(m.User.username == form_data.username)).first()

    # If not right, 401
    if not user or not s.verify_password(form_data.password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"request": request, "title": "Login", "active_page": "login", "error": "Invalid Credentials"}, status_code=401)

    # Give cookie 
    access_token = s.create_access_token(data={"sub": user.username}) 
    response = RedirectResponse(url="/my-stations", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True, path="/", samesite="lax")
    return response

# Log out
@app.get("/logout")
def logout():
    # Delete cookie
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(key="access_token", path="/", samesite="lax")
    return response

# Admin Settings
@app.get("/settings", response_class=HTMLResponse)
def website_settings(request: Request, session: db.SessionDep, required_user: Annotated[m.User, Depends(require_admin)], current_user: Annotated[m.User, Depends(get_current_user)], success: str | None = None, username: str | None = None, error: str | None = None, stations_user_id: int | None = None, access_station_id: str | None = None, read_stations: bool | None = None):
    # If blank user:
    if stations_user_id == "":
        stations_user_id = None
    elif stations_user_id is not None:
        stations_user_id = int(stations_user_id)

    # list of users
    users = read_users(session, offset=0, current_user=current_user)
    # List of station
    stations = session.exec(select(m.Station).order_by(m.Station.station_name)).all()
   
    # What permissions users have at a stations
    selected_access = None
    if stations_user_id is not None and access_station_id:
        selected_access = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == stations_user_id, m.UserAccess.station_id == access_station_id,)).first()

    login_error = ""
    # Errors
    if error == "user_exists":
        login_error = "User already exists"


    # Read Users Stations
    user_stations = []
    access_stations = []

    if stations_user_id is not None:
        rows = session.exec(select(m.UserAccess, m.Station).join(m.Station, m.UserAccess.station_id == m.Station.station_id).where(m.UserAccess.user_id == stations_user_id).order_by(m.Station.station_name)).all()

        user_stations = [
            {
                "station_id": station.station_id,
                "station_name": station.station_name,
                "can_view": access.can_view,
                "can_toggle_maintenance": access.can_toggle_maintenance,
            }
            for access, station in rows
        ]

        access_stations = [station for access, station in rows]

    return templates.TemplateResponse(request, "w_settings.html", {
        "request": request,
        "title": "Settings",
        "active_page": "settings",
        "users": users,
        "stations": stations,
        "access_stations": access_stations,
        "stations_user_id": stations_user_id,
        "access_station_id": access_station_id,
        "selected_access": selected_access,
        "success": success,
        "username": username,
        "error": error,
        "login_error": login_error,
        "user_stations": user_stations,
        "stations_user_id": stations_user_id,
        "read_stations": read_stations
    })

# Owner dashboard for the station:
@app.get("/stations/dashboard/{station_id}", response_class=HTMLResponse)
def owner_station(request: Request, session: db.SessionDep, station_id: str, required_user: Annotated[m.User, Depends(require_station_access)], current_user: Annotated[m.User, Depends(get_current_user)]):
    # Check units:
    units = request.query_params.get("units", "imperial")
    # Open DB tables
    status = session.exec(select(m.Status).where(m.Status.station_id == station_id)).first()
    weather = session.exec(select(m.Weather).where(m.Weather.station_id == station_id)).first()
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()

    if not station:
        raise HTTPException(status_code=404, detail="Station Not Found")

    date = None
    time = None
    wind_label = None

    s_date = None
    s_time = None
    lc_date = None
    lc_time = None
    fo_date = None
    fo_time = None
    temp = None
    dew_p = None
    wind_speed = None
    wind_gust = None
    pressure_angle = 180
    temp_pct = 0

    # If user can activate maintence:
    maintenance = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == current_user.id, m.UserAccess.can_view == True, m.UserAccess.can_toggle_maintenance == True, m.UserAccess.station_id == station_id)).first()
    maintenance = bool(maintenance)

    if current_user.role == "admin":
        maintenance = True

    converted = {
        "temp": None,
        "dew_p": None,
        "pressure": None,
        "precip_r": None,
        "precip_a": None,
        "wind_speed": None,
        "wind_gust": None,
    }

    # Time Expressions
    if weather is not None:
        d_date, d_time = get_date_and_time(weather.observed_at)

        # Wind dir label
        wind_label = degree_to_label(weather.wind_dir)

    if status is not None:
        s_date, s_time = get_date_and_time(status.time_of_status)
        lc_date, lc_time = get_date_and_time(status.last_connected)
        fo_date, fo_time = get_date_and_time(status.first_offline)

    stime = {
        "s_date": s_date,
        "s_time": s_time,
        "lc_date": lc_date,
        "lc_time": lc_time,
        "fo_date": fo_date,
        "fo_time": fo_time,
    }

    # Get success (from maintenance/public) querry
    success = request.query_params.get("success")


    # Imperial
    if units == "metric":
        
        # Temp Percent fill
        temp_pct = 0
        if weather and weather.temp is not None:
            temp_pct = ((weather.temp - cfg.m_temp_min) / (cfg.m_temp_max - cfg.m_temp_min)) * 100
            temp_pct = max(0, min(100, temp_pct)) 

        # Pressure dial
        pressure_angle = 180
        if weather and weather.pressure is not None:

            pressure = cv.inhg_to_hpa(weather.pressure)
            pressure_min = cv.inhg_to_hpa(cfg.pressure_min)
            pressure_mid = cv.inhg_to_hpa(cfg.pressure_mid)
            pressure_max = cv.inhg_to_hpa(cfg.pressure_max)


            pressure_angle_1 = ((pressure - pressure_min) / (pressure_max - pressure_min)) * (cfg.angle_max - cfg.angle_min) + cfg.angle_min
            pressure_angle = round(max(cfg.angle_min, min(cfg.angle_max, pressure_angle_1)), 2)
        
        # Precip
        precip_r = cv.in_to_mm(weather.precip_rate)
        precip_a = cv.in_to_mm(weather.precip_accum)


        pressure_labels = {
            "low": pressure_min,
            "mid": pressure_mid,
            "high": pressure_max
        }

        w_units = {
            "temp": "°C",
            "precip_r": "mm/hr",
            "precip_a": "mm",
            "wind": "knots",
            "pressure": "hPa"
        }

        converted = {
            "pressure": pressure,
            "precip_r": precip_r,
            "precip_a": precip_a,
            "temp": weather.temp,
            "dew_p": weather.dewpoint,
            "wind_speed": weather.wind_speed,
            "wind_gust": weather.wind_gust
        }

    else:

        # Thermometer percent fill
        temp = cv.c_to_f(weather.temp)
        dew_p = cv.c_to_f(weather.dewpoint)

        temp_pct = 0
        if weather and weather.temp is not None:
            temp_pct = ((temp - cfg.temp_min) / (cfg.temp_max - cfg.temp_min)) * 100
            temp_pct = max(0, min(100, temp_pct))

        
        # Pressure dial
        pressure_angle = 180
        if weather and weather.pressure is not None:
            pressure_angle_1 = ((weather.pressure - cfg.pressure_min) / (cfg.pressure_max - cfg.pressure_min)) * (cfg.angle_max - cfg.angle_min) + cfg.angle_min
            pressure_angle = round(max(cfg.angle_min, min(cfg.angle_max, pressure_angle_1)), 2)

        # Knots - mph
        wind_speed = cv.knots_to_mph(weather.wind_speed)
        wind_gust = cv.knots_to_mph(weather.wind_gust)

        pressure_labels = {
            "low": cfg.pressure_min,
            "mid": cfg.pressure_mid,
            "high": cfg.pressure_max,
        }

        w_units = {
            "temp": "°F",
            "precip_r": "in/hr",
            "precip_a": "in",
            "wind": "mph",
            "pressure": "inHg",
        }

        converted = {
            "temp": temp,
            "dew_p": dew_p,
            "pressure": weather.pressure,
            "precip_r": weather.precip_rate,
            "precip_a": weather.precip_accum,
            "wind_speed": wind_speed,
            "wind_gust": wind_gust,
        }

    return templates.TemplateResponse(request, "owner_dash.html", context={
        "request": request, 
        "title": f"{station.station_name} Station Dashboard", 
        "active_page": "my_stations", 
        "station": station, 
        "weather": weather, 
        "status": status,
        "station_id": station_id, 
        "date": d_date, 
        "time": d_time,
        "units": units,
        "pressure_labels": pressure_labels,
        "wind_label": wind_label,
        "stime": stime,
        "temp_pct": temp_pct, 
        "pressure_angle": pressure_angle,
        "w_units": w_units,
        "converted": converted,
        "maintenance": maintenance,
        "timezone": cfg.time_zone_name,
        "success": success,
        "wu_base_url": cfg.wu_base_url,
    })

#---Graphing---

# Graph page
@app.get("/graph", response_class=HTMLResponse)
def graph_page(request: Request, session: db.SessionDep, station_id: str="", variables: Annotated[list[str] | None, Query()] = None, units: str="imperial", title: str="", range_mode: str = "relative", range_value: int | None = None, range_unit: str | None = None, start_date: str | None = None, end_date: str | None = None):
    # Open stations
    stations = session.exec(select(m.Station).where(m.Station.is_public == True).order_by(m.Station.station_name)).all()

    # Variables
    selected_variables = variables or []

    graph_url = None
    csv_url = None

    # Add parms
    if station_id and selected_variables:
        params = []

        for var in selected_variables:
            params.append(f"variables={var}") # All variables
        params.append(f"units={units}")
        params.append(f"title={title}")
        params.append(f"fig_width=10")
        params.append(f"fig_height=5")
        params.append(f"range_mode={range_mode}")

        if range_mode == "relative":
            params.append(f"range_value={range_value}")
            params.append(f"range_unit={range_unit}")

        elif range_mode == "dates":
            if start_date:
                params.append(f"start_date={start_date}")

            if end_date:
                params.append(f"end_date={end_date}")
        
        query_string = "&".join(params)

        graph_url = f"/graph/weather/{station_id}?{query_string}"
        csv_url = f"/graph/weather/{station_id}/csv?{query_string}"

    return templates.TemplateResponse(request, "graph.html", context={"request": request, "title": "Graphing", "active_page": "graph", "selected_title": title, "selected_station": station_id, "selected_units": units, "selected_variables": selected_variables, "stations": stations, "selected_range_mode": range_mode, "selected_range_value": range_value, "selected_range_unit": range_unit, "selected_start_date": start_date, "selected_end_date": end_date, "graph_url": graph_url, "csv_url": csv_url})

# Graph data and return as memory
@app.get("/graph/weather/{station_id}")
def graph_variables(station_id: str, variables: Annotated[list[str], Query()], session: db.SessionDep, units: str="imperial", title: str="", range_mode: str = "relative", range_value: int | None = 24, range_unit: str | None = "hours", start_date: str | None = None, end_date: str | None = None, fig_width: int=6, fig_height: int=3):

    # Relative Mode
    if range_mode == "relative":
        if not range_value or not range_unit:
            raise HTTPException(status_code=400, detail="Range Value must at least be 1")


        allowed_units = {"hours", "days", "weeks", "months", "years"}
        if range_unit not in allowed_units:
            raise HTTPException(status_code=400, detail="Must be valid unit")

        now = datetime.now(pytz.UTC)

        # Graph by last 24 hrs
        if range_unit == "hours":
            cutoff_start = now - timedelta(hours=range_value)

        elif range_unit == "days":
            cutoff_start = now - timedelta(days=range_value)

        elif range_unit == "weeks":
            cutoff_start = now - timedelta(weeks=range_value)

        elif range_unit == "months":
            cutoff_start = now - timedelta(days = 30 * range_value)

        elif range_unit == "years":
            cutoff_start = now - timedelta(days = 365 * range_value)

        cutoff_end = now

    # Date Mode
    elif range_mode == "dates":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Start date and end date are required")

        start_naive = datetime.strptime(start_date, "%Y-%m-%d")
        end_naive = datetime.strptime(end_date, "%Y-%m-%d")

        if end_naive < start_naive:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        # Turn request into UTC to query db
        eastern = pytz.timezone(cfg.timezone)
        cutoff_start = eastern.localize(start_naive).astimezone(pytz.UTC)
        cutoff_end = eastern.localize(end_naive.replace(hour=23, minute=59, second=59)).astimezone(pytz.UTC)

    else:
        raise HTTPException(status_code=400, detail="Invalid Range Mode")
    

    # Get data
    weather = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_id, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()

    if not weather:
        raise HTTPException(status_code=404, detail="No Weather History Found")

    # Define allowed variables
    allowed = {
        "temp": "Air Temperature",
        "dewpoint": "Dew Point",
        "humidity": "Humidity",
        "pressure": "Pressure",
        "wind_speed": "Wind Speed",
        "wind_gust": "Wind Gust",
        "wind_dir": "Wind Direction",
        "precip_rate": "Precipitation Rate",
        "precip_accum": "Precipitation Accumulation",
        "uv": "UV Index",
        "solar": "Solar Radiation"
    }

    for var in variables:
        if var not in allowed:
            raise HTTPException(status_code=400, detail="Invalid Variable")

    # Units
    if units == "metric":
        labels = {
            "temp": "°C",
            "dewpoint": "°C",
            "humidity": "%",
            "pressure": "hPa",
            "wind_speed": "knots",
            "wind_gust": "knots",
            "wind_dir": "°",
            "precip_rate": "mm/hr",
            "precip_accum": "mm",
            "uv": "",
            "solar": "watts/m²"
        }

    else:
        labels = {
            "temp": "°F",
            "dewpoint": "°F",
            "humidity": "%",
            "pressure": "inHg",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "wind_dir": "°",
            "precip_rate": "in/hr",
            "precip_accum": "in",
            "uv": "",
            "solar": "watts/m²"
        }

     # Define Variable Groups
    unit_groups = {
        "temp": "temperature",
        "dewpoint": "temperature",
        "humidity": "humidity",
        "pressure": "pressure",
        "wind_speed": "wind",
        "wind_gust": "wind",
        "wind_dir": "direction",
        "precip_rate": "precipitation",
        "precip_accum": "precipitation",
        "uv": "uv",
        "solar": "solar"
    }

    # Make Y Label based on units
    selected_units = {labels[var] for var in variables}
    selected_groups = {unit_groups[var] for var in variables}

    if len(selected_units) == 1:
        y_axis_label = next(iter(selected_units)) or "Value"
    elif len(selected_groups) == 1:
        family_labels = {
        "temperature": f"Temperature ({labels[variables[0]]})",
        "wind": f"Wind ({labels[variables[0]]})",
        "humidity": "%",
        "pressure": labels[variables[0]],
        "direction": "Direction (°)",
        "precip_rate": labels[variables[0]],
        "precip_accum": labels[variables[0]],
        "uv": "UV Index",
        "solar": "Solar Radiation (watts/m²)",
    }
        y_axis_label = family_labels.get(next(iter(selected_groups)), "Value")
    else:
        y_axis_label = "(mixed units)"

    series = {}

    # Variables
    for var in variables: # for each variables append converted data to series
        x = []
        y = []

        # Append to values
        for row in weather:
            value = getattr(row, var, None)
            if value is None or row.observed_at is None:
                continue

            x.append(m.to_eastern(row.observed_at))

            # Convert to metric
            if units == "metric":
                if var in ["pressure"]:
                    value = cv.inhg_to_hpa(value)
                elif var in ["precip_rate", "precip_accum"]:
                    value = cv.in_to_mm(value)
                

            # Convert to Imperial
            else:
                if var in ["temp", "dewpoint"]:
                    value = cv.c_to_f(value)
                elif var in ["wind_speed", "wind_gust"]:
                    value = cv.knots_to_mph(value)
                
                
            y.append(value)

        if x and y:
            series[var] = {"x": x, "y": y} 

    if not series:
        raise HTTPException(status_code=404, detail="No Plottable Data Found")

    # Size and Color
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    colors = ["#005baa", "#d1295b", "#2a9d8f", "#8d5fd3", "#f4a26a", "#FE05E9"]

    # Mode title
    if range_mode == "relative":
        range_title = (f"(Past {range_value} {range_unit})")

        if range_value == 1:
            range_title = f"Past {range_unit[:-1]}"
    else:
        range_title = (f"{start_date} to {end_date}")

    # Graph
    for i, var in enumerate(series):
        ax.plot(series[var]["x"], series[var]["y"], marker="o", linewidth=2, markersize=3, color=colors[i % len(colors)], label=f"{allowed[var]} ({labels[var]})" if labels[var] else allowed[var])

    # Titles
    ax.set_title(f"{station_id} {title} {range_title}", fontsize=16)
    ax.set_xlabel(f"Time ({cfg.time_zone_name})", fontsize=13)
    ax.set_ylabel(y_axis_label, fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.margins(x=0.05, y=0.10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H"))
    fig.autofmt_xdate(rotation=30)
    plt.tight_layout()
    plt.subplots_adjust(top=0.80)
    
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    # Download link
    filename = f"{station_id}_{title or 'graph'}_{range_title}.png"
    safe_name = filename.replace(" ", "_")

    headers = {"Content-Disposition": f'attachment; filename="{safe_name}"'}


    return Response(content=buf.getvalue(), media_type="image/png", headers=headers)

# CSV Download
@app.get("/graph/weather/{station_id}/csv")
def export_graph_csv(station_id: str, variables: Annotated[list[str], Query()], session: db.SessionDep, units: str="imperial", title: str="", range_mode: str = "relative", range_value: int | None = None, range_unit: str | None = None, start_date: str | None = None, end_date: str | None = None):
    # Relative Mode
    if range_mode == "relative":
        if not range_value or not range_unit:
            raise HTTPException(status_code=400, detail="Range Value must at least be 1")


        allowed_units = {"hours", "days", "weeks", "months", "years"}
        if range_unit not in allowed_units:
            raise HTTPException(status_code=400, detail="Must be valid unit")

        now = datetime.now(pytz.UTC)

        # Graph by last 24 hrs
        if range_unit == "hours":
            cutoff_start = now - timedelta(hours=range_value)

        elif range_unit == "days":
            cutoff_start = now - timedelta(days=range_value)

        elif range_unit == "weeks":
            cutoff_start = now - timedelta(weeks=range_value)

        elif range_unit == "months":
            cutoff_start = now - timedelta(days = 30 * range_value)

        elif range_unit == "years":
            cutoff_start = now - timedelta(days = 365 * range_value)

        cutoff_end = now

    # Date Mode
    elif range_mode == "dates":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Start date and end date are required")

        start_naive = datetime.strptime(start_date, "%Y-%m-%d")
        end_naive = datetime.strptime(end_date, "%Y-%m-%d")

        if end_naive < start_naive:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        # Turn request into UTC to query db
        eastern = pytz.timezone(cfg.timezone)
        cutoff_start = eastern.localize(start_naive).astimezone(pytz.UTC)
        cutoff_end = eastern.localize(end_naive.replace(hour=23, minute=59, second=59)).astimezone(pytz.UTC)

    else:
        raise HTTPException(status_code=400, detail="Invalid Range Mode")

    # Get data
    weather = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_id, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()
    

    if not weather:
        raise HTTPException(status_code=404, detail="No Weather History Found")

    allowed = {
        "temp": "Air Temperature",
        "dewpoint": "Dew Point",
        "humidity": "Humidity",
        "pressure": "Pressure",
        "wind_speed": "Wind Speed",
        "wind_gust": "Wind Gust",
        "wind_dir": "Wind Direction",
        "precip_rate": "Precipitation Rate",
        "precip_accum": "Precipitation Accumulation",
        "uv": "UV Index",
        "solar": "Solar Radiation"
    }

    # Units
    if units == "metric":
        labels = {
            "temp": "°C",
            "dewpoint": "°C",
            "humidity": "%",
            "pressure": "hPa",
            "wind_speed": "knots",
            "wind_gust": "knots",
            "wind_dir": "°",
            "precip_rate": "mm/hr",
            "precip_accum": "mm",
            "uv": "",
            "solar": "watts/m²"
        }

    else:
        labels = {
            "temp": "°F",
            "dewpoint": "°F",
            "humidity": "%",
            "pressure": "inHg",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "wind_dir": "°",
            "precip_rate": "in/hr",
            "precip_accum": "in",
            "uv": "",
            "solar": "watts/m²"
        }

    for var in variables:
        if var not in allowed:
            raise HTTPException(status_code=400, detail="Invalid Variable")

    def convert_value(var, value):
        if value is None:
            return None

        # Convert to metric
        if units == "metric":
            if var == "pressure":
                return cv.inhg_to_hpa(value)
            elif var in ["precip_rate", "precip_accum"]:
                return cv.in_to_mm(value)
            return value

        # convert to imperial
        else:
            if var in ["temp", "dewpoint"]:
                return cv.c_to_f(value)
            elif var in ["wind_speed", "wind_gust"]:
                return cv.knots_to_mph(value)
            return value

    output = io.StringIO()

    fieldnames = ["station_id", f"observed_at_{cfg.time_zone_name}"] + variables
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    # Print units
    unit_row = {
        "station_id": station_id,
        f"observed_at_{cfg.time_zone_name}": "units",
    }

    for var in variables:
        unit_row[var] = labels[var]
    writer.writerow(unit_row)

    wrote_rows = False

    for row in weather:
        if row.observed_at is None:
            continue

        csv_row = {
            "station_id": station_id,
            f"observed_at_{cfg.time_zone_name}": m.to_eastern(row.observed_at).isoformat(),
        }

        has_value = False

        for var in variables:
            value = getattr(row, var, None)
            value = convert_value(var, value)
            csv_row[var] = value
            if value is not None:
                has_value = True

        if has_value:
            writer.writerow(csv_row, )
            wrote_rows = True

    if not wrote_rows:
        raise HTTPException(status_code=404, detail="No Exportable Data Found")

    csv_data = output.getvalue()
    output.close()

    safe_title = title.strip().replace(" ", "_") if title.strip() else "weather_graph"
    filename = f"{station_id}_{safe_title}_past_{range_value}_{range_unit}_{units}.csv"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return Response(content=csv_data, media_type="text/csv", headers=headers)

#---Analysis---

# Calculations
def build_analysis_stats(session, station_id: str, variable: str, units: str = "imperial", range_mode: str = "relative", range_value: int | None = None, range_unit: str | None = None, start_date: str | None = None, end_date: str | None = None):
    allowed = {
        "temp": "Air Temperature",
        "dewpoint": "Dew Point",
        "humidity": "Humidity",
        "pressure": "Pressure",
        "wind_speed": "Wind Speed",
        "wind_gust": "Wind Gust",
        "wind_dir": "Wind Direction",
        "precip_rate": "Precipitation Rate",
        "precip_accum": "Precipitation Accumulation",
        "uv": "UV Index",
        "solar": "Solar Radiation"
    }

    # Check if valid
    if variable not in allowed:
        raise HTTPException(status_code=400, detail="Invalid Variable")

    if units == "metric":
        labels = {
            "temp": "°C",
            "dewpoint": "°C",
            "humidity": "%",
            "pressure": "hPa",
            "wind_speed": "knots",
            "wind_gust": "knots",
            "wind_dir": "°",
            "precip_rate": "mm/hr",
            "precip_accum": "mm",
            "uv": "",
            "solar": "watts/m²"
        }

    else:
        labels = {
          "temp": "°F",
            "dewpoint": "°F",
            "humidity": "%",
            "pressure": "inHg",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "wind_dir": "°",
            "precip_rate": "in/hr",
            "precip_accum": "in",
            "uv": "",
            "solar": "watts/m²",  
        }

    if range_mode == "relative":
        # Defaults
        range_value = range_value or 24
        range_unit = range_unit or "hours"

        allowed_units = {"hours", "days", "weeks", "months", "years"}
        if range_unit not in allowed_units:
            raise HTTPException(status_code=400, detail="Not Valid Relative Unit")

        now = datetime.now(pytz.UTC)

        # Set cutoffs
        if range_unit == "hours":
            cutoff_start = now - timedelta(hours=range_value)

        elif range_unit == "days":
            cutoff_start = now - timedelta(days=range_value)

        elif range_unit == "weeks":
            cutoff_start = now - timedelta(weeks=range_value)

        elif range_unit == "months":
            cutoff_start = now - timedelta(days = 30 * range_value)

        else:
            cutoff_start = now - timedelta(days = 365 * range_value)

        cutoff_end = now

        # Title
        range_title = f"Past {range_value} {range_unit}"
        if range_value == 1:
            range_title = f"Past {range_value} {range_unit[:-1]}"

    elif range_mode == "dates":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Start and End Date Required")

        start_naive = datetime.strptime(start_date, "%Y-%m-%d")
        end_naive = datetime.strptime(end_date, "%Y-%m-%d")

        if end_naive < start_naive:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        # Turn user inputs to UTC
        eastern = pytz.timezone(cfg.timezone)
        cutoff_start = eastern.localize(start_naive).astimezone(pytz.UTC)
        cutoff_end = eastern.localize(end_naive.replace(hour=23, minute=59, second=59)).astimezone(pytz.UTC)

        range_title = f"{start_date} to {end_date}"

    else:
        raise HTTPException(status_code=400, detail="Invalid Range Mode")

    # Get history
    weather = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_id, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()

    x = []
    y = []

    # Get X/Y
    for row in weather:
        value = getattr(row, variable, None)
        if value is None or row.observed_at is None:
            continue

        observed_local = m.to_eastern(row.observed_at)

        # Convert
        if units == "metric":
            if variable == "pressure":
                value = cv.inhg_to_hpa(value)
            elif variable in ["precip_rate", "precip_accum"]:
                value = cv.in_to_mm(value)

        else:
            if variable in ["temp", "dewpoint"]:
                value = cv.c_to_f(value)
            elif variable in ["wind_speed", "wind_gust"]:
                value = cv.knots_to_mph(value)

        x.append(observed_local)
        y.append(value)

    if not y:
        raise HTTPException(status_code=404, detail="No Data to Analyze")

    # Stats Calc
    latest_value = y[-1]

    latest = x[-1]
    latest_date, latest_time = get_date_and_time(latest)
    latest_dt = {
        "date": latest_date,
        "time": latest_time
    }

    min_value = min(y)
    max_value = max(y)
    mean_value = statistics.mean(y)
    median_value = statistics.median(y)
    value_range = max_value - min_value
    n_value = len(y)

    min_index = y.index(min_value)
    max_index = y.index(max_value)

    # Min/Max Time
    min_raw = x[min_index]
    min_date, min_time = get_date_and_time(min_raw)
    
    max_raw = x[max_index]
    max_date, max_time = get_date_and_time(max_raw)

    min_dt = {
        "date": min_date,
        "time": min_time
    }

    max_dt = {
        "date": max_date,
        "time": max_time
    }

    # Trends
    if len(y) >= 2:
        if y[-1] > y[0]:
            trend_direction = "Rising"
        elif y[-1] < y[0]:
            trend_direction = "Falling"
        else:
            trend_direction = "Steady"
    else:
        trend_direction = "Insufficient Data"

    # Start/End Converage
    s_date, s_time = get_date_and_time(x[0])
    e_date, e_time = get_date_and_time(x[-1])

    start = {
        "date": s_date,
        "time": s_time
    }

    start_raw = x[0]

    end = {
        "date": e_date,
        "time": e_time, 
    }

    end_raw = x[-1]

    return {
        "allowed_variables": allowed, "variable_label": allowed[variable], "unit_label": labels[variable], "range_title": range_title, "timestamps": x, "values": y, "latest_value": round(latest_value, 2), "latest_time": latest_dt, "latest_dt": latest.isoformat(),
        "min_value": round(min_value, 2), "min_time": min_dt, "min_dt": min_raw.isoformat(), "max_value": max_value, "max_time": max_dt, "max_dt": max_raw.isoformat(), "mean_value": round(mean_value, 2), "median_value": median_value, "value_range": round(value_range, 2), "n_value": n_value, "start_coverage": start, "end_coverage": end, "start_dt": x[0], "end_dt": x[-1], "trend_direction": trend_direction,
    }

# HTML Page
@app.get("/graph/analysis", response_class=HTMLResponse)
def analysis_page(request: Request, session: db.SessionDep, station_id: str = "", variable: str = "", units: str = "imperial", range_mode: str = "relative", range_value: int | None = None, range_unit: str | None = None, start_date: str | None = None, end_date: str | None = None):

    #Get Stations
    stations = session.exec(select(m.Station).where(m.Station.is_public == True).order_by(m.Station.station_name)).all()

    allowed = {
        "temp": "Air Temperature",
        "dewpoint": "Dew Point",
        "humidity": "Humidity",
        "pressure": "Pressure",
        "wind_speed": "Wind Speed",
        "wind_gust": "Wind Gust",
        "wind_dir": "Wind Direction",
        "precip_rate": "Precipitation Rate",
        "precip_accum": "Precipitation Accumulation",
        "uv": "UV Index",
        "solar": "Solar Radiation"
    }

    # Urls
    stats = None
    csv_url = None

    if station_id and variable:
        stats = build_analysis_stats(session=session, station_id=station_id, variable=variable, units=units, range_mode=range_mode, range_value=range_value, range_unit=range_unit, start_date=start_date, end_date=end_date)

        # Add params
        params = []

        params.append(f"variable={variable}")
        params.append(f"units={units}")
        params.append(f"range_mode={range_mode}")

        if range_mode == "relative":
            params.append(f"range_value={range_value}")
            params.append(f"range_unit={range_unit}")

        elif range_mode == "dates":
            if start_date:
                params.append(f"start_date={start_date}")
            if end_date:
                params.append(f"end_date={end_date}")

        query_string = "&".join(params)
        csv_url = f"/analyze/weather/{station_id}/csv?{query_string}"

    context = {
        "request": request,
        "title": "Analysis",
        "active_page": "analysis",
        "stations": stations,
        "allowed_variables": allowed,
        "selected_station": station_id,
        "selected_variable": variable,
        "selected_units": units,
        "selected_range_mode": range_mode,
        "selected_range_value": range_value,
        "selected_range_unit": range_unit,
        "selected_start_date": start_date,
        "selected_end_date": end_date,
        "csv_url": csv_url,
        "stats": stats,
        "timezone": cfg.time_zone_name
    }

    if stats:
        context.update(stats)

    return templates.TemplateResponse(request, "analysis.html", context=context)

# Download Analysis
@app.get("/analyze/weather/{station_id}/csv")
def analysis_csv(station_id: str, variable: str, session: db.SessionDep, units: str = "imperial", range_mode: str = "relative", range_value: int | None = None, range_unit: str | None = None, start_date: str | None = None, end_date: str | None = None):
    # Get Data
    stats = build_analysis_stats(session=session, station_id=station_id, variable=variable, units=units, range_mode=range_mode, range_value=range_value, range_unit=range_unit, start_date=start_date, end_date=end_date)

    output = io.StringIO()
    writer = csv.writer(output)

    # Write csv Heaers

    # Stats top
    writer.writerow([
        "station_id:", "variable:", "unit:", "observed_at:", "value:", "|", "'===", "STATS:", "'===", "|"
    ])

    writer.writerow([
       "", "", "", "", "", "|", "'===", "'===", "'===", "|"
    ])

    # Row 1 - Names
    writer.writerow([
        "", "", "", "", "", "|", "latest_value:", "minimum:", "maximum:", "|"  
    ])

    # Row 2 - Variables
    writer.writerow([
        "", "", "", "", "", "|", stats["latest_value"], stats["min_value"], stats["max_value"], "|"
    ]) 

    # Row 3 - Variable times
    writer.writerow([
        "", "", "", "", "", "|", stats["latest_dt"], stats["min_dt"], stats["max_dt"], "|"
    ])

    # Row 4 - Names
    writer.writerow([
        "", "", "", "", "", "|", "mean:", "median:", "range:", "|"
    ])

    # Row 5 - variables
    writer.writerow([
        "", "", "", "", "", "|", stats["mean_value"], stats["median_value"], stats["value_range"], "|"
    ])

    # Row 6 - Names
    writer.writerow([
        "", "", "", "", "", "|", "n value:", "trend:", "", "|"
    ])

    # Row 7 - Variables
    writer.writerow([
        "", "", "", "", "", "|", stats["n_value"], stats["trend_direction"], "", "|"
    ])

    # Row 8 - Names
    writer.writerow([
        "", "", "", "", "", "|", "coverage start:", "coverage end:", "", "|", 
    ])

    # Row 9 - Variables
    writer.writerow([
        "", "", "", "", "", "|", stats["start_coverage"], stats["end_coverage"], "", "|"
    ])

    # Row 10 - End Chart
    writer.writerow([
        "", "", "", "", "", "|", "'===", "'===", "'===", "|"
    ])
    writer.writerow([""])

    # Write data to csv
    for ts, value in zip(stats["timestamps"], stats["values"]):
        writer.writerow([
            station_id, stats["variable_label"], stats["unit_label"], ts.isoformat(), value
            ])

    csv_data = output.getvalue()
    output.close()

    # Create titles
    if range_mode == "relative":
        filename = f"{station_id}_{variable}_analysis_{range_value or 24}_{range_unit or 'hours'}.csv"

    else:
        filename = f"{station_id}_{variable}_analysis_{start_date}_to_{end_date}.csv"

    safe_name = filename.replace(" ", "_")

    headers = {"Content-Disposition": f'attachment; filename="{safe_name}"'}

    return Response(content=csv_data, media_type="text/csv", headers=headers)

#---TESTS---

# HTML Page
@app.get("/graph/test", response_class=HTMLResponse)
def load_tests(request: Request, session: db.SessionDep, station_id: str = "", variable: str = "", units: str = "imperial", range_mode: str = "relative", range_value: int | None = None, range_unit: str = None, start_date: str | None = None, end_date: str | None = None, test: str | None = None, x_variable: str | None = None, y_variable: str | None = None, title: str | None = None, station_id_a: str | None = None, station_id_b: str | None = None, station_id_c: str | None = None):

    # Get stations for list
    stations = session.exec(select(m.Station).where(m.Station.is_public == True).order_by(m.Station.station_name)).all()
    stations_map = {station.station_id : station.station_name for station in stations}

    allowed = {
        "temp": "Air Temperature",
        "dewpoint": "Dew Point",
        "humidity": "Humidity",
        "pressure": "Pressure",
        "wind_speed": "Wind Speed",
        "wind_gust": "Wind Gust",
        "wind_dir": "Wind Direction",
        "precip_rate": "Precipitation Rate",
        "precip_accum": "Precipitation Accumulation",
        "uv": "UV Index",
        "solar": "Solar Radiation"
    }

    # Urls
    t_test = None
    anova = None
    graph_url = None
    csv_url = None

    params = []

    # Add Params and create urls
    if test == "linear_regression" and station_id and x_variable and y_variable:
        params = [
            f"test={test}",
            f"station_id={station_id}",
            f"x_variable={x_variable}",
            f"y_variable={y_variable}",
            f"units={units}",
            f"title={title or ''}",
            f"range_mode={range_mode}",
        ]

        if range_mode == "relative":
            params.append(f"range_value={range_value or 24}")
            params.append(f"range_unit={range_unit or 'hours'}")
        else:
            if start_date:
                params.append(f"start_date={start_date}")
            if end_date:
                params.append(f"end_date={end_date}")

        csv_url = f"/test/weather/csv?{'&'.join(params)}"
        graph_url = f"/graph/lr/weather/{station_id}?{'&'.join(params)}"

    elif test == "t_test" and variable and station_id_a and station_id_b:

        t_test = run_t_test(session, units=units, range_mode=range_mode, range_value=range_value, range_unit=range_unit, start_date=start_date, end_date=end_date, station_a=station_id_a, station_b=station_id_b, variable=variable)
        t_test["variable_label"] = allowed.get(variable, variable)
        t_test["station_a_name"] = stations_map.get(station_id_a, station_id_a)
        t_test["station_b_name"] = stations_map.get(station_id_b, station_id_b)
    
        params = [
            f"test={test}",
            f"variable={variable}",
            f"station_id_a={station_id_a}",
            f"station_id_b={station_id_b}",
            f"units={units}",
            f"range_mode={range_mode}",
        ]

        if range_mode == "relative":
            params.append(f"range_value={range_value or 24}")
            params.append(f"range_unit={range_unit or 'hours'}")
        else:
            if start_date:
                params.append(f"start_date={start_date}")
            if end_date:
                params.append(f"end_date={end_date}")

        csv_url = f"/test/weather/csv?{'&'.join(params)}"

    elif test == "anova" and variable and station_id_a and station_id_b and station_id_c:

        anova = run_anova(session, units=units, range_mode=range_mode, range_value=range_value, range_unit=range_unit, start_date=start_date, end_date=end_date, station_a=station_id_a, station_b=station_id_b, station_c=station_id_c, variable=variable)
        anova["variable_label"] = allowed.get(variable, variable)
        anova["station_a_name"] = stations_map.get(station_id_a, station_id_a)
        anova["station_b_name"] = stations_map.get(station_id_b, station_id_b)
        anova["station_c_name"] = stations_map.get(station_id_c, station_id_c)

        params = [
            f"test={test}",
            f"variable={variable}",
            f"station_id_a={station_id_a}",
            f"station_id_b={station_id_b}",
            f"station_id_c={station_id_c}",
            f"units={units}",
            f"range_mode={range_mode}",
        ]

        if range_mode == "relative":
            params.append(f"range_value={range_value or 24}")
            params.append(f"range_unit={range_unit or 'hours'}")
        else:
            if start_date:
                params.append(f"start_date={start_date}")
            if end_date:
                params.append(f"end_date={end_date}")

        csv_url = f"/test/weather/csv?{'&'.join(params)}"

    context = {
        "request": request,
        "title": "Tests",
        "active_page": "test",
        "stations": stations,
        "allowed_variables": allowed,
        "selected_station": station_id,
        "selected_station_a": station_id_a,
        "selected_station_b": station_id_b,
        "selected_station_c": station_id_c,
        "selected_variable": variable,
        "selected_x_variable": x_variable,
        "selected_y_variable": y_variable,
        "selected_units": units,
        "selected_title": title,
        "selected_range_mode": range_mode,
        "selected_range_value": range_value,
        "selected_range_unit": range_unit,
        "selected_start_date": start_date,
        "selected_end_date": end_date,
        "selected_test": test,
        "csv_url": csv_url,
        "graph_url": graph_url,
        "anova": anova,
        "t_test": t_test,
        "timezone": cfg.time_zone_name
    }

    return templates.TemplateResponse(request, "testing.html", context=context)

@app.get("/graph/lr/weather/{station_id}")
def linear_regression(session: db.SessionDep, station_id: str, x_variable: str, y_variable: str, units: str="imperial", title: str="", range_mode: str = "relative", range_value: int | None = 24, range_unit: str | None = "hours", start_date: str | None = None, end_date: str | None = None, fig_width: int=6, fig_height: int=3):
    # Relative Mode
    if range_mode == "relative":
        if not range_value or not range_unit:
            raise HTTPException(status_code=400, detail="Range Value must at least be 1")


        allowed_units = {"hours", "days", "weeks", "months", "years"}
        if range_unit not in allowed_units:
            raise HTTPException(status_code=400, detail="Must be valid unit")

        now = datetime.now(pytz.UTC)

        # Graph by last 24 hrs
        if range_unit == "hours":
            cutoff_start = now - timedelta(hours=range_value)

        elif range_unit == "days":
            cutoff_start = now - timedelta(days=range_value)

        elif range_unit == "weeks":
            cutoff_start = now - timedelta(weeks=range_value)

        elif range_unit == "months":
            cutoff_start = now - timedelta(days = 30 * range_value)

        elif range_unit == "years":
            cutoff_start = now - timedelta(days = 365 * range_value)

        cutoff_end = now

    # Date Mode
    elif range_mode == "dates":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Start date and end date are required")

        start_naive = datetime.strptime(start_date, "%Y-%m-%d")
        end_naive = datetime.strptime(end_date, "%Y-%m-%d")

        if end_naive < start_naive:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        # Turn request into UTC to query db
        eastern = pytz.timezone(cfg.timezone)
        cutoff_start = eastern.localize(start_naive).astimezone(pytz.UTC)
        cutoff_end = eastern.localize(end_naive.replace(hour=23, minute=59, second=59)).astimezone(pytz.UTC)

    else:
        raise HTTPException(status_code=400, detail="Invalid Range Mode")
    

    # Get data
    weather = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_id, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()

    if not weather:
        raise HTTPException(status_code=404, detail="No Weather History Found")

    # Define allowed variables
    allowed = {
        "temp": "Air Temperature",
        "dewpoint": "Dew Point",
        "humidity": "Humidity",
        "pressure": "Pressure",
        "wind_speed": "Wind Speed",
        "wind_gust": "Wind Gust",
        "wind_dir": "Wind Direction",
        "precip_rate": "Precipitation Rate",
        "precip_accum": "Precipitation Accumulation",
        "uv": "UV Index",
        "solar": "Solar Radiation"
    }

    if y_variable not in allowed or x_variable not in allowed:
        raise HTTPException(status_code=400, detail="Invalid Variable")

    # Units
    if units == "metric":
        labels = {
            "temp": "°C",
            "dewpoint": "°C",
            "humidity": "%",
            "pressure": "hPa",
            "wind_speed": "knots",
            "wind_gust": "knots",
            "wind_dir": "°",
            "precip_rate": "mm/hr",
            "precip_accum": "mm",
            "uv": "",
            "solar": "watts/m²"
        }

    else:
        labels = {
            "temp": "°F",
            "dewpoint": "°F",
            "humidity": "%",
            "pressure": "inHg",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "wind_dir": "°",
            "precip_rate": "in/hr",
            "precip_accum": "in",
            "uv": "",
            "solar": "watts/m²"
            }

        # Define Variable Groups
    unit_groups = {
        "temp": "temperature",
        "dewpoint": "temperature",
        "humidity": "humidity",
        "pressure": "pressure",
        "wind_speed": "wind",
        "wind_gust": "wind",
        "wind_dir": "direction",
        "precip_rate": "precipitation",
        "precip_accum": "precipitation",
        "uv": "uv",
        "solar": "solar"
    }

    x = []
    y = []

    for row in weather:
        x_value = getattr(row, x_variable, None)
        if x_value is None or row.observed_at is None:
            continue

        # Convert to metric
        if units == "metric":
            if x_variable in ["pressure"]:
                x_value = cv.inhg_to_hpa(x_value)
            elif x_variable in ["precip_rate", "precip_accum"]:
                x_value = cv.in_to_mm(x_value)
            

        # Convert to Imperial
        else:
            if x_variable in ["temp", "dewpoint"]:
                x_value = cv.c_to_f(x_value)
            elif x_variable in ["wind_speed", "wind_gust"]:
                x_value = cv.knots_to_mph(x_value)

        y_value = getattr(row, y_variable, None)
        if y_value is None or row.observed_at is None:
            continue
        # Convert to metric
        if units == "metric":
            if y_variable in ["pressure"]:
                y_value = cv.inhg_to_hpa(y_value)
            elif y_variable in ["precip_rate", "precip_accum"]:
                y_value = cv.in_to_mm(y_value)
            

        # Convert to Imperial
        else:
            if y_variable in ["temp", "dewpoint"]:
                y_value = cv.c_to_f(y_value)
            elif y_variable in ["wind_speed", "wind_gust"]:
                y_value = cv.knots_to_mph(y_value)
            
        x.append(x_value)
        y.append(y_value)

    if not x or not y:
        raise HTTPException(status_code=404, detail="No Plottable Data Found")

    if len(x) < 2 or len(y) < 2:
        raise HTTPException(status_code=400, detail="Need at least two data points")

    # Size
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    # Mode title
    if range_mode == "relative":
        range_title = (f"(Past {range_value} {range_unit})")

        if range_value == 1:
            range_title = f"Past {range_unit[:-1]}"
    else:
        range_title = (f"{start_date} to {end_date}")

    # Calc LR
    slope, intercept = np.polyfit(x, y, 1)

    if len(set(y)) <= 1:
        r_squared = 0.0
    else:
        predicted_y = slope * np.array(x) + intercept
        ss_residual = np.sum((np.array(y) - predicted_y) ** 2)
        ss_total = np.sum((np.array(y) - np.mean(y)) ** 2)

        r_squared = 1 - (ss_residual / ss_total)

    # Scatter plot
    ax.scatter(x, y, color="#005baa", marker="o", linewidth=2, s=3, label=f"{allowed[y_variable]} ({labels[y_variable]}) on {allowed[x_variable]} ({labels[x_variable]})")

    # Slope Line
    x_line = np.linspace(min(x), max(x), 100)
    y_line = slope * x_line + intercept

    ax.plot(x_line, y_line, color="#d1295b", label=f"Fit: y = {slope:.2f}x + {intercept:.2f}, R² = {r_squared:.3f}")

    # Titles
    ax.set_title(f"{station_id} {title or 'Linear Regression'} {range_title}", fontsize=16)
    ax.set_xlabel(f"{allowed[x_variable]} ({labels[x_variable]})", fontsize=13)
    ax.set_ylabel(f"{allowed[y_variable]} ({labels[y_variable]})", fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.margins(x=0.05, y=0.10)
    plt.tight_layout()
    plt.subplots_adjust(top=0.80)

    # Download
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    # Download link
    filename = f"{station_id}_{title or 'graph'}_{range_title}.png"
    safe_name = filename.replace(" ", "_")

    headers = {"Content-Disposition": f'attachment; filename="{safe_name}"'}


    return Response(content=buf.getvalue(), media_type="image/png", headers=headers)

def run_t_test(session: db.SessionDep, units: str="imperial", range_mode: str = "relative", range_value: int | None = 24, range_unit: str | None = "hours", start_date: str | None = None, end_date: str | None = None, station_a: str | None = None, station_b: str | None = None, variable: str | None = None):
    # Relative Mode
    if range_mode == "relative":
        if not range_value or not range_unit:
            raise HTTPException(status_code=400, detail="Range Value must at least be 1")


        allowed_units = {"hours", "days", "weeks", "months", "years"}
        if range_unit not in allowed_units:
            raise HTTPException(status_code=400, detail="Must be valid unit")

        now = datetime.now(pytz.UTC)

        # Graph by last 24 hrs
        if range_unit == "hours":
            cutoff_start = now - timedelta(hours=range_value)

        elif range_unit == "days":
            cutoff_start = now - timedelta(days=range_value)

        elif range_unit == "weeks":
            cutoff_start = now - timedelta(weeks=range_value)

        elif range_unit == "months":
            cutoff_start = now - timedelta(days = 30 * range_value)

        elif range_unit == "years":
            cutoff_start = now - timedelta(days = 365 * range_value)

        cutoff_end = now

    # Date Mode
    elif range_mode == "dates":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Start date and end date are required")

        start_naive = datetime.strptime(start_date, "%Y-%m-%d")
        end_naive = datetime.strptime(end_date, "%Y-%m-%d")

        if end_naive < start_naive:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        # Turn request into UTC to query db
        eastern = pytz.timezone(cfg.timezone)
        cutoff_start = eastern.localize(start_naive).astimezone(pytz.UTC)
        cutoff_end = eastern.localize(end_naive.replace(hour=23, minute=59, second=59)).astimezone(pytz.UTC)

    else:
        raise HTTPException(status_code=400, detail="Invalid Range Mode")
    

    # Get data
    weather_a = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_a, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()
    weather_b = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_b, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()
    

    if not weather_a or not weather_b:
        raise HTTPException(status_code=404, detail="No Weather History Found")

    # Define allowed variables
    allowed = {
        "temp": "Air Temperature",
        "dewpoint": "Dew Point",
        "humidity": "Humidity",
        "pressure": "Pressure",
        "wind_speed": "Wind Speed",
        "wind_gust": "Wind Gust",
        "wind_dir": "Wind Direction",
        "precip_rate": "Precipitation Rate",
        "precip_accum": "Precipitation Accumulation",
        "uv": "UV Index",
        "solar": "Solar Radiation"
    }

    if variable not in allowed:
        raise HTTPException(status_code=400, detail="Invalid Variable")

    # Units
    if units == "metric":
        labels = {
            "temp": "°C",
            "dewpoint": "°C",
            "humidity": "%",
            "pressure": "hPa",
            "wind_speed": "knots",
            "wind_gust": "knots",
            "wind_dir": "°",
            "precip_rate": "mm/hr",
            "precip_accum": "mm",
            "uv": "",
            "solar": "watts/m²"
        }

    else:
        labels = {
            "temp": "°F",
            "dewpoint": "°F",
            "humidity": "%",
            "pressure": "inHg",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "wind_dir": "°",
            "precip_rate": "in/hr",
            "precip_accum": "in",
            "uv": "",
            "solar": "watts/m²"
            }

    
    values_a = []
    values_b = []

    # Get Values and convert them
    for row in weather_a:
        value = getattr(row, variable, None)
        if value is None:
            continue

        if units == "metric":
            if variable == "pressure":
                value = cv.inhg_to_hpa(value)
            elif variable in ["precip_rate", "precip_accum"]:
                value = cv.in_to_mm(value)
        else:
            if variable in ["temp", "dewpoint"]:
                value = cv.c_to_f(value)
            elif variable in ["wind_speed", "wind_gust"]:
                value = cv.knots_to_mph(value)

        values_a.append(value)

    # do same for other station
    for row in weather_b:
        value = getattr(row, variable, None)
        if value is None:
            continue

        if units == "metric":
            if variable == "pressure":
                value = cv.inhg_to_hpa(value)
            elif variable in ["precip_rate", "precip_accum"]:
                value = cv.in_to_mm(value)
        else:
            if variable in ["temp", "dewpoint"]:
                value = cv.c_to_f(value)
            elif variable in ["wind_speed", "wind_gust"]:
                value = cv.knots_to_mph(value)

        values_b.append(value)

    if len(values_a) < 2 or len(values_b) < 2:
        raise HTTPException(status_code=400, detail="Need at least two data points in each group")

    result = stats.ttest_ind(values_a, values_b, equal_var=False, nan_policy="omit")

    # Return Rounded values
    return {
        "t_stat": round(result.statistic, 4),
        "p_value": round(result.pvalue, 4)
    }

def run_anova(session: db.SessionDep, units: str="imperial", range_mode: str = "relative", range_value: int | None = 24, range_unit: str | None = "hours", start_date: str | None = None, end_date: str | None = None, station_a: str | None = None, station_b: str | None = None, station_c: str | None = None, variable: str | None = None):
    # Relative Mode
    if range_mode == "relative":
        if not range_value or not range_unit:
            raise HTTPException(status_code=400, detail="Range Value must at least be 1")


        allowed_units = {"hours", "days", "weeks", "months", "years"}
        if range_unit not in allowed_units:
            raise HTTPException(status_code=400, detail="Must be valid unit")

        now = datetime.now(pytz.UTC)

        # Graph by last 24 hrs
        if range_unit == "hours":
            cutoff_start = now - timedelta(hours=range_value)

        elif range_unit == "days":
            cutoff_start = now - timedelta(days=range_value)

        elif range_unit == "weeks":
            cutoff_start = now - timedelta(weeks=range_value)

        elif range_unit == "months":
            cutoff_start = now - timedelta(days = 30 * range_value)

        elif range_unit == "years":
            cutoff_start = now - timedelta(days = 365 * range_value)

        cutoff_end = now

    # Date Mode
    elif range_mode == "dates":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Start date and end date are required")

        start_naive = datetime.strptime(start_date, "%Y-%m-%d")
        end_naive = datetime.strptime(end_date, "%Y-%m-%d")

        if end_naive < start_naive:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        # Turn request into UTC to query db
        eastern = pytz.timezone(cfg.timezone)
        cutoff_start = eastern.localize(start_naive).astimezone(pytz.UTC)
        cutoff_end = eastern.localize(end_naive.replace(hour=23, minute=59, second=59)).astimezone(pytz.UTC)

    else:
        raise HTTPException(status_code=400, detail="Invalid Range Mode")
    

    # Get data
    weather_a = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_a, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()
    weather_b = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_b, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()
    weather_c = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_c, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()

    if not weather_a or not weather_b or not weather_c:
        raise HTTPException(status_code=404, detail="No Weather History Found")

    # Define allowed variables
    allowed = {
        "temp": "Air Temperature",
        "dewpoint": "Dew Point",
        "humidity": "Humidity",
        "pressure": "Pressure",
        "wind_speed": "Wind Speed",
        "wind_gust": "Wind Gust",
        "wind_dir": "Wind Direction",
        "precip_rate": "Precipitation Rate",
        "precip_accum": "Precipitation Accumulation",
        "uv": "UV Index",
        "solar": "Solar Radiation"
    }

    if variable not in allowed:
        raise HTTPException(status_code=400, detail="Invalid Variable")

    # Units
    if units == "metric":
        labels = {
            "temp": "°C",
            "dewpoint": "°C",
            "humidity": "%",
            "pressure": "hPa",
            "wind_speed": "knots",
            "wind_gust": "knots",
            "wind_dir": "°",
            "precip_rate": "mm/hr",
            "precip_accum": "mm",
            "uv": "",
            "solar": "watts/m²"
        }

    else:
        labels = {
            "temp": "°F",
            "dewpoint": "°F",
            "humidity": "%",
            "pressure": "inHg",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "wind_dir": "°",
            "precip_rate": "in/hr",
            "precip_accum": "in",
            "uv": "",
            "solar": "watts/m²"
            }

    
    values_a = []
    values_b = []
    values_c = []

    # Get Values and convert them
    for row in weather_a:
        value = getattr(row, variable, None)
        if value is None:
            continue

        if units == "metric":
            if variable == "pressure":
                value = cv.inhg_to_hpa(value)
            elif variable in ["precip_rate", "precip_accum"]:
                value = cv.in_to_mm(value)
        else:
            if variable in ["temp", "dewpoint"]:
                value = cv.c_to_f(value)
            elif variable in ["wind_speed", "wind_gust"]:
                value = cv.knots_to_mph(value)

        values_a.append(value)

    for row in weather_b:
        value = getattr(row, variable, None)
        if value is None:
            continue

        if units == "metric":
            if variable == "pressure":
                value = cv.inhg_to_hpa(value)
            elif variable in ["precip_rate", "precip_accum"]:
                value = cv.in_to_mm(value)
        else:
            if variable in ["temp", "dewpoint"]:
                value = cv.c_to_f(value)
            elif variable in ["wind_speed", "wind_gust"]:
                value = cv.knots_to_mph(value)

        values_b.append(value)

    for row in weather_c:
        value = getattr(row, variable, None)
        if value is None:
            continue

        if units == "metric":
            if variable == "pressure":
                value = cv.inhg_to_hpa(value)
            elif variable in ["precip_rate", "precip_accum"]:
                value = cv.in_to_mm(value)
        else:
            if variable in ["temp", "dewpoint"]:
                value = cv.c_to_f(value)
            elif variable in ["wind_speed", "wind_gust"]:
                value = cv.knots_to_mph(value)

        values_c.append(value)
            


    if len(values_a) < 2 or len(values_b) < 2 or len(values_c) < 2:
        raise HTTPException(status_code=400, detail="Need at least two data points in each group")

    result = stats.f_oneway(values_a, values_b, values_c, nan_policy="omit")

    return {
        "f_stat": round(result.statistic, 4),
        "p_value": round(result.pvalue, 4)
    }

# CSV Test Download
@app.get("/test/weather/csv")
def test_csv(session: db.SessionDep, units: str = "imperial", range_mode: str = "relative", range_value: int | None = None, range_unit: str | None = None, start_date: str | None = None, end_date: str | None = None, title: str = "", station_id: str = "", variable: str = "", test: str | None = None, x_variable: str | None = None, y_variable: str | None = None, station_id_a: str | None = None, station_id_b: str | None = None, station_id_c: str | None = None):
    # Relative Mode
    if range_mode == "relative":
        if not range_value or not range_unit:
            raise HTTPException(status_code=400, detail="Range Value must at least be 1")

        allowed_units = {"hours", "days", "weeks", "months", "years"}
        if range_unit not in allowed_units:
            raise HTTPException(status_code=400, detail="Must be valid unit")

        now = datetime.now(pytz.UTC)

        # Graph by last 24 hrs
        if range_unit == "hours":
            cutoff_start = now - timedelta(hours=range_value)

        elif range_unit == "days":
            cutoff_start = now - timedelta(days=range_value)

        elif range_unit == "weeks":
            cutoff_start = now - timedelta(weeks=range_value)

        elif range_unit == "months":
            cutoff_start = now - timedelta(days = 30 * range_value)

        elif range_unit == "years":
            cutoff_start = now - timedelta(days = 365 * range_value)

        cutoff_end = now
        range_label = f"Past {range_value} {range_unit}"

    # Date Mode
    elif range_mode == "dates":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Start date and end date are required")

        start_naive = datetime.strptime(start_date, "%Y-%m-%d")
        end_naive = datetime.strptime(end_date, "%Y-%m-%d")

        if end_naive < start_naive:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        # Turn request into UTC to query db
        eastern = pytz.timezone(cfg.timezone)
        cutoff_start = eastern.localize(start_naive).astimezone(pytz.UTC)
        cutoff_end = eastern.localize(end_naive.replace(hour=23, minute=59, second=59)).astimezone(pytz.UTC)

        range_label = f"{start_date} to {end_date}"

    else:
        raise HTTPException(status_code=400, detail="Invalid Range Mode")
    
    allowed = {
            "temp": "Air Temperature",
            "dewpoint": "Dew Point",
            "humidity": "Humidity",
            "pressure": "Pressure",
            "wind_speed": "Wind Speed",
            "wind_gust": "Wind Gust",
            "wind_dir": "Wind Direction",
            "precip_rate": "Precipitation Rate",
            "precip_accum": "Precipitation Accumulation",
            "uv": "UV Index",
            "solar": "Solar Radiation"
        }

    # Units
    if units == "metric":
        labels = {
            "temp": "°C",
            "dewpoint": "°C",
            "humidity": "%",
            "pressure": "hPa",
            "wind_speed": "knots",
            "wind_gust": "knots",
            "wind_dir": "°",
            "precip_rate": "mm/hr",
            "precip_accum": "mm",
            "uv": "",
            "solar": "watts/m²"
        }

    else:
        labels = {
            "temp": "°F",
            "dewpoint": "°F",
            "humidity": "%",
            "pressure": "inHg",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "wind_dir": "°",
            "precip_rate": "in/hr",
            "precip_accum": "in",
            "uv": "",
            "solar": "watts/m²"
        }

    def convert_value(var, value):
        if value is None:
            return None

        # Convert to metric
        if units == "metric":
            if var == "pressure":
                return cv.inhg_to_hpa(value)
            if var in ["precip_rate", "precip_accum"]:
                return cv.in_to_mm(value)
            return value

        # convert to imperial
        else:
            if var in ["temp", "dewpoint"]:
                return cv.c_to_f(value)
            if var in ["wind_speed", "wind_gust"]:
                return cv.knots_to_mph(value)
            return value

    local_tz = pytz.timezone(cfg.timezone)
    output = io.StringIO()

    if test == "linear_regression":
        if not station_id or not x_variable or not y_variable:
            raise HTTPException(status_code=400, detail="Missing Linear Regression Inputs")

        if x_variable not in allowed or y_variable not in allowed:
            raise HTTPException(status_code=400, detail="Invalid Variable")

        # Get Weather
        weather = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_id, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()

        x = []
        y = []
        cleaned = []

        # Convert
        for row in weather:
            x_value = convert_value(x_variable, getattr(row, x_variable, None))
            y_value = convert_value(y_variable, getattr(row, y_variable, None))
            observed_at = row.observed_at

            if x_value is None or y_value is None or observed_at is None:
                continue

            if observed_at.tzinfo is None:
                observed_at = pytz.UTC.localize(observed_at)
            local_time = observed_at.astimezone(local_tz)

            x.append(x_value)
            y.append(y_value)
            cleaned.append((local_time.isoformat(), x_value, y_value))

        if len(x) < 2:
            raise HTTPException(status_code=400, detail="Need at least two data points")

        # Run Stats
        slope, intercept = np.polyfit(x, y, 1)

        if len(set(y)) <= 1:
            r_squared = 0.0
        else:
            predicted_y = slope * np.array(x) + intercept
            ss_residual = np.sum((np.array(y) - predicted_y) ** 2)
            ss_total = np.sum((np.array(y) - np.mean(y)) ** 2)
            r_squared = 1 - (ss_residual / ss_total)

        fieldnames = [
            "test_type", "station_id", "range", "x_label", "y_label",
            "slope", "intercept", "r_squared",
            f"observed_at_{cfg.time_zone_name}", "x_value", "y_value"
        ]

        # Write Summary
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for observed_at, x_value, y_value in cleaned:
            writer.writerow({
                "test_type": "linear_regression",
                "station_id": station_id,
                "range": range_label,
                "x_label": f"{allowed[x_variable]} ({labels[x_variable]})",
                "y_label": f"{allowed[y_variable]} ({labels[y_variable]})",
                "slope": round(slope, 4),
                "intercept": round(intercept, 4),
                "r_squared": round(r_squared, 4),
                f"observed_at_{cfg.time_zone_name}": observed_at,
                "x_value": x_value,
                "y_value": y_value,
            })

    # T Test
    elif test == "t_test":
        if not variable or not station_id_a or not station_id_b:
            raise HTTPException(status_code=400, detail="Missing T-Test Inputs")
        if variable not in allowed:
            raise HTTPException(status_code=400, detail="INvalid Variable")

        result = run_t_test(session, units=units, range_mode=range_mode, range_value=range_value, range_unit=range_unit, start_date=start_date, end_date=end_date, station_a=station_id_a, station_b=station_id_b, variable=variable)

        fieldnames = [
            "test_type", "variable", "range", "station_a", "station_b",
            "t_stat", "p_value", "station_id",
            f"observed_at_{cfg.time_zone_name}", "value"
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        wrote_rows = False
        for sid in [station_id_a, station_id_b]:
            weather = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == sid, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()
        
            for row in weather:
                value = convert_value(variable, getattr(row, variable, None))
                observed_at = row.observed_at

                if value is None or observed_at is None:
                    continue

                if observed_at.tzinfo is None:
                    observed_at = pytz.UTC.localize(observed_at)
                local_time = observed_at.astimezone(local_tz)

                writer.writerow({
                    "test_type": "independent_two_sample_t_test",
                    "variable": f"{allowed[variable]} ({labels[variable]})",
                    "range": range_label,
                    "station_a": station_id_a,
                    "station_b": station_id_b,
                    "t_stat": result["t_stat"],
                    "p_value": result["p_value"],
                    "station_id": sid,
                    f"observed_at_{cfg.time_zone_name}": observed_at.astimezone(local_tz).isoformat(),
                    "value": value,
                })
                wrote_rows = True

        if not wrote_rows:
            raise HTTPException(status_code=404, detail="No Exportable Data Found")

    elif test == "anova":
        if not variable or not station_id_a or not station_id_b or not station_id_c:
            raise HTTPException(status_code=400, detail="Missing ANOVA Inputs")

        if variable not in allowed:
            raise HTTPException(status_code=400, detail="Invalid Variable")

        result = run_anova(session, units=units, range_mode=range_mode, range_value=range_value, range_unit=range_unit, start_date=start_date, end_date=end_date, station_a=station_id_a, station_b=station_id_b, station_c=station_id_c, variable=variable)

        fieldnames = [
            "test_type", "variable", "range", "station_a", "station_b", "station_c",
            "f_stat", "p_value", "station_id",
            f"observed_at_{cfg.time_zone_name}", "value"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        wrote_rows = False
        for sid in [station_id_a, station_id_b, station_id_c]:
            weather = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == sid, m.WeatherHistory.observed_at >= cutoff_start, m.WeatherHistory.observed_at <= cutoff_end).order_by(m.WeatherHistory.observed_at)).all()

            for row in weather:
                value = convert_value(variable, getattr(row, variable, None))
                observed_at = row.observed_at

                if value is None or observed_at is None:
                    continue

                if observed_at.tzinfo is None:
                    observed_at = pytz.UTC.localize(observed_at)
                local_time = observed_at.astimezone(local_tz)

                writer.writerow({
                    "test_type": "one_way_anova",
                    "variable": f"{allowed[variable]} ({labels[variable]})",
                    "range": range_label,
                    "station_a": station_id_a,
                    "station_b": station_id_b,
                    "station_c": station_id_c,
                    "f_stat": result["f_stat"],
                    "p_value": result["p_value"],
                    "station_id": sid,
                    f"observed_at_{cfg.time_zone_name}": observed_at.astimezone(local_tz).isoformat(),
                    "value": value,
                })
                wrote_rows = True

            if not wrote_rows:
                    raise HTTPException(status_code=404, detail="No Exportable Data Found")

    else:
        raise HTTPException(status_code=400, detail="Invalid Test type")

    csv_data = output.getvalue()
    output.close()

    safe_title = title.strip().replace(" ", "_") if title.strip() else (test or "weather_test")
    filename = f"{safe_title}_{range_label}_{units}.csv"
    filename = filename.strip().replace(" ", "_") if filename.strip() else (f"{test}.csv" or "weather_test.csv")

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return Response(content=csv_data, media_type="text/csv", headers=headers)

#---API Read---

# API Active Station Read
@app.get("/scraper/stations", response_model=list[m.Station])
def scraper_station_active(session: db.SessionDep, x_api_key: Annotated[str, Header()]):
    # Check if api key is correct
    if x_api_key != cfg.scraper_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Open Station and check if active
    stations = session.exec(select(m.Station).order_by(m.Station.station_name)).all()
    if not stations:
        raise HTTPException(status_code=404, detail="Station Not Found")
    
    return stations
    

# Toggle maintenance with a form
@app.post("/maintenance/{station_id}", response_class=HTMLResponse)
def toggle_maintenance(request: Request, session: db.SessionDep, station_id: str, current_user: Annotated[m.User, Depends(get_current_user)]):

    update = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()

    if not update:
        raise HTTPException(status_code=404, detail="Station Not Found")

    # Check if user
    user = session.exec(select(m.User).where(m.User.id == current_user.id)).first()

    if not user:
        raise HTTPException(status_code=404, detail="User Not Found")
    
    if current_user.role != "admin":
        # Check if user
        access = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == current_user.id, m.UserAccess.can_view == True, m.UserAccess.can_toggle_maintenance == True, m.UserAccess.station_id == station_id)).first()

        # Check if they have access
        if not access:
            raise HTTPException(status_code=403, detail="Cannot Toggle Maintenance")

    update.is_in_maintenance = not update.is_in_maintenance

    if update.is_in_maintenance:
        update.is_public = False

    # Update in db
    session.add(update)
    session.commit()
    session.refresh(update)

    # Response message
    msg = "maintenance_on" if update.is_in_maintenance else "maintenance_off"
    
    return RedirectResponse(url=f"/stations/dashboard/{station_id}?success={msg}", status_code=303)

# Toggle public with form
@app.post("/public/{station_id}", response_class=HTMLResponse)
def toggle_public(request: Request, session: db.SessionDep, station_id: str, current_user: Annotated[m.User, Depends(get_current_user)]):

    update = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()

    if not update:
        raise HTTPException(status_code=404, detail="Station Not Found")

    # Check if user
    user = session.exec(select(m.User).where(m.User.id == current_user.id)).first()

    if not user:
        raise HTTPException(status_code=404, detail="User Not Found")

    if current_user.role != "admin":
        # Check if they have access
        access = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == current_user.id, m.UserAccess.can_view == True, m.UserAccess.can_toggle_maintenance == True, m.UserAccess.station_id == station_id)).first()

        if not access:
            raise HTTPException(status_code=403, detail="Cannot Toggle Maintenance")

    if update.is_in_maintenance and not update.is_public:
        return RedirectResponse(url=f"/stations/dashboard/{station_id}?success=public_blocked", status_code=303)
    
    update.is_public = not update.is_public
    
    # Update DB
    session.add(update)
    session.commit()
    session.refresh(update)

    # Success message
    msg = "public_on" if update.is_public else "public_off"

    return RedirectResponse(url=f"/stations/dashboard/{station_id}?success={msg}", status_code=303)

@app.get("/register/no")
def load_register_no():
    return {"message": "Please Register Man or Woman. Or person. Or Apache attack helicopter. If you are not one of those I give up. Computers don't judge"}

@app.get("/register", response_class=HTMLResponse)
def load_register(request: Request):
    return templates.TemplateResponse(request, "register.html", {"request": request, "title": "Register", "active_page": "register"})

# Form Response for register
@app.post("/register")
def register(request: Request, session: db.SessionDep, username: str = Form(), password: str = Form()): #make this require admin later
    # Check for existing user:
    existing_user = session.exec(select(m.User).where(m.User.username == username)).first()

    if existing_user:
        return templates.TemplateResponse(request, "register.html", {"request": request, "title": "Register", "active_page": "register", "error": "User already exists"}, status_code=401)

    # Table Entry
    db_user = m.User(
        username=username,
        role="public",
        password_hash=s.hash_password(password),
    )
    # Save to db
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    # First account is A admin account
    if db_user.id == 1:
        db_user.role = "admin"
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

    return templates.TemplateResponse(request, "login.html", {"request": request, "title": "Login", "active_page": "login"})

# Form Response for register
@app.post("/settings/register")
def register(request: Request, session: db.SessionDep, username: str = Form(), password: str = Form()): #make this require admin later
    # Check for existing user:
    existing_user = session.exec(select(m.User).where(m.User.username == username)).first()

    if existing_user:
        return RedirectResponse(url="/settings?error=user_exists", status_code=303)

    # Table Entry
    db_user = m.User(
        username=username,
        role="public",
        password_hash=s.hash_password(password),
    )
    # Save to db
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    # First account is A admin account
    if db_user.id == 1:
        db_user.role = "admin"
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

    return RedirectResponse(url="/settings?success=registered", status_code=303)


# Read your user
@app.get("/users/me")
def read_users_me(current_user: Annotated[m.User, Depends(get_current_user)]):
    return current_user["username"], current_user["role"]

# All users
@app.get("/users/")
def read_users(session: db.SessionDep, offset: Annotated[int, Query(ge=0)], current_user: Annotated[m.User, Depends(require_admin)], limit: Annotated[int, Query(gt=0, le=100)] = 100,):
   users = session.exec(select(m.User).offset(offset).limit(limit)).all()
   return users

# Delete User
@app.delete("/users/{user_id}")
def delete_user(session: db.SessionDep, user_id: int, current_user: Annotated[m.User, Depends(require_admin)]):
    # Check id
    id = session.exec(select(m.User).where(m.User.id == user_id)).first()
    if not id:
        raise HTTPException(status_code=404, detail="User Not Found")

    # Delete
    session.delete(id)
    session.commit()
    return {"ok": True, "Detail": f"{id.username} deleted"}

# Delete using Settings html
@app.post("/users/delete")
def delete_user_from_html(session: db.SessionDep, user_id: int = Form(), current_user: Annotated[m.User, Depends(require_admin)] = None):
    user_db = session.exec(select(m.User).where(m.User.id == user_id)).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not Found")

    username = user_db.username

    session.delete(user_db)
    session.commit()

    return RedirectResponse(url=f"/settings?success=deleted&username={username}", status_code=status.HTTP_303_SEE_OTHER)
#---Access---

# Read what stations a user can affect
@app.get("/users/{user_id}/stations")
def read_user_stations(user_id: int, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    # Open row
    access_rows = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id)).all()

    if not access_rows:
        return []

    # Send back data
    return [
        {
            "station_id": row.station_id,
            "can_view": row.can_view,
            "can_toggle_maintenance": row.can_toggle_maintenance,
        }
        for row in access_rows
    ]

# Give User Access to a station
@app.post("/users/{user_id}/stations/{station_id}")
def grant_station_access(user_id: int, station_id: str, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    # Open station
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station Not Found")

    # Find user
    id = session.exec(select(m.User).where(m.User.id == user_id)).first()
    if not id:
        raise HTTPException(status_code=404, detail="User Not Found")

    # Check for duplicate
    existing = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id, m.UserAccess.station_id == station_id)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Access already exists")

    # Add access
    access = m.UserAccess(user_id=user_id, station_id=station_id, can_view=True)
    session.add(access)
    session.commit()
    return {"Ok": True}

@app.post("/users/stations/grant")
def grant_station_access_from_form(session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)], user_id: int = Form(), station_id: str = Form()):
    # Open station
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        return RedirectResponse(url=f"/settings?error=404", status_code=303)

    # Find user
    id = session.exec(select(m.User).where(m.User.id == user_id)).first()
    if not id:
        return RedirectResponse(url=f"/settings?error=404", status_code=303)

    # Check for duplicate
    existing = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id, m.UserAccess.station_id == station_id)).first()
    if existing:
        return RedirectResponse(url=f"/settings?error=duplicate", status_code=303)

    # Add access
    access = m.UserAccess(user_id=user_id, station_id=station_id, can_view=True)
    session.add(access)
    session.commit()
    return RedirectResponse(url=f"/settings?success=granted", status_code=303)

# Delete Access
@app.delete("/users/{user_id}/stations/{station_id}")
def revoke_station_access(user_id: int, station_id: str, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    # Open station
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station Not Found")

    # Check id
    id = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id)).first()
    if not id:
        raise HTTPException(status_code=404, detail="User Not Found")

    # Select
    access = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id, m.UserAccess.station_id == station_id)).first()

    # Delete
    session.delete(access)
    session.commit()
    return {"ok": True}

# Delete Access from form
@app.post("/users/stations/revoke")
def revoke_station_access_from_form(session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)], user_id: int = Form(), station_id: str = Form()):
    # Open station
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        return RedirectResponse(url=f"/settings?error=404", status_code=303)

    # Check id
    id = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id)).first()
    if not id:
        return RedirectResponse(url=f"/settings?error=404", status_code=303)

    # Select
    access = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id, m.UserAccess.station_id == station_id)).first()
    if not access:
        return RedirectResponse(url=f"/settings?error=404", status_code=303)

    # Delete
    session.delete(access)
    session.commit()
    return RedirectResponse(url=f"/settings?success=revoked", status_code=303)

# Update access
@app.patch("/users/{user_id}/stations/{station_id}")
def update_station_access(user_id: int, station_id: str, user: m.UserAccessUpdate, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):

    # select user
    user_db = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id, m.UserAccess.station_id == station_id)).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="Station Not Found")

    # Open and update
    user_data = user.model_dump(exclude_unset=True)
    user_db.sqlmodel_update(user_data)
    session.commit()
    session.refresh(user_db)
    return user_db

# Update access from form
@app.post("/users/stations/update")
def update_station_access_from_form(session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)], user_id: int = Form(), station_id: str = Form(), can_view: bool | None = Form(False), can_toggle_maintenance: bool | None = Form(False)):

    # select user
    access_db = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id,m.UserAccess.station_id == station_id)).first()
    if not access_db:
        return RedirectResponse(url="/settings?error=404", status_code=303)

    payload = {
        "can_view": can_view,
        "can_toggle_maintenance": can_toggle_maintenance,
    }
    if not payload:
        return RedirectResponse(url=f"/settings?error=no_payload", status_code=303)

    # Open and update
    access_db.sqlmodel_update(payload)
    session.add(access_db)
    session.commit()
    session.refresh(access_db)

    return RedirectResponse(url="/settings?success=updated", status_code=status.HTTP_303_SEE_OTHER)

# Update user from settings form
@app.post("/users/update")
def update_user_from_form(session: db.SessionDep, user_id: int = Form(), username: str | None = Form(None), password: str | None = Form(None), role: str | None = Form(None)):
    # Select User
    user_db = session.exec(select(m.User).where(m.User.id == user_id)).first()
    if not user_db:
        return RedirectResponse(url=f"/settings?error=404", status_code=303)

    # Update
    payload = {}
    if username and username.strip():
        payload["username"] = username.strip()
    if password and password.strip():
        payload["password"] = password.strip()
    if role and role.strip():
        payload["role"] = role.strip()

    if not payload:
        return RedirectResponse(url=f"/settings?error=no_payload", status_code=303)

    user = m.UserUpdate(**payload)
    user_data = user.model_dump(exclude_unset=True)

    if "password" in user_data:
        user_db.password_hash = s.hash_password(user_data.pop("password"))

    user_db.sqlmodel_update(user_data)
    session.add(user_db)
    session.commit()
    session.refresh(user_db)

    return RedirectResponse(url="/settings?success=updated", status_code=status.HTTP_303_SEE_OTHER)

# Update User
@app.patch("/users/{user_id}")
def update_user(user_id: int, user: m.UserUpdate, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    # Open User
    user_db = session.exec(select(m.User).where(m.User.id == user_id)).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="No User Exists")

    # update
    user_data = user.model_dump(exclude_unset=True)

    # Hash password
    if "password" in user_data:
        user_db.password_hash = s.hash_password(user_data.pop("password"))

    # Save
    user_db.sqlmodel_update(user_data)
    session.add(user_db)
    session.commit()
    session.refresh(user_db)
    return user_db

#---Stations---

# Create Station Rows in DB:
@app.post("/stations/create", response_model=m.StationPublic)
def create_station(station: m.StationCreate, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    # Make and Save
    db_station = m.Station.model_validate(station)
    session.add(db_station)
    session.commit()
    session.refresh(db_station)
    return db_station

# Create Station Rows in DB from form:
@app.post("/stations/create/form")
def create_station_form(session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)], station_id: str = Form(), station_name: str = Form(), is_in_maintenance: bool = Form(False), is_public: bool = Form(True)):
    # Get data
    payload = {
        "station_id": station_id.strip(),
        "station_name": station_name.strip(),
        "is_in_maintenance": is_in_maintenance,
        "is_public": is_public
    }

    if not payload:
        return RedirectResponse(url="/settings?error=no_payload", status_code=303)

    station = m.StationCreate(**payload)
    db_station = m.Station.model_validate(station)

    # Create
    session.add(db_station)
    session.commit()
    session.refresh(db_station)

    return RedirectResponse(url=f"/settings?success=station_created&username={station_name}", status_code=303)    


# Read all stations:
@app.get("/read/stations/", response_model=list[m.StationPublic])
def read_all_stations(session: db.SessionDep, offset: Annotated[int, Query(ge=0)], limit: Annotated[int, Query(gt=0, le=100)] = 100,):
    stations = session.exec(select(m.Station).offset(offset).limit(limit)).all()
    return stations

# Read station by ID:
@app.get("/read/stations/{station_id}", response_model=m.StationPublic)
def read_one_station(station_id: str, session: db.SessionDep, station: Annotated[m.User, Depends(require_station_access)]):
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station Not Found")
    return station

# Double check all stations in config are in database   
@app.get("/seed")
def seed(current_user: Annotated[m.User, Depends(require_admin)]):
    seed_stations()
    return {"message": "Stations seeded"}

# Delete station
@app.delete("/delete/stations/{station_id}")
def delete_station(station_id: str, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="No Station to Delete")
    session.delete(station)
    session.commit()
    return {"ok": True}

# Delete Station from form
@app.post("/delete/stations")
def delete_station_from_form(session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)], station_id: str = Form()):
    # Get Station
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        return RedirectResponse(url="/settings?error=404", status_code=303)

    # Delete
    session.delete(station)
    session.commit()
    return RedirectResponse(url="/settings?success=station_deleted", status_code=303)


# Update Station (MAIN METHOD)
@app.patch("/update/stations/{station_id}", response_model=m.StationPublic)
def update_station(station_id: str, station: m.StationUpdate, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    station_db = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station_db:
        raise HTTPException(status_code=404, detail="Station Not Found")
    station_data = station.model_dump(exclude_unset=True)
    station_db.sqlmodel_update(station_data)
    session.commit()
    session.refresh(station_db)
    return station_db

# Update Station (form)
@app.post("/update/stations")
def update_station_from_form(session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)], station_id: str = Form(), station_name: str = Form()):
    # Open Data
    station_db = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station_db:
        return RedirectResponse(url="/settings?error=404", status_code=303)

    # Update
    payload = {}
    if station_name and station_name.strip():
        payload["station_name"] = station_name.strip()
    if not payload:
            return RedirectResponse(url=f"/settings?error=no_payload", status_code=303)

    station = m.StationUpdate(**payload)
    station_data = station.model_dump(exclude_unset=True)

    station_db.sqlmodel_update(station_data)
    session.add(station_db)
    session.commit()
    session.refresh(station_db)
    return RedirectResponse(url="/settings?success=updated", status_code=303)

#---Status---

# Add Current/History Status
@app.post("/status/stations", response_model=m.StatusPublic)
def post_status(session: db.SessionDep, status_in: m.StatusIn, x_api_key: Annotated[str, Header()]):

    # Check api_key
    if x_api_key != cfg.scraper_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Open current
    current = session.exec(select(m.Status).where(m.Status.station_id == status_in.station_id)).first()
    
    # On first post
    if current is None:
        current = m.Status(
            station_id=status_in.station_id,
            time_of_status=status_in.time_of_status,
            last_status=status_in.last_status,
            consecutive_offline=status_in.consecutive_offline,
            first_offline=status_in.first_offline,
            last_connected=status_in.last_connected,
            alert_sent=status_in.alert_sent
        )
        session.add(current)

        history = m.StatusHistory(
            station_id=status_in.station_id,
            time_of_status=status_in.time_of_status,
            last_status=status_in.last_status,
            consecutive_offline=status_in.consecutive_offline,
            first_offline=status_in.first_offline,
            last_connected=status_in.last_connected,
            alert_sent=status_in.alert_sent
        )
        session.add(history)

        session.commit()
        session.refresh(current)
        return current
    
    # Check for changes, if so append history.
    changed = any([
        current.last_status != status_in.last_status,
        current.consecutive_offline != status_in.consecutive_offline,
        current.first_offline != status_in.first_offline,
        current.last_connected != status_in.last_connected,
        current.alert_sent != status_in.alert_sent,
    ])

    if changed:
        history = m.StatusHistory(
            station_id=status_in.station_id,
            time_of_status=status_in.time_of_status,
            last_status=status_in.last_status,
            consecutive_offline=status_in.consecutive_offline,
            first_offline=status_in.first_offline,
            last_connected=status_in.last_connected,
            alert_sent=status_in.alert_sent
        )
        session.add(history)

    # Update Current
    current.time_of_status = status_in.time_of_status
    current.last_status = status_in.last_status
    current.consecutive_offline = status_in.consecutive_offline
    current.first_offline = status_in.first_offline
    current.last_connected = status_in.last_connected
    current.alert_sent = status_in.alert_sent

    session.add(current)

    # Save
    session.commit()
    session.refresh(current)
    return current

# Read Current by Station
@app.get("/read/status/stations/{station_id}", response_model=m.StatusPublic)
def read_current_status(session: db.SessionDep, station_id: str, current_user: Annotated[m.User, Depends(require_station_access)]):
    # Read
    status = session.exec(select(m.Status).where(m.Status.station_id == station_id)).first()
    if not status:
        raise HTTPException(status_code=404, detail="Station Not Found")
    return status

# Read History by Station
@app.get("/read/status-history/stations/{station_id}", response_model=list[m.StatusHistoryPublic])
def read_status_history(session: db.SessionDep, station_id: str, current_user: Annotated[m.User, Depends(require_station_access)], offset: Annotated[int, Query(ge=0)], limit: Annotated[int, Query(gt=0, le=cfg.limit_history)] = cfg.default_history):
    history = session.exec(select(m.StatusHistory).where(m.StatusHistory.station_id == station_id).offset(offset).limit(limit)).all()
    return history 

#---Weather---

# Add Current/History Weather
@app.post("/weather/stations", response_model=m.WeatherPublic)
def post_weather(session: db.SessionDep, x_api_key: Annotated[str, Header()], w_in: m.WeatherIn):
    current = session.exec(select(m.Weather).where(m.Weather.station_id == w_in.station_id)).first()

    # On first post
    if current is None:
        current = m.Weather(
            station_id=w_in.station_id,
            observed_at=w_in.observed_at,
            temp=w_in.temp,
            dewpoint=w_in.dewpoint,
            humidity=w_in.humidity,
            wind_speed=w_in.wind_speed,
            wind_gust=w_in.wind_gust,
            wind_dir=w_in.wind_dir,
            pressure=w_in.pressure,
            precip_rate=w_in.precip_rate,
            precip_accum=w_in.precip_accum,
            uv=w_in.uv,
            solar=w_in.solar
        )
        session.add(current)
        
        history = m.WeatherHistory(
            station_id=w_in.station_id,
            observed_at=w_in.observed_at,
            temp=w_in.temp,
            dewpoint=w_in.dewpoint,
            humidity=w_in.humidity,
            wind_speed=w_in.wind_speed,
            wind_gust=w_in.wind_gust,
            wind_dir=w_in.wind_dir,
            pressure=w_in.pressure,
            precip_rate=w_in.precip_rate,
            precip_accum=w_in.precip_accum,
            uv=w_in.uv,
            solar=w_in.solar
        )
        session.add(history)

        session.commit()
        session.refresh(current)
        return current
    
    # Add to current
    current.observed_at = w_in.observed_at
    current.temp = w_in.temp
    current.dewpoint = w_in.dewpoint
    current.humidity = w_in.humidity
    current.wind_speed = w_in.wind_speed
    current.wind_gust = w_in.wind_gust
    current.wind_dir = w_in.wind_dir
    current.pressure = w_in.pressure
    current.precip_rate = w_in.precip_rate
    current.precip_accum = w_in.precip_accum
    current.uv = w_in.uv
    current.solar = w_in.solar
    session.add(current)

    # Add to history
    history = m.WeatherHistory(
        station_id=w_in.station_id,
        observed_at=w_in.observed_at,
        temp=w_in.temp,
        dewpoint=w_in.dewpoint,
        humidity=w_in.humidity,
        wind_speed=w_in.wind_speed,
        wind_gust=w_in.wind_gust,
        wind_dir=w_in.wind_dir,
        pressure=w_in.pressure,
        precip_rate=w_in.precip_rate,
        precip_accum=w_in.precip_accum,
        uv=w_in.uv,
        solar=w_in.solar
    )
    session.add(history)

    session.commit()
    session.refresh(current)
    return current

# Read Current by Station
@app.get("/read/weather/stations/{station_id}", response_model=m.WeatherPublic)
def read_current_weather(session: db.SessionDep, station_id: str, current_user: Annotated[m.User, Depends(require_station_access)]):
    current = session.exec(select(m.Weather).where(m.Weather.station_id == station_id)).first()
    if not current:
        raise HTTPException(status_code=404, detail="Station Not Found")
    return current

# Read History by Station
@app.get("/read/weather-history/stations/{station_id}", response_model=list[m.WeatherHistoryPublic])
def read_history_weather(session: db.SessionDep, station_id: str, current_user: Annotated[m.User, Depends(require_station_access)], offset: Annotated[int, Query(ge=0)], limit: Annotated[int, Query(gt=0, le=cfg.limit_history)] = cfg.default_history):
    history = session.exec(select(m.WeatherHistory).where(m.WeatherHistory.station_id == station_id).offset(offset).limit(limit)).all()
    if not history:
        raise HTTPException(status_code=404, detail="Station Not Found")
    return history
    