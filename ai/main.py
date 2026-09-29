import time

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

import models
from database import SessionLocal

from ai.LLM import ask_ai
from ai.router import route_message
from ai.qualification import qualify_lead, merge_qualification
from ai.scoring import calculate_lead_score
from ai.schemas import ChatRequest, ChatResponse


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Lead Nurturing AI API",
    version="1.0.0"
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
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "message": "Lead Nurturing AI API is running"
    }


# =========================================================
# AI CHAT
# =========================================================

@app.post(
    "/ai/chat",
    response_model=ChatResponse
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):

    # =====================================================
    # START TOTAL TIMER
    # =====================================================

    total_start = time.perf_counter()

    print("\n", flush=True)
    print("=" * 50, flush=True)
    print("AI REQUEST STARTED", flush=True)
    print("=" * 50, flush=True)

    print(
        f"Lead ID: {request.lead_id}",
        flush=True
    )

    print(
        f"Message: {request.message}",
        flush=True
    )


    # =====================================================
    # 1. CHECK LEAD
    # =====================================================

    db_start = time.perf_counter()

    lead = (
        db.query(models.Lead)
        .filter(
            models.Lead.id == request.lead_id
        )
        .first()
    )

    db_lookup_time = (
        time.perf_counter() - db_start
    )

    print(
        f"LEAD DB LOOKUP: "
        f"{db_lookup_time:.3f} seconds",
        flush=True
    )

    if not lead:

        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )


    # =====================================================
    # 2. GET CONVERSATION HISTORY
    # =====================================================

    history_start = time.perf_counter()

    history = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.lead_id
            == request.lead_id
        )
        .order_by(
            models.Conversation.created_at.asc(),
            models.Conversation.id.asc()
        )
        .all()
    )

    history_time = (
        time.perf_counter() - history_start
    )

    print(
        f"HISTORY LOAD: "
        f"{history_time:.3f} seconds",
        flush=True
    )

    print(
        f"HISTORY MESSAGES: {len(history)}",
        flush=True
    )


    # =====================================================
    # 3. REBUILD OLD QUALIFICATION
    # =====================================================

    qualification_start = time.perf_counter()

    qualification = {
        "interest": None,
        "budget": None,
        "timeline": None,
        "requirement": None
    }

    for conversation in history:

        # Only lead messages are used
        # for qualification extraction.
        if conversation.role == "lead":

            old_data = qualify_lead(
                conversation.message
            )

            qualification = merge_qualification(
                qualification,
                old_data
            )


    # =====================================================
    # 4. QUALIFY NEW MESSAGE
    # =====================================================

    new_qualification = qualify_lead(
        request.message
    )

    qualification = merge_qualification(
        qualification,
        new_qualification
    )

    qualification_time = (
        time.perf_counter()
        - qualification_start
    )

    print(
        f"QUALIFICATION: "
        f"{qualification_time:.3f} seconds",
        flush=True
    )

    print(
        f"QUALIFICATION DATA: "
        f"{qualification}",
        flush=True
    )


    # =====================================================
    # 5. CALCULATE AI SCORE
    # =====================================================

    scoring_start = time.perf_counter()

    scoring = calculate_lead_score(
        qualification
    )

    scoring_time = (
        time.perf_counter()
        - scoring_start
    )

    print(
        f"AI SCORING: "
        f"{scoring_time:.3f} seconds",
        flush=True
    )

    print(
        f"AI SCORE: "
        f"{scoring['score']}",
        flush=True
    )

    print(
        f"AI TEMPERATURE: "
        f"{scoring['status']}",
        flush=True
    )


    # =====================================================
    # 6. FAST ROUTER
    # =====================================================

    router_start = time.perf_counter()

    direct_response = route_message(
        request.message
    )

    router_time = (
        time.perf_counter()
        - router_start
    )

    print(
        f"ROUTER CHECK: "
        f"{router_time:.3f} seconds",
        flush=True
    )


    # =====================================================
    # DIRECT RESPONSE
    # =====================================================

    if direct_response is not None:

        ai_response = direct_response

        print(
            "RESPONSE PATH: FAST ROUTER",
            flush=True
        )

        print(
            "OLLAMA USED: NO",
            flush=True
        )

        ai_generation_time = 0.0


    # =====================================================
    # 7. COMPLEX MESSAGE
    # RAG + OLLAMA
    # =====================================================

    else:

        print(
            "RESPONSE PATH: RAG + OLLAMA",
            flush=True
        )

        print(
            "OLLAMA USED: YES",
            flush=True
        )

        ai_start = time.perf_counter()

        try:

            ai_response = ask_ai(
                request.message,
                history,
                qualification
            )

        except RuntimeError as error:

            db.rollback()

            raise HTTPException(
                status_code=503,
                detail=(
                    "AI service is temporarily "
                    "unavailable"
                )
            ) from error

        ai_generation_time = (
            time.perf_counter()
            - ai_start
        )

        print(
            f"AI / OLLAMA RESPONSE TIME: "
            f"{ai_generation_time:.3f} seconds",
            flush=True
        )


    # =====================================================
    # 8. PREPARE DATABASE CHANGES
    # =====================================================

    # -----------------------------------------------------
    # AI QUALIFICATION DATA
    # -----------------------------------------------------

    lead.interest = qualification.get(
        "interest"
    )

    lead.budget = qualification.get(
        "budget"
    )

    lead.timeline = qualification.get(
        "timeline"
    )

    lead.requirement = qualification.get(
        "requirement"
    )


    # -----------------------------------------------------
    # AI SCORE
    # -----------------------------------------------------

    lead.ai_score = scoring["score"]

    lead.ai_temperature = scoring["status"]


    # -----------------------------------------------------
    # IMPORTANT
    # -----------------------------------------------------
    # Backend fields are NOT changed here:
    #
    # lead.lead_score
    # lead.lead_temperature
    #
    # Those belong to Person-1 backend scoring.
    # -----------------------------------------------------

    print(
        f"SAVING AI QUALIFICATION: "
        f"{qualification}",
        flush=True
    )

    print(
        f"SAVING AI SCORE: "
        f"{lead.ai_score}",
        flush=True
    )

    print(
        f"SAVING AI TEMPERATURE: "
        f"{lead.ai_temperature}",
        flush=True
    )


    # =====================================================
    # SAVE LEAD MESSAGE
    # =====================================================

    user_message = models.Conversation(
        lead_id=request.lead_id,
        role="lead",
        message=request.message
    )


    # =====================================================
    # SAVE AI MESSAGE
    # =====================================================

    assistant_message = models.Conversation(
        lead_id=request.lead_id,
        role="ai",
        message=ai_response
    )

    db.add(user_message)
    db.add(assistant_message)


    # =====================================================
    # 9. SAVE EVERYTHING
    # =====================================================

    commit_start = time.perf_counter()

    try:

        db.commit()

    except SQLAlchemyError as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to save AI conversation"
        ) from error

    commit_time = (
        time.perf_counter()
        - commit_start
    )

    print(
        f"DATABASE COMMIT: "
        f"{commit_time:.3f} seconds",
        flush=True
    )


    # =====================================================
    # 10. REFRESH LEAD
    # =====================================================

    refresh_start = time.perf_counter()

    db.refresh(lead)

    refresh_time = (
        time.perf_counter()
        - refresh_start
    )

    print(
        f"DATABASE REFRESH: "
        f"{refresh_time:.3f} seconds",
        flush=True
    )

    print(
        f"DB INTEREST AFTER SAVE: "
        f"{lead.interest}",
        flush=True
    )

    print(
        f"DB BUDGET AFTER SAVE: "
        f"{lead.budget}",
        flush=True
    )

    print(
        f"DB TIMELINE AFTER SAVE: "
        f"{lead.timeline}",
        flush=True
    )

    print(
        f"DB REQUIREMENT AFTER SAVE: "
        f"{lead.requirement}",
        flush=True
    )

    print(
        f"DB AI SCORE AFTER SAVE: "
        f"{lead.ai_score}",
        flush=True
    )

    print(
        f"DB AI TEMPERATURE AFTER SAVE: "
        f"{lead.ai_temperature}",
        flush=True
    )


    # =====================================================
    # 11. TOTAL RESPONSE TIME
    # =====================================================

    total_time = (
        time.perf_counter()
        - total_start
    )

    print(
        "-" * 50,
        flush=True
    )

    print(
        f"AI GENERATION TIME: "
        f"{ai_generation_time:.3f} seconds",
        flush=True
    )

    print(
        f"TOTAL API TIME: "
        f"{total_time:.3f} seconds",
        flush=True
    )

    print(
        "=" * 50,
        flush=True
    )

    print(
        "AI REQUEST COMPLETED",
        flush=True
    )

    print(
        "=" * 50,
        flush=True
    )

    print(
        "\n",
        flush=True
    )


    # =====================================================
    # 12. RETURN AI RESPONSE
    # =====================================================

    return {
        "response": ai_response,
        "qualification": qualification,
        "ai_score": scoring["score"],
        "ai_temperature": scoring["status"]
    }