# Web Deployment using sqlite:

from fastapi import FastAPI, HTTPException, Query
from typing import Annotated
from sqlmodel import select
import database as db
import model as m
import web_config as cfg

app = FastAPI(title="SBB Mesonet Notification System")

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

# Actual Web App:
@app.on_event("startup")
def on_startup():
    db.create_db_table()
    seed_stations()

# Create Station Rows in DB:
@app.post("/stations/", response_model=m.StationPublic)
def create_station(station: m.StationCreate, session: db.SessionDep):
    db_station = m.Station.model_validate(station)
    session.add(db_station)
    session.commit()
    session.refresh(db_station)
    return db_station

# Read all stations:
@app.get("/stations/", response_model=list[m.StationPublic])
def read_all_stations(
    session: db.SessionDep,
    offset: Annotated[int, Query(ge=0)],
    limit: Annotated[int, Query(gt=0, le=100)] = 100,
):

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
def delete_station(station_id: str, session: db.SessionDep):
    station = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="No Station to Delete")
    session.delete(station)
    session.commit()
    return {"ok": True}

# Update Station (MAIN METHOD)
@app.patch("/stations/{station_id}", response_model=m.StationPublic)
def update_station(station_id: str, station: m.StationUpdate, session: db.SessionDep):
    station_db = session.exec(select(m.Station).where(m.Station.station_id == station_id)).first()
    if not station_db:
        raise HTTPException(status_code=404, detail="Station Not Found")
    station_data = station.model_dump(exclude_unset=True)
    station_db.sqlmodel_update(station_data)
    session.commit()
    session.refresh(station_db)
    return station_db
