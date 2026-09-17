from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

import models
from database import SessionLocal

from ai.LLM import ask_ai
from ai.qualification import qualify_lead, merge_qualification
from ai.scoring import calculate_lead_score
from ai.schemas import ChatRequest, ChatResponse


app = FastAPI(
    title="Lead Nurturing AI API",
    version="1.0.0"
)


# =========================
# DATABASE SESSION
# =========================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =========================
# ROOT
# =========================

@app.get("/")
def root():
    return {
        "message": "Lead Nurturing AI API is running"
    }


# =========================
# AI CHAT
# =========================

@app.post("/ai/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):

    # =========================
    # 1. CHECK LEAD
    # =========================

    lead = db.query(models.Lead).filter(
        models.Lead.id == request.lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )


    # =========================
    # 2. GET CONVERSATION HISTORY
    # =========================

    history = db.query(models.Conversation).filter(
        models.Conversation.lead_id == request.lead_id
    ).order_by(
        models.Conversation.created_at.asc(),
        models.Conversation.id.asc()
    ).all()


    # =========================
    # 3. REBUILD OLD QUALIFICATION
    # =========================

    qualification = {
        "interest": None,
        "budget": None,
        "timeline": None,
        "requirement": None
    }

    for conversation in history:

        if conversation.role == "user":

            old_data = qualify_lead(
                conversation.message
            )

            qualification = merge_qualification(
                qualification,
                old_data
            )


    # =========================
    # 4. QUALIFY NEW MESSAGE
    # =========================

    new_qualification = qualify_lead(
        request.message
    )

    qualification = merge_qualification(
        qualification,
        new_qualification
    )


    # =========================
    # 5. CALCULATE LEAD SCORE
    # =========================

    scoring = calculate_lead_score(
        qualification
    )


    # =========================
    # 6. GENERATE AI RESPONSE
    # =========================

    try:
        ai_response = ask_ai(
            request.message,
            history
        )

    except RuntimeError as error:

        # Remove any uncommitted DB state
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail="AI service is temporarily unavailable"
        ) from error


    # =========================
    # 7. PREPARE DATABASE CHANGES
    # =========================

    lead.lead_score = scoring["score"]
    lead.lead_temperature = scoring["status"]

    user_message = models.Conversation(
        lead_id=request.lead_id,
        role="user",
        message=request.message
    )

    assistant_message = models.Conversation(
        lead_id=request.lead_id,
        role="assistant",
        message=ai_response
    )

    db.add(user_message)
    db.add(assistant_message)


    # =========================
    # 8. SAVE EVERYTHING
    # =========================

    try:
        db.commit()

    except SQLAlchemyError as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to save AI conversation"
        ) from error


    # =========================
    # 9. REFRESH LEAD
    # =========================

    db.refresh(lead)


    # =========================
    # 10. RETURN RESPONSE
    # =========================

    return {
        "response": ai_response,
        "qualification": qualification,
        "lead_score": scoring["score"],
        "lead_status": scoring["status"]
    }