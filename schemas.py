from datetime import datetime
from typing import Optional, Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
    field_validator,
)


LeadStatus = Literal[
    "new",
    "contacted",
    "qualified",
    "converted",
    "lost",
]


# =========================================================
# LEAD CREATE
# =========================================================

class LeadCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
    )

    phone: str = Field(
        ...,
        min_length=10,
        max_length=10,
    )

    email: EmailStr

    source: str = Field(
        ...,
        min_length=2,
        max_length=50,
    )

    status: LeadStatus = "new"

    notes: Optional[str] = None

    follow_up_at: Optional[datetime] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str):
        value = value.strip()

        if not value.isdigit():
            raise ValueError(
                "Phone number must contain only digits"
            )

        if len(value) != 10:
            raise ValueError(
                "Phone number must contain exactly 10 digits"
            )

        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str):
        return value.strip()

    @field_validator("source")
    @classmethod
    def clean_source(cls, value: str):
        return value.strip()


# =========================================================
# LEAD UPDATE
# =========================================================

class LeadUpdate(BaseModel):
    name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
    )

    phone: Optional[str] = Field(
        None,
        min_length=10,
        max_length=10,
    )

    email: Optional[EmailStr] = None

    source: Optional[str] = Field(
        None,
        min_length=2,
        max_length=50,
    )

    status: Optional[LeadStatus] = None

    notes: Optional[str] = None

    follow_up_at: Optional[datetime] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        if value is None:
            return value

        value = value.strip()

        if not value.isdigit():
            raise ValueError(
                "Phone number must contain only digits"
            )

        if len(value) != 10:
            raise ValueError(
                "Phone number must contain exactly 10 digits"
            )

        return value


# =========================================================
# FOLLOW-UP UPDATE
# =========================================================

class FollowUpUpdate(BaseModel):
    follow_up_at: Optional[datetime] = None


# =========================================================
# STATUS UPDATE
# =========================================================

class LeadStatusUpdate(BaseModel):
    status: LeadStatus


# =========================================================
# CONVERSATION CREATE
# =========================================================

class ConversationCreate(BaseModel):
    role: Literal["lead", "ai"]

    message: str = Field(
        ...,
        min_length=1,
    )


# =========================================================
# CONVERSATION RESPONSE
# =========================================================

class ConversationResponse(BaseModel):
    id: int
    lead_id: int
    role: str
    message: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# ACTIVITY RESPONSE
# =========================================================

class LeadActivityResponse(BaseModel):
    id: int
    lead_id: int
    activity_type: str
    description: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )