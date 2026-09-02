from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=15)
    email: EmailStr
    source: str = Field(min_length=2, max_length=50)
    status: str = "new"
class LeadUpdate(BaseModel):
    name: str
    phone: str
    email: EmailStr
    source: str
    status: str
    