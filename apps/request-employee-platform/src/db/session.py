from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.settings import get_settings
def get_engine():
    url=get_settings().database_url
    if url.startswith('sqlite:///'):
        Path(url.replace('sqlite:///','')).parent.mkdir(parents=True,exist_ok=True)
        return create_engine(url,connect_args={'check_same_thread':False},pool_pre_ping=True)
    return create_engine(url,pool_pre_ping=True)
SessionLocal=sessionmaker(autocommit=False,autoflush=False,bind=get_engine())
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
