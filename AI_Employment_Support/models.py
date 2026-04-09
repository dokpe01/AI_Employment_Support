from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.orm import declarative_base

try:
    from database import Base
except ImportError:
    from .database import Base
Base = declarative_base()

class Enter(Base):
    __tablename__ = "Enter"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    period = Column(String, nullable=False)
    job = Column(Text, nullable=False)
    location = Column(Text, nullable=False)
    work = Column(Text, nullable=True)
    qual = Column(Text, nullable=True)
    prefer = Column(Text, nullable=True)
    procedure = Column(Text, nullable=True)
    docs = Column(Text, nullable=True)
    apply = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    source = Column(Text, nullable=False)
    career = Column(Text, nullable=True)
    collected_at = Column(Text, nullable=True)

class User(Base):
    __tablename__ = "User"

    id = Column(String, primary_key=True, index=True)
    pw = Column(Text, nullable=False)
    job = Column(Text, nullable=False)
    location = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    skill = Column(Text, nullable=True)
    email = Column(Text, nullable=False)
    phone = Column(String(20), nullable=False)
    name = Column(String(50), nullable=False)