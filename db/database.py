from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

sql_db_url = "sqlite:///./db/smrtfood.db"
engine = create_engine(sql_db_url,connect_args={"check_same_thread": False})
SessLocal = sessionmaker(autocommit=False,autoflush=False,bind=engine)
Base = declarative_base()