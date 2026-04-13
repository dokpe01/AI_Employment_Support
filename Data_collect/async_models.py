from sqlalchemy import Column, Integer, String, Text

try:
    from async_database import Base
except ImportError:
    from .async_database import Base

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
    url = Column(Text, nullable=False, unique=True)
    source = Column(Text, nullable=False)
    career = Column(Text, nullable=True)
    collected_at = Column(Text, nullable=True)
    content = Column(Text, nullable=True)