import src.db.models  # noqa
from src.db.base import Base
from src.db.session import get_engine
from src.db.migrations import migrate_schema
def init_db():
    engine=get_engine()
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    Base.metadata.create_all(bind=engine)
