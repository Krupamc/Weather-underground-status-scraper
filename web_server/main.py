# Web Deployment using sqlite:

from fastapi import FastAPI, Cookie, HTTPException, Query, Depends, status, Request, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Annotated
from sqlmodel import select
import database as db
import model as m
import web_config as cfg
import security as s
import jwt
from jwt import InvalidTokenError
from datetime import datetime

app = FastAPI(title="SBB Mesonet Notification System")

# Static and Templates
templates = Jinja2Templates(directory="web_server/templates")
app.mount("/static", StaticFiles(directory="web_server/static"), name="static")

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
        for station in db_station:
            if station.station_id not in config_ids:
                session.delete(station)
                # make it delet its other models...

        session.commit()

# Check what user
def get_current_user(session: db.SessionDep, access_token: str | None = Cookie(default=None)):
    
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated; login")
    
    if access_token is None:
        raise credentials_exception
    
    try:
        payload = jwt.decode(access_token, s.secret_key, algorithms=[s.algorithm],)
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    
    user = session.exec(select(m.User).where(m.User.username == username)).first()

    if user is None:
        raise credentials_exception
    
    return user
    

def require_admin(current_user: Annotated[m.User, Depends(get_current_user)]):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Enough Permissions")
    return current_user

def require_station_access(station_id: str, current_user: Annotated[m.User, Depends(get_current_user)], session: db.SessionDep):
    
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    
    if not station:
        raise HTTPException(status_code=404, detail="Station Does Not Exist")

    # Admin override
    if current_user.role == "admin":
        return station
    
    access = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == current_user.id, m.UserAccess.station_id == station_id, m.UserAccess.can_view == True)).first()

    if not access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Enough Permissions")
    
    return station

#----Actual Web App-----

@app.on_event("startup")
def on_startup():
    db.create_db_table()
    seed_stations()


# Homepage
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"request": request})

# Manually go to 404 error
@app.get("/404", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "404.html", {"request": request, "title": "404"})

# For any http error, send them to a specific error page
@app.exception_handler(StarletteHTTPException)
async def not_found(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(request, "404.html", {"request": request, "title": "404"})
    elif exc.status_code == 403:
        return templates.TemplateResponse(request, "403.html", {"request": request, "title": "403"})
    elif exc.status_code == 401:
        return templates.TemplateResponse(request, "401.html", {"request": request, "title": "401"})
    
    return await http_exception_handler(request, exc)
    

# List of Stations
@app.get("/stations", response_class=HTMLResponse)
def stations(request: Request):
    with db.Session(db.engine) as session:
        stations = session.exec(select(m.Station)).all()
    return templates.TemplateResponse(request, "stations.html", context={"request": request, "title": "Weather Stations", "active_page": "stations", "stations": stations})

#---Login---

# Gives direct token
@app.post("/token")
def login_for_access_token(
    session: db.SessionDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    user = session.exec(select(m.User).where(m.User.username == form_data.username)).first()

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

@app.post("/login")
def login_page_submit(request: Request, session: db.SessionDep, form_data: OAuth2PasswordRequestForm = Depends()):
    user = session.exec(select(m.User).where(m.User.username == form_data.username)).first()

    if not user or not s.verify_password(form_data.password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"request": request, "title": "Login", "active_page": "login", "error": "Invalid Credentials"}, status_code=401)
    
    access_token = s.create_access_token(data={"sub": user.username}) 
    response = RedirectResponse(url="/users", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response

@app.get("/register/no")
def load_register_no():
    return {"message": "Please Register Man or Woman. Or person. Or Apache attack helicopter. If you are not one of those I give up. Computers don't judge"}

@app.get("/register/", response_class=HTMLResponse)
def load_register(request: Request):
    return templates.TemplateResponse(request, "register.html", {"request": request, "title": "Register", "active_page": "register"})

@app.post("/register/")
def register(username: str, password: str, session: db.SessionDep): #make this require admin later
    db_user = m.User(
        username=username,
        role="public",
        password_hash=s.hash_password(password),
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@app.get("/users/me")
def read_users_me(current_user: Annotated[m.User, Depends(get_current_user)]):
    return current_user

@app.get("/users/")
def read_users(session: db.SessionDep, offset: Annotated[int, Query(ge=0)], current_user: Annotated[m.User, Depends(require_admin)], limit: Annotated[int, Query(gt=0, le=100)] = 100,):
   users = session.exec(select(m.User).offset(offset).limit(limit)).all()
   return users
 
#---Access---

# Give User Access to a station
@app.post("/users/{user_id}/stations/{station_id}")
def grant_station_access(user_id: int, station_id: str, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station Not Found")
    id = session.exec(select(m.User).where(m.User.id == user_id)).first()
    if not id:
        raise HTTPException(status_code=404, detail="User Not Found")

    existing = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id, m.UserAccess.station_id == station_id)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Access already exists")
    
    access = m.UserAccess(user_id=user_id, station_id=station_id, can_view=True)
    session.add(access)
    session.commit()
    return {"Ok": True}

# Delete Access
@app.delete("/users/{user_id}/station/{station_id}")
def revoke_station_access(user_id: int, station_id: str, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station Not Found")
    id = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id)).first()
    if not id:
        raise HTTPException(status_code=404, detail="User Not Found")
    
    access = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id, m.UserAccess.station_id == station_id)).first()

    session.delete(access)
    session.commit()
    return {"ok": True}

# Update access
@app.patch("/users/{user_id}/stations/{station_id}")
def update_station_access(user_id: int, station_id: str, user: m.UserAccessUpdate, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    user_db = session.exec(select(m.UserAccess).where(m.UserAccess.user_id == user_id, m.UserAccess.station_id == station_id)).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="Station Not Found")
    user_data = user.model_dump(exclude_unset=True)
    user_db.sqlmodel_update(user_data)
    session.commit()
    session.refresh(user_db)
    return user_db

# Update User
@app.patch("/users/{user_id}")
def update_user(user_id: int, user: m.UserUpdate, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    user_db = session.exec(select(m.User).where(m.User.id == user_id)).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="No User Exists")
    user_data = user.model_dump(exclude_unset=True)

    if "password" in user_data:
        user_db.password_hash = s.hash_password(user_data.pop("password"))

    user_db.sqlmodel_update(user_data)
    session.add(user_db)
    session.commit()
    session.refresh(user_db)
    return user_db
#---Stations---

# Public dashboard for the station:
@app.get("/stations/public/{station_id}")
def public_station():
    return {"message": "ok"}


# Create Station Rows in DB:
@app.post("/stations/create", response_model=m.StationPublic)
def create_station(station: m.StationCreate, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    db_station = m.Station.model_validate(station)
    session.add(db_station)
    session.commit()
    session.refresh(db_station)
    return db_station

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
@app.delete("/stations/{station_id}")
def delete_station(station_id: str, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="No Station to Delete")
    session.delete(station)
    session.commit()
    return {"ok": True}

# Update Station (MAIN METHOD)
@app.patch("/stations/{station_id}", response_model=m.StationPublic)
def update_station(station_id: str, station: m.StationUpdate, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    station_db = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station_db:
        raise HTTPException(status_code=404, detail="Station Not Found")
    station_data = station.model_dump(exclude_unset=True)
    station_db.sqlmodel_update(station_data)
    session.commit()
    session.refresh(station_db)
    return station_db

#---Status---

# Add Current/History Status
@app.post("/status/stations", response_model=m.StatusPublic)
def post_status(session: db.SessionDep, status_in: m.StatusIn, x_api_key: Annotated[str, Header()]):
    
    if x_api_key != cfg.scraper_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
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

    session.commit()
    session.refresh(current)
    return current

# Read Current by Station
@app.get("/read/status/stations/{station_id}", response_model=m.StatusPublic)
def read_current_status(session: db.SessionDep, station_id: str, current_user: Annotated[m.User, Depends(require_station_access)]):
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
def post_weather(
    session: db.SessionDep,
    x_api_key: Annotated[str, Header()], 
    w_in: m.WeatherIn,
    
):
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
    