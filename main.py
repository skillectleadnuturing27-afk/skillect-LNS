from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Query,
)

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from datetime import (
    datetime,
    timezone,
    timedelta,
)

from typing import Optional

import models
import schemas

from database import (
    engine,
    SessionLocal,
)


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

models.Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Skillect Lead Nurturing System API",
    version="1.0.0",
    description="Backend API for the Skillect Lead Nurturing System",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE SESSION
# =========================================================

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =========================================================
# HELPER - LEAD SCORE
# =========================================================

def calculate_lead_score(lead):

    score = 0

    status_scores = {
        "new": 10,
        "contacted": 30,
        "qualified": 60,
        "converted": 100,
        "lost": 0,
    }

    score += status_scores.get(
        str(lead.status).lower(),
        0,
    )

    source = (
        str(lead.source).lower()
        if lead.source
        else ""
    )

    if source == "website":
        score += 10

    elif source == "instagram":
        score += 5

    if lead.follow_up_at:
        score += 10

    score = min(score, 100)

    return score


# =========================================================
# HELPER - LEAD TEMPERATURE
# =========================================================

def calculate_lead_temperature(score):

    if score >= 70:
        return "hot"

    elif score >= 40:
        return "warm"

    return "cold"


# =========================================================
# HELPER - UPDATE SCORE
# =========================================================

def update_lead_score(lead):

    score = calculate_lead_score(lead)

    lead.lead_score = score

    lead.lead_temperature = (
        calculate_lead_temperature(score)
    )

    return lead


# =========================================================
# HELPER - CREATE ACTIVITY
# =========================================================

def create_activity(
    db: Session,
    lead_id: int,
    activity_type: str,
    description: str,
):

    activity = models.LeadActivity(
        lead_id=lead_id,
        activity_type=activity_type,
        description=description,
    )

    db.add(activity)

    return activity


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "message":
        "Skillect Lead Nurturing System API is running"
    }


# =========================================================
# DASHBOARD SUMMARY
# =========================================================

@app.get("/dashboard/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
):

    total_leads = (
        db.query(models.Lead)
        .count()
    )

    hot_leads = (
        db.query(models.Lead)
        .filter(
            models.Lead.lead_temperature == "hot"
        )
        .count()
    )

    qualified_leads = (
        db.query(models.Lead)
        .filter(
            models.Lead.status == "qualified"
        )
        .count()
    )

    converted_leads = (
        db.query(models.Lead)
        .filter(
            models.Lead.status == "converted"
        )
        .count()
    )

    now = datetime.now(timezone.utc)

    start_today = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_today = (
        start_today
        + timedelta(days=1)
    )

    todays_followups = (
        db.query(models.Lead)
        .filter(
            models.Lead.follow_up_at.isnot(None),
            models.Lead.follow_up_at >= start_today,
            models.Lead.follow_up_at < end_today,
        )
        .count()
    )

    return {
        "total_leads": total_leads,
        "hot_leads": hot_leads,
        "qualified_leads": qualified_leads,
        "converted_leads": converted_leads,
        "todays_followups": todays_followups,
    }


# =========================================================
# DASHBOARD RECENT
# =========================================================

@app.get("/dashboard/recent")
def dashboard_recent(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
):

    recent_leads = (
        db.query(models.Lead)
        .order_by(
            models.Lead.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    recent_activities = (
        db.query(models.LeadActivity)
        .order_by(
            models.LeadActivity.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    return {
        "recent_leads": recent_leads,
        "recent_activities": recent_activities,
    }


# =========================================================
# LEAD STATISTICS
# =========================================================

@app.get("/leads/stats")
def lead_statistics(
    db: Session = Depends(get_db),
):

    total = (
        db.query(models.Lead)
        .count()
    )

    new = (
        db.query(models.Lead)
        .filter(
            models.Lead.status == "new"
        )
        .count()
    )

    contacted = (
        db.query(models.Lead)
        .filter(
            models.Lead.status == "contacted"
        )
        .count()
    )

    qualified = (
        db.query(models.Lead)
        .filter(
            models.Lead.status == "qualified"
        )
        .count()
    )

    converted = (
        db.query(models.Lead)
        .filter(
            models.Lead.status == "converted"
        )
        .count()
    )

    lost = (
        db.query(models.Lead)
        .filter(
            models.Lead.status == "lost"
        )
        .count()
    )

    hot = (
        db.query(models.Lead)
        .filter(
            models.Lead.lead_temperature == "hot"
        )
        .count()
    )

    warm = (
        db.query(models.Lead)
        .filter(
            models.Lead.lead_temperature == "warm"
        )
        .count()
    )

    cold = (
        db.query(models.Lead)
        .filter(
            models.Lead.lead_temperature == "cold"
        )
        .count()
    )

    return {
        "total": total,
        "status": {
            "new": new,
            "contacted": contacted,
            "qualified": qualified,
            "converted": converted,
            "lost": lost,
        },
        "temperature": {
            "hot": hot,
            "warm": warm,
            "cold": cold,
        },
    }


# =========================================================
# HOT LEADS
# =========================================================

@app.get("/leads/hot")
def get_hot_leads(
    db: Session = Depends(get_db),
):

    leads = (
        db.query(models.Lead)
        .filter(
            models.Lead.lead_temperature == "hot"
        )
        .order_by(
            models.Lead.lead_score.desc()
        )
        .all()
    )

    return {
        "count": len(leads),
        "leads": leads,
    }


# =========================================================
# ALL FOLLOW-UPS
# =========================================================

@app.get("/leads/follow-ups")
def get_followups(
    db: Session = Depends(get_db),
):

    leads = (
        db.query(models.Lead)
        .filter(
            models.Lead.follow_up_at.isnot(None)
        )
        .order_by(
            models.Lead.follow_up_at.asc()
        )
        .all()
    )

    return {
        "count": len(leads),
        "leads": leads,
    }


# =========================================================
# OVERDUE FOLLOW-UPS
# =========================================================

@app.get("/leads/follow-ups/overdue")
def overdue_followups(
    db: Session = Depends(get_db),
):

    now = datetime.now(timezone.utc)

    leads = (
        db.query(models.Lead)
        .filter(
            models.Lead.follow_up_at.isnot(None),
            models.Lead.follow_up_at < now,
        )
        .order_by(
            models.Lead.follow_up_at.asc()
        )
        .all()
    )

    return {
        "count": len(leads),
        "leads": leads,
    }


# =========================================================
# TODAY FOLLOW-UPS
# =========================================================

@app.get("/leads/follow-ups/today")
def today_followups(
    db: Session = Depends(get_db),
):

    now = datetime.now(timezone.utc)

    start_today = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_today = (
        start_today
        + timedelta(days=1)
    )

    leads = (
        db.query(models.Lead)
        .filter(
            models.Lead.follow_up_at.isnot(None),
            models.Lead.follow_up_at >= start_today,
            models.Lead.follow_up_at < end_today,
        )
        .order_by(
            models.Lead.follow_up_at.asc()
        )
        .all()
    )

    return {
        "count": len(leads),
        "leads": leads,
    }


# =========================================================
# CREATE LEAD
# =========================================================

@app.post("/leads")
def create_lead(
    lead_data: schemas.LeadCreate,
    db: Session = Depends(get_db),
):

    existing_lead = (
        db.query(models.Lead)
        .filter(
            models.Lead.email
            == str(lead_data.email)
        )
        .first()
    )

    if existing_lead:

        raise HTTPException(
            status_code=400,
            detail="A lead with this email already exists",
        )

    lead = models.Lead(
        name=lead_data.name,
        phone=lead_data.phone,
        email=str(lead_data.email),
        source=lead_data.source,
        status=lead_data.status,
        notes=lead_data.notes,
        follow_up_at=lead_data.follow_up_at,
    )

    update_lead_score(lead)

    try:

        db.add(lead)

        db.flush()

        create_activity(
            db=db,
            lead_id=lead.id,
            activity_type="lead_created",
            description=(
                f"Lead '{lead.name}' was created"
            ),
        )

        db.commit()

        db.refresh(lead)

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Lead could not be created",
        )

    return lead


# =========================================================
# GET ALL LEADS
# ADVANCED FILTER + SORT + PAGINATION
# =========================================================

@app.get("/leads")
def get_leads(

    search: Optional[str] = Query(
        default=None
    ),

    status: Optional[str] = Query(
        default=None
    ),

    source: Optional[str] = Query(
        default=None
    ),

    min_score: Optional[int] = Query(
        default=None,
        ge=0,
        le=100,
    ),

    max_score: Optional[int] = Query(
        default=None,
        ge=0,
        le=100,
    ),

    temperature: Optional[str] = Query(
        default=None
    ),

    sort_by: str = Query(
        default="created_at"
    ),

    order: str = Query(
        default="desc"
    ),

    skip: int = Query(
        default=0,
        ge=0,
    ),

    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),

    db: Session = Depends(get_db),
):

    query = db.query(models.Lead)


    # =====================================================
    # SEARCH
    # =====================================================

    if search:

        search_value = f"%{search}%"

        query = query.filter(
            or_(
                models.Lead.name.ilike(
                    search_value
                ),
                models.Lead.email.ilike(
                    search_value
                ),
                models.Lead.phone.ilike(
                    search_value
                ),
            )
        )


    # =====================================================
    # STATUS FILTER
    # =====================================================

    if status:

        query = query.filter(
            models.Lead.status == status
        )


    # =====================================================
    # SOURCE FILTER
    # =====================================================

    if source:

        query = query.filter(
            models.Lead.source == source
        )


    # =====================================================
    # MIN SCORE FILTER
    # =====================================================

    if min_score is not None:

        query = query.filter(
            models.Lead.lead_score
            >= min_score
        )


    # =====================================================
    # MAX SCORE FILTER
    # =====================================================

    if max_score is not None:

        query = query.filter(
            models.Lead.lead_score
            <= max_score
        )


    # =====================================================
    # TEMPERATURE FILTER
    # =====================================================

    if temperature:

        query = query.filter(
            models.Lead.lead_temperature
            == temperature
        )


    # =====================================================
    # VALID SORT FIELDS
    # =====================================================

    sort_fields = {

        "id":
            models.Lead.id,

        "name":
            models.Lead.name,

        "status":
            models.Lead.status,

        "source":
            models.Lead.source,

        "lead_score":
            models.Lead.lead_score,

        "lead_temperature":
            models.Lead.lead_temperature,

        "created_at":
            models.Lead.created_at,

        "updated_at":
            models.Lead.updated_at,

        "follow_up_at":
            models.Lead.follow_up_at,
    }


    sort_column = sort_fields.get(
        sort_by,
        models.Lead.created_at,
    )


    # =====================================================
    # SORT ORDER
    # =====================================================

    if order.lower() == "asc":

        query = query.order_by(
            sort_column.asc()
        )

    else:

        query = query.order_by(
            sort_column.desc()
        )


    # =====================================================
    # TOTAL COUNT BEFORE PAGINATION
    # =====================================================

    total_count = query.count()


    # =====================================================
    # PAGINATION
    # =====================================================

    leads = (
        query
        .offset(skip)
        .limit(limit)
        .all()
    )


    return {

        "count": total_count,

        "returned": len(leads),

        "skip": skip,

        "limit": limit,

        "leads": leads,
    }


# GET ONE LEAD
# =====================================================

@app.get(
    "/leads/{lead_id}",
    responses={
        404: {
            "description": "Lead not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Lead not found"
                    }
                }
            },
        }
    },
)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
):
    lead = (
        db.query(models.Lead)
        .filter(models.Lead.id == lead_id)
        .first()
    )

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    return lead


# =========================================================
# UPDATE LEAD
# =========================================================

@app.put("/leads/{lead_id}")
def update_lead(
    lead_id: int,
    lead_data: schemas.LeadUpdate,
    db: Session = Depends(get_db),
):

    lead = (
        db.query(models.Lead)
        .filter(
            models.Lead.id == lead_id
        )
        .first()
    )

    if not lead:

        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    update_data = (
        lead_data.model_dump(
            exclude_unset=True
        )
    )

    old_status = lead.status
    old_notes = lead.notes
    old_followup = lead.follow_up_at

    if "email" in update_data:

        update_data["email"] = str(
            update_data["email"]
        )

        existing_email = (
            db.query(models.Lead)
            .filter(
                models.Lead.email
                == update_data["email"],
                models.Lead.id
                != lead_id,
            )
            .first()
        )

        if existing_email:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Another lead already uses this email"
                ),
            )

    for key, value in update_data.items():

        setattr(
            lead,
            key,
            value,
        )

    update_lead_score(lead)

    if (
        "status" in update_data
        and old_status != lead.status
    ):

        create_activity(
            db=db,
            lead_id=lead.id,
            activity_type="status_changed",
            description=(
                f"Status changed from "
                f"'{old_status}' to "
                f"'{lead.status}'"
            ),
        )

    if (
        "notes" in update_data
        and old_notes != lead.notes
    ):

        create_activity(
            db=db,
            lead_id=lead.id,
            activity_type="notes_updated",
            description="Lead notes were updated",
        )

    if (
        "follow_up_at" in update_data
        and old_followup
        != lead.follow_up_at
    ):

        create_activity(
            db=db,
            lead_id=lead.id,
            activity_type="follow_up_updated",
            description=(
                "Lead follow-up date/time was updated"
            ),
        )

    try:

        db.commit()

        db.refresh(lead)

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Lead could not be updated",
        )

    return lead


# =========================================================
# DELETE LEAD
# =========================================================

@app.delete("/leads/{lead_id}")
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db),
):

    lead = (
        db.query(models.Lead)
        .filter(
            models.Lead.id == lead_id
        )
        .first()
    )

    if not lead:

        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    lead_name = lead.name

    db.delete(lead)

    db.commit()

    return {
        "message":
        f"Lead '{lead_name}' deleted successfully"
    }


# =========================================================
# UPDATE FOLLOW-UP
# =========================================================

@app.patch("/leads/{lead_id}/follow-up")
def update_followup(
    lead_id: int,
    followup: schemas.FollowUpUpdate,
    db: Session = Depends(get_db),
):

    lead = (
        db.query(models.Lead)
        .filter(
            models.Lead.id == lead_id
        )
        .first()
    )

    if not lead:

        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    lead.follow_up_at = (
        followup.follow_up_at
    )

    update_lead_score(lead)

    create_activity(
        db=db,
        lead_id=lead.id,
        activity_type="follow_up_updated",
        description=(
            "Follow-up date/time updated to "
            f"{lead.follow_up_at}"
        ),
    )

    db.commit()

    db.refresh(lead)

    return lead


# =========================================================
# UPDATE STATUS
# =========================================================

@app.patch("/leads/{lead_id}/status")
def update_status(
    lead_id: int,
    status_data: schemas.LeadStatusUpdate,
    db: Session = Depends(get_db),
):

    lead = (
        db.query(models.Lead)
        .filter(
            models.Lead.id == lead_id
        )
        .first()
    )

    if not lead:

        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    old_status = lead.status

    lead.status = (
        status_data.status
    )

    update_lead_score(lead)

    create_activity(
        db=db,
        lead_id=lead.id,
        activity_type="status_changed",
        description=(
            f"Status changed from "
            f"'{old_status}' to "
            f"'{lead.status}'"
        ),
    )

    db.commit()

    db.refresh(lead)

    return lead


# =========================================================
# LEAD ACTIVITIES
# =========================================================

@app.get(
    "/leads/{lead_id}/activities",
    response_model=list[
        schemas.LeadActivityResponse
    ],
)
def get_lead_activities(
    lead_id: int,
    db: Session = Depends(get_db),
):

    lead = (
        db.query(models.Lead)
        .filter(
            models.Lead.id == lead_id
        )
        .first()
    )

    if not lead:

        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    activities = (
        db.query(models.LeadActivity)
        .filter(
            models.LeadActivity.lead_id
            == lead_id
        )
        .order_by(
            models.LeadActivity.created_at.desc()
        )
        .all()
    )

    return activities


# =========================================================
# CREATE CONVERSATION
# =========================================================

    lead = (
        db.query(models.Lead)
        .filter(
            models.Lead.id == lead_id
        )
        .first()
    )

    if not lead:

        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    new_message = (
        models.Conversation(
            lead_id=lead_id,
            role=conversation.role,
            message=conversation.message,
        )
    )

    db.add(new_message)

    db.commit()

    db.refresh(new_message)

    return new_message

# =========================================================
# FULL LEAD DETAILS
# =========================================================

@app.get("/leads/{lead_id}/full-details")
def get_full_lead_details(
    lead_id: int,
    db: Session = Depends(get_db),
):

    lead = (
        db.query(models.Lead)
        .filter(
            models.Lead.id == lead_id
        )
        .first()
    )

    if not lead:

        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    activities = (
        db.query(models.LeadActivity)
        .filter(
            models.LeadActivity.lead_id
            == lead_id
        )
        .order_by(
            models.LeadActivity.created_at.desc()
        )
        .all()
    )

    conversations = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.lead_id
            == lead_id
        )
        .order_by(
            models.Conversation.created_at.asc()
        )
        .all()
    )

    return {
        "lead": lead,
        "activities": activities,
        "conversations": conversations,
    }

# =========================
# CREATE CONVERSATION
# =========================

@app.post(
    "/leads/{lead_id}/conversations",
    response_model=schemas.ConversationResponse
)
def create_conversation(
    lead_id: int,
    conversation: schemas.ConversationCreate,
    db: Session = Depends(get_db)
):
    # Check whether the lead exists
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    # Create conversation message
    new_conversation = models.Conversation(
        lead_id=lead_id,
        role=conversation.role,
        message=conversation.message
    )

    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)

    return new_conversation

# =========================
# GET LEAD CONVERSATIONS
# =========================

@app.get(
    "/leads/{lead_id}/conversations",
    response_model=list[schemas.ConversationResponse]
)
def get_lead_conversations(
    lead_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    # Check whether lead exists
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    # Get conversations with pagination
    conversations = (
    db.query(models.Conversation)
    .filter(models.Conversation.lead_id == lead_id)
    .order_by(models.Conversation.created_at.asc())
    .offset(offset)
    .limit(limit)
    .all()
)

    return conversations

# =========================
# DELETE CONVERSATION
# =========================

@app.delete("/leads/{lead_id}/conversations/{conversation_id}")
def delete_conversation(
    lead_id: int,
    conversation_id: int,
    db: Session = Depends(get_db)
):
    # Check whether the lead exists
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    # Find the conversation belonging to this lead
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.lead_id == lead_id
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )

    # Delete conversation
    db.delete(conversation)
    db.commit()

    return {
        "message": "Conversation deleted successfully",
        "conversation_id": conversation_id
    }

# =========================
# UPDATE CONVERSATION
# =========================

@app.patch(
    "/leads/{lead_id}/conversations/{conversation_id}",
    response_model=schemas.ConversationResponse
)
def update_conversation(
    lead_id: int,
    conversation_id: int,
    conversation_update: schemas.ConversationUpdate,
    db: Session = Depends(get_db)
):
    # Check whether the lead exists
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    # Find conversation belonging to this lead
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.lead_id == lead_id
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )

    # Update only provided fields
    if conversation_update.role is not None:
        conversation.role = conversation_update.role

    if conversation_update.message is not None:
        conversation.message = conversation_update.message

    db.commit()
    db.refresh(conversation)

    return conversation

# =========================
# CONVERSATION STATISTICS
# =========================

@app.get("/leads/{lead_id}/conversations/stats")
def get_conversation_stats(
    lead_id: int,
    db: Session = Depends(get_db)
):
    # Check if lead exists
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    # Get all conversations for this lead
    conversations = db.query(models.Conversation).filter(
        models.Conversation.lead_id == lead_id
    ).all()

    total_conversations = len(conversations)

    lead_messages = sum(
        1 for conversation in conversations
        if conversation.role == "lead"
    )

    ai_messages = sum(
        1 for conversation in conversations
        if conversation.role == "ai"
    )

    return {
        "lead_id": lead_id,
        "total_conversations": total_conversations,
        "lead_messages": lead_messages,
        "ai_messages": ai_messages
    }

# =========================
# GET LATEST CONVERSATION
# =========================

@app.get("/leads/{lead_id}/conversations/latest")
def get_latest_conversation(
    lead_id: int,
    db: Session = Depends(get_db)
):
    # Check if lead exists
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    # Get latest conversation
    conversation = (
        db.query(models.Conversation)
        .filter(models.Conversation.lead_id == lead_id)
        .order_by(models.Conversation.created_at.desc())
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="No conversations found for this lead"
        )

    return conversation

# =========================
# SEARCH CONVERSATIONS
# =========================

@app.get("/leads/{lead_id}/conversations/search")
def search_conversations(
    lead_id: int,
    query: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    # Check if lead exists
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    # Search conversation messages
    conversations = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.lead_id == lead_id,
            models.Conversation.message.ilike(f"%{query}%")
        )
        .order_by(models.Conversation.created_at.desc())
        .all()
    )

    return {
        "lead_id": lead_id,
        "query": query,
        "count": len(conversations),
        "conversations": conversations
    }



