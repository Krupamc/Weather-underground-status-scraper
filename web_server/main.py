# Web Deployment using sqlite:

from fastapi import FastAPI, Cookie, HTTPException, Query, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
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

app = FastAPI(title="SBB Mesonet Notification System")

# Static and Templates
templates = Jinja2Templates(directory="web_server/templates")
app.mount("/static", StaticFiles(directory="web_server/static"), name="static")

# Security using JWT
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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
    
    except Exception:
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

# Actual Web App:

@app.on_event("startup")
def on_startup():
    db.create_db_table()
    seed_stations()


# Homepage
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"request": request})

# List of Stations
@app.get("/stations", response_class=HTMLResponse)
def stations(request: Request):
    with db.Session(db.engine) as session:
        stations = session.exec(select(m.Station)).all()
    return templates.TemplateResponse(request, "stations.html", context={"request": request, "title": "Weather Stations", "active_page": "stations", "stations": stations})

# Login

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
def register(username: str, password: str, role: str, session: db.SessionDep): #make this require admin later
    db_user = m.User(
        username=username,
        role=role,
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
 
# Access

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
    id = session.exec(select(m.User).where(m.UserAccess.user_id == user_id)).first()
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

# Stations

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
def read_one_station(station_id: str, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_station_access)]):
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station Does not Exist")
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
