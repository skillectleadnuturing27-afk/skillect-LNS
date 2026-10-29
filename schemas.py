from datetime import datetime
from typing import Optional, Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
    field_validator,
)


# =========================================================
# LEAD STATUS
# =========================================================

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

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):

        if value is None:
            return value

        return value.strip()

    @field_validator("source")
    @classmethod
    def clean_source(cls, value):

        if value is None:
            return value

        return value.strip()


# =========================================================
# LEAD RESPONSE
# =========================================================

class LeadResponse(BaseModel):

    # -----------------------------------------------------
    # BASIC LEAD DATA
    # -----------------------------------------------------

    id: int
    name: str
    phone: str
    email: str
    source: str
    status: str

    notes: Optional[str] = None
    follow_up_at: Optional[datetime] = None

    # -----------------------------------------------------
    # PERSON-1 BACKEND / CRM SCORING
    # -----------------------------------------------------

    lead_score: int = 0
    lead_temperature: str = "cold"

    # -----------------------------------------------------
    # PERSON-2 AI QUALIFICATION DATA
    # -----------------------------------------------------

    interest: Optional[str] = None
    budget: Optional[int] = None
    timeline: Optional[str] = None
    requirement: Optional[str] = None

    # -----------------------------------------------------
    # PERSON-2 AI SCORING
    # -----------------------------------------------------

    ai_score: int = 0
    ai_temperature: str = "cold"

    # -----------------------------------------------------
    # TIMESTAMPS
    # -----------------------------------------------------

    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# FOLLOW-UP UPDATE
# =========================================================

class FollowUpUpdate(BaseModel):
    notes: Optional[str] = None
    follow_up_at: Optional[datetime] = None


# =========================================================
# STATUS UPDATE
# =========================================================

class LeadStatusUpdate(BaseModel):
    status: LeadStatus


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


# =========================================================
# CONVERSATION CREATE
# =========================================================

class ConversationCreate(BaseModel):
    role: Literal[
        "lead",
        "ai",
    ]

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
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
# CONVERSATION UPDATE
# =========================================================

class ConversationUpdate(BaseModel):
    role: Optional[
        Literal[
            "lead",
            "ai",
        ]
    ] = None

    message: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )


# =========================================================
# LEAD LIST RESPONSE
# =========================================================

class LeadListResponse(BaseModel):
    count: int
    returned: int
    skip: int
    limit: int
    leads: list[LeadResponse]


# =========================================================
# HOT LEADS RESPONSE
# =========================================================

class HotLeadsResponse(BaseModel):
    count: int
    leads: list[LeadResponse]


# =========================================================
# FOLLOW-UP LEADS RESPONSE
# =========================================================

class FollowUpLeadsResponse(BaseModel):
    count: int
    leads: list[LeadResponse]


# =========================================================
# DASHBOARD RECENT RESPONSE
# =========================================================

class DashboardRecentResponse(BaseModel):
    recent_leads: list[LeadResponse]
    recent_activities: list[LeadActivityResponse]


# =========================================================
# LEAD FULL DETAILS RESPONSE
# =========================================================

class LeadFullDetailsResponse(BaseModel):
    lead: LeadResponse
    activities: list[LeadActivityResponse]
    conversations: list[ConversationResponse]


# =========================================================
# CONVERSATION STATS RESPONSE
# =========================================================

class ConversationStatsResponse(BaseModel):
    lead_id: int
    total_conversations: int
    lead_messages: int
    ai_messages: int


# =========================================================
# DELETE CONVERSATION RESPONSE
# =========================================================

class DeleteConversationResponse(BaseModel):
    message: str
    conversation_id: int


# =========================================================
# DELETE LEAD RESPONSE
# =========================================================

class DeleteLeadResponse(BaseModel):
    message: str


# =========================================================
# DASHBOARD SUMMARY RESPONSE
# =========================================================

class DashboardSummaryResponse(BaseModel):
    total_leads: int
    hot_leads: int
    qualified_leads: int
    converted_leads: int
    todays_followups: int


# =========================================================
# LEAD STATS RESPONSE
# =========================================================

class LeadStatusStats(BaseModel):
    new: int
    contacted: int
    qualified: int
    converted: int
    lost: int


class LeadTemperatureStats(BaseModel):
    hot: int
    warm: int
    cold: int


class LeadStatsResponse(BaseModel):
    total: int
    status: LeadStatusStats
    temperature: LeadTemperatureStats


# =========================================================
# LEAD ALERTS
# =========================================================

LeadAlertStatus = Literal["active", "acknowledged", "resolved"]


class LeadAlertStatusUpdate(BaseModel):
    status: LeadAlertStatus


class LeadAlertLeadSummary(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    source: str
    lead_score: int
    lead_temperature: str
    ai_score: int
    ai_temperature: str

    model_config = ConfigDict(from_attributes=True)


class LeadAlertResponse(BaseModel):
    id: int
    lead_id: int
    alert_type: str
    reason: str
    score: int
    qualification_summary: str
    status: LeadAlertStatus
    created_at: datetime
    lead: LeadAlertLeadSummary

    model_config = ConfigDict(from_attributes=True)