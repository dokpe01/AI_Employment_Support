from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    pw: str
    job: str
    location: str
    url: Optional[str] = None
    skill: Optional[str] = None
    email: EmailStr
    phone: str
    name: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str

    class Config:
        from_attributes = True