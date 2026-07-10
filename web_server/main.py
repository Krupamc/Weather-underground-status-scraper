# Web Deployment using sqlite:

from fastapi import FastAPI, Depends, HTTPException, Query
from typing import Annotated
from sqlmodel import Field, Session, SQLModel, create_engine, select

app = FastAPI(title="SBB Mesonet Notification System")

# Base Model
class StationBase(SQLModel):
    station_id: str = Field(index=True, unique=True)
    station_name: str = Field(index=True)
    is_in_maintenance: bool = Field(default=False)

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

# Engine of the DB:
sqlite_file_name = "web_server/database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

# Create table:
def create_db_table():
    SQLModel.metadata.create_all(engine)

# Sessions:
def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

# Actual Web App:
@app.on_event("startup")
def on_startup():
    create_db_table()

# Create Station Rows in DB:
@app.post("/stations/", response_model=StationPublic)
def create_station(station: StationCreate, session: SessionDep):
    db_station = Station.model_validate(station)
    session.add(db_station)
    session.commit()
    session.refresh(db_station)
    return db_station

# Read all stations:
@app.get("/stations/", response_model=list[StationPublic])
def read_all_stations(
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)],
    limit: Annotated[int, Query(gt=0, le=100)] = 100,
):

    stations = session.exec(select(Station).offset(offset).limit(limit)).all()
    return stations

# Read station by ID:
@app.get("/stations/{station_id}", response_model=StationPublic)
def read_one_station(station_id: str, session: SessionDep):
    station = session.exec(select(Station).where(Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station Does not Exist")
    return station

# Delete station
@app.delete("/stations/{station_id}")
def delete_station(station_id: str, session: SessionDep):
    station = session.exec(select(Station).where(Station.station_id == station_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="No Station to Delete")
    session.delete(station)
    session.commit()
    return {"ok": True}

# Update Station (MAIN METHOD)
@app.patch("/stations/{station_id}", response_model=StationPublic)
def update_station(station_id: str, station: StationUpdate, session: SessionDep):
    station_db = session.exec(select(Station).where(Station.station_id == station_id)).first()
    if not station_db:
        raise HTTPException(status_code=404, detail="Station Not Found")
    station_data = station.model_dump(exclude_unset=True)
    station_db.sqlmodel_update(station_data)
    session.commit()
    session.refresh(station_db)
    return station_db
