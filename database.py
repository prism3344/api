from sqlmodel import SQLModel, create_engine, Session
import os
from models import *  
DB_FILE = "./complex.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# create folder if needed
os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

def init_db():
# ensure models are imported
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
