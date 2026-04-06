from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus

load_dotenv(encoding="utf-8")
DB = os.getenv("DB")
DB_ID = os.getenv("DB_ID")
DB_PW = quote_plus(os.getenv("DB_PW"))
Port = os.getenv("Port")

SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_ID}:{DB_PW}@localhost:5432/{DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    try:
        connection = engine.connect()
        print("PostgreSQL Connect")
        connection.close()
    except Exception as e:
        print(e)