from pydantic import BaseModel, Field
from typing import Optional, Literal


# =========================
# QUALIFICATION RESPONSE
# =========================

class QualificationData(BaseModel):
    interest: Optional[str] = None
    budget: Optional[int] = None
    timeline: Optional[str] = None
    requirement: Optional[str] = None


# =========================
# AI CHAT REQUEST
# =========================

class ChatRequest(BaseModel):
    lead_id: int = Field(gt=0)

    message: str = Field(
        min_length=1,
        max_length=2000
    )


# =========================
# AI CHAT RESPONSE
# =========================

class ChatResponse(BaseModel):
    response: str

    qualification: QualificationData

    lead_score: int = Field(
        ge=0,
        le=100
    )

    lead_status: Literal["COLD", "WARM", "HOT"]