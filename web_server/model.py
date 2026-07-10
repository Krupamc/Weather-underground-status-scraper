from sqlmodel import Field, SQLModel

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