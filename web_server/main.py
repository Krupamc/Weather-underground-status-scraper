# Web Deployment using sqlite:

from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
from sqlmodel import select
import database as db
import model as m
import web_config as cfg
import security as s
import jwt
from jwt import InvalidTokenError

app = FastAPI(title="SBB Mesonet Notification System")

# Security using JWT
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Make sure only stations in the config are in server:
def seed_stations(): # perhaps add auto delete if not in dict?
    with db.Session(db.engine) as session:
        db_station = session.exec(select(m.Station)).all()
        
        db_ids = {station.station_id for station in db_station}
        config_ids = set(cfg.stations.keys())
        
        # If a station is in the config but not the db, add it
        for station_id, station_name in cfg.stations.items():
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
def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: db.SessionDep):
    
    # Make Exception
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})

    try: # When username != right, raise exception
        payload = jwt.decode(token, cfg.secret_key, algorithms=[cfg.algorithm])
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
    if current_user != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Enough Permissions")
    return current_user

# Actual Web App:

@app.on_event("startup")
def on_startup():
    db.create_db_table()
    seed_stations()

# Login

# Real login
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
@app.get("/login/")
def load_login():
    return {"message": "Login"}

@app.get("/register")
def load_register():
    return {"message": "Register Man"}

@app.post("/register/")
def register(username: str, password: str, role: str, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
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

# Create Station Rows in DB:
@app.post("/stations/", response_model=m.StationPublic)
def create_station(station: m.StationCreate, session: db.SessionDep, current_user: Annotated[m.User, Depends(require_admin)]):
    db_station = m.Station.model_validate(station)
    session.add(db_station)
    session.commit()
    session.refresh(db_station)
    return db_station

# Read all stations:
@app.get("/stations/", response_model=list[m.StationPublic])
def read_all_stations(session: db.SessionDep, offset: Annotated[int, Query(ge=0)], limit: Annotated[int, Query(gt=0, le=100)] = 100,):
    stations = session.exec(select(m.Station).offset(offset).limit(limit)).all()
    return stations

# Read station by ID:
@app.get("/stations/{station_id}", response_model=m.StationPublic)
def read_one_station(station_id: str, session: db.SessionDep):
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station Does not Exist")
    return station

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
