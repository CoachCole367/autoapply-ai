from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import config
from .models import Base


def make_engine(url):
    return create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})


def initialize():
    engine = make_engine(config().database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
