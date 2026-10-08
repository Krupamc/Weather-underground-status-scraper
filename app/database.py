from sqlmodel import Session, SQLModel, create_engine, text
from typing import Annotated
from fastapi import Depends
import config as cfg

# Engine of the DB:

# SQLite
if cfg.develop == True:
    sqlite_file_name = "app/database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    connect_args = {"check_same_thread": False}
    engine = create_engine(sqlite_url, connect_args=connect_args)

# Postgres
else:
    engine = create_engine(cfg.database_url, pool_pre_ping=True)

# Create table:
def create_db_table():
    SQLModel.metadata.create_all(engine)

# Sessions:
def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

# SQlite migrate
def migrate_add_column():
    with Session(engine) as session:
        columns = session.exec(text("PRAGMA table_info(station)")).all()
        column_names = [col[1] for col in columns]

        if "hardware" not in column_names:
            session.exec(
                text("ALTER TABLE station ADD COLUMN hardware VARCHAR(255) DEFAULT NULL")
            )
            session.commit()

# SQlite delete
def delete_column(table_name: str, column: str):
    with Session(engine) as session:
        columns = session.exec(text("PRAGMA table_info(station)")).all()
        column_names = [col[1] for col in columns]

        if column not in column_names:
            session.exec(
                text(f"ALTER TABLE {table_name} DROP {column} longitude")
            )
            session.commit()

"""
    "elevation": elevation,
    "city": city,
    "state": state,
    "country": country,
    "hardware": hardware
"""

# Add the new station info stuff into tables and into db and into the weather pst route