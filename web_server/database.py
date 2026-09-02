from sqlmodel import Session, SQLModel, create_engine, text
from typing import Annotated
from fastapi import Depends

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

def migrate_add_column():
    with Session(engine) as session:
        columns = session.exec(text("PRAGMA table_info(station)")).all()
        column_names = [col[1] for col in columns]

        if "hardware" not in column_names:
            session.exec(
                text("ALTER TABLE station ADD COLUMN hardware TEXT NOT NULL DEFAULT 'Unknown'")
            )
            session.commit()

