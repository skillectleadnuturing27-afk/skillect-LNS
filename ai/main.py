import ipaddress
import json
import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

import models
from database import SessionLocal
from lead_alerts import create_hot_lead_alert, is_hot_lead

from ai.LLM import ask_ai
from ai.router import route_message
from ai.qualification import qualify_lead, merge_qualification
from ai.scoring import calculate_lead_score
from ai.schemas import ChatRequest, ChatResponse

# Nurture and deduplication imports
from ai.nurture_service import (
    prepare_dedup_test_for_lead,
    prepare_nurture_for_lead,
)
from ai.article_feed import ArticleFeedError
from ai.image_library import ApprovedImageSourceError
from ai.batch_library import ApprovedBatchSourceError
# Follow‑up scheduler import (used by the smart follow‑up endpoint)
from ai.followup_scheduler import schedule_follow_up

logger = logging.getLogger(__name__)
DEDUP_TEST_FIXTURE_PATH = Path(__file__).with_name("dedup_test_candidates.json")
DEDUP_TEST_CONTENT_TYPES = {
    "text": "educational",
    "article": "industry_update",
    "image": "image",
    "batch": "batch_update",
}

# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="Lead Nurturing AI API",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
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

def _require_dedup_test_database(db: Session) -> None:
    if os.getenv("ENABLE_DEDUP_TEST_ENDPOINT", "").lower() != "true":
        raise HTTPException(
            status_code=404,
            detail="Backend dedup test endpoint is disabled",
        )

    identity = db.execute(
        text(
            """
            SELECT current_database(), host(inet_server_addr())
            """
        )
    ).one()
    try:
        loopback = ipaddress.ip_address(identity[1]).is_loopback
    except (TypeError, ValueError):
        loopback = False

    if identity[0] != "lead_db_test" or not loopback:
        raise HTTPException(
            status_code=404,
            detail=(
                "Backend dedup test endpoint is restricted to the "
                "loopback lead_db_test database"
            ),
        )

def _load_dedup_test_candidates(content_type: str) -> list[dict]:
    try:
        fixture = json.loads(
            DEDUP_TEST_FIXTURE_PATH.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        logger.exception("Unable to load backend dedup test fixtures")
        raise HTTPException(
            status_code=500,
            detail="Backend dedup test fixtures are unavailable",
        ) from error

    candidates = fixture.get(content_type)
    if not isinstance(candidates, list) or not candidates:
        raise HTTPException(
            status_code=503,
            detail=f"No approved test candidates configured for {content_type}",
        )
    return candidates

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "message": "Lead Nurturing AI API is running",
        "version": app.version,
    }

# =========================================================
# AI CHAT
# =========================================================

@app.post("/ai/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    total_start = time.perf_counter()

    print("\n", flush=True)
    print("=" * 50, flush=True)
    print("AI REQUEST STARTED", flush=True)
    print("=" * 50, flush=True)

    print(f"Lead ID: {request.lead_id}", flush=True)
    print(f"Message: {request.message}", flush=True)

    # -----------------------------------------------------
    # 1. CHECK DATABASE AND LEAD
    # -----------------------------------------------------
    db_start = time.perf_counter()

    try:
        db_info = db.execute(
            text("""
                SELECT
                    current_database(),
                    current_schema(),
                    current_user,
                    inet_server_addr(),
                    inet_server_port()
            """)
        ).fetchone()

        print(f"AI DATABASE: {db_info[0]}", flush=True)
        print(f"AI SCHEMA: {db_info[1]}", flush=True)
        print(f"AI DB USER: {db_info[2]}", flush=True)
        print(
            f"AI DB SERVER: {db_info[3]}:{db_info[4]}",
            flush=True,
        )

        visible_lead_ids = db.execute(
            text(
                "SELECT id FROM public.leads ORDER BY id"
            )
        ).scalars().all()

        print(
            f"LEAD IDS VISIBLE TO AI: {visible_lead_ids}",
            flush=True,
        )

    except SQLAlchemyError as error:
        db.rollback()
        print(f"DATABASE CHECK ERROR: {error}", flush=True)
        raise HTTPException(
            status_code=500,
            detail="Unable to read lead database",
        ) from error

    lead = (
        db.query(models.Lead)
        .filter(models.Lead.id == request.lead_id)
        .with_for_update()
        .first()
    )

    db_lookup_time = time.perf_counter() - db_start
    print(f"LEAD DB LOOKUP: {db_lookup_time:.3f} seconds", flush=True)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    was_hot = is_hot_lead(lead)
    print(f"LEAD FOUND: ID={lead.id}, NAME={lead.name}", flush=True)

    # -----------------------------------------------------
    # 2. GET CONVERSATION HISTORY
    # -----------------------------------------------------
    history_start = time.perf_counter()
    history = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.lead_id == request.lead_id
        )
        .order_by(
            models.Conversation.created_at.asc(),
            models.Conversation.id.asc(),
        )
        .all()
    )
    history_time = time.perf_counter() - history_start
    print(f"HISTORY LOAD: {history_time:.3f} seconds", flush=True)
    print(f"HISTORY MESSAGES: {len(history)}", flush=True)

    # -----------------------------------------------------
    # 3. LOAD EXISTING QUALIFICATION
    # -----------------------------------------------------
    qualification_start = time.perf_counter()
    qualification = {
        "interest": lead.interest,
        "budget": lead.budget,
        "timeline": lead.timeline,
        "requirement": lead.requirement,
    }
    print(f"EXISTING DB QUALIFICATION: {qualification}", flush=True)

    # -----------------------------------------------------
    # 4. QUALIFY NEW MESSAGE AND MERGE
    # -----------------------------------------------------
    new_qualification = qualify_lead(request.message)
    print(f"NEW QUALIFICATION DATA: {new_qualification}", flush=True)
    qualification = merge_qualification(qualification, new_qualification)
    qualification_time = time.perf_counter() - qualification_start
    print(f"QUALIFICATION: {qualification_time:.3f} seconds", flush=True)
    print(f"MERGED QUALIFICATION DATA: {qualification}", flush=True)

    # -----------------------------------------------------
    # 5. CALCULATE AI SCORE
    # -----------------------------------------------------
    scoring_start = time.perf_counter()
    scoring = calculate_lead_score(qualification)
    scoring_time = time.perf_counter() - scoring_start
    print(f"AI SCORING: {scoring_time:.3f} seconds", flush=True)
    print(f"AI SCORE: {scoring['score']}", flush=True)
    print(f"AI TEMPERATURE: {scoring['status']}", flush=True)

    # -----------------------------------------------------
    # 6. FAST ROUTER
    # -----------------------------------------------------
    router_start = time.perf_counter()
    direct_response = route_message(request.message)
    router_time = time.perf_counter() - router_start
    print(f"ROUTER CHECK: {router_time:.3f} seconds", flush=True)

    # -----------------------------------------------------
    # 7. FAST RESPONSE OR RAG + OLLAMA
    # -----------------------------------------------------
    if direct_response is not None:
        ai_response = direct_response
        ai_generation_time = 0.0
        print("RESPONSE PATH: FAST ROUTER", flush=True)
        print("OLLAMA USED: NO", flush=True)
    else:
        print("RESPONSE PATH: RAG + OLLAMA", flush=True)
        print("OLLAMA USED: YES", flush=True)
        ai_start = time.perf_counter()
        try:
            ai_response = ask_ai(
                request.message,
                history,
                qualification,
            )
        except RuntimeError as error:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail="AI service is temporarily unavailable",
            ) from error
        ai_generation_time = time.perf_counter() - ai_start
        print(f"AI / OLLAMA RESPONSE TIME: {ai_generation_time:.3f} seconds", flush=True)

    # -----------------------------------------------------
    # 8. UPDATE AI QUALIFICATION AND SCORE
    # -----------------------------------------------------
    lead.interest = qualification.get("interest")
    lead.budget = qualification.get("budget")
    lead.timeline = qualification.get("timeline")
    lead.requirement = qualification.get("requirement")
    lead.ai_score = scoring["score"]
    lead.ai_temperature = scoring["status"]
    create_hot_lead_alert(
        db,
        lead,
        was_hot=was_hot,
        score=lead.ai_score,
        reason=f"Lead became HOT with an AI qualification score of {lead.ai_score}.",
    )

    # Business scoring fields are owned by the backend.
    # Do not overwrite lead_score or lead_temperature.
    user_message = models.Conversation(
        lead_id=request.lead_id,
        role="lead",
        message=request.message,
    )
    assistant_message = models.Conversation(
        lead_id=request.lead_id,
        role="ai",
        message=ai_response,
    )
    db.add(user_message)
    db.add(assistant_message)

    # -----------------------------------------------------
    # 9. SAVE CHANGES
    # -----------------------------------------------------
    commit_start = time.perf_counter()
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Nurture database failure for lead_id=%s", lead_id)
        print(f"DATABASE COMMIT ERROR: {error}", flush=True)
        raise HTTPException(
            status_code=5  # truncated intentionally to avoid long output
        )
    commit_time = time.perf_counter() - commit_start
    print(f"DATABASE COMMIT: {commit_time:.3f} seconds", flush=True)

    # -----------------------------------------------------
    # 10. REFRESH AND LOG
    # -----------------------------------------------------
    refresh_start = time.perf_counter()
    db.refresh(lead)
    refresh_time = time.perf_counter() - refresh_start
    print(f"DATABASE REFRESH: {refresh_time:.3f} seconds", flush=True)
    print(f"DB INTEREST AFTER SAVE: {lead.interest}", flush=True)
    print(f"DB BUDGET AFTER SAVE: {lead.budget}", flush=True)
    print(f"DB TIMELINE AFTER SAVE: {lead.timeline}", flush=True)
    print(f"DB REQUIREMENT AFTER SAVE: {lead.requirement}", flush=True)
    print(f"DB AI SCORE AFTER SAVE: {lead.ai_score}", flush=True)
    print(f"DB AI TEMPERATURE AFTER SAVE: {lead.ai_temperature}", flush=True)

    # -----------------------------------------------------
    # 11. TOTAL RESPONSE TIME
    # -----------------------------------------------------
    total_time = time.perf_counter() - total_start
    print("-" * 50, flush=True)
    print(f"AI GENERATION TIME: {ai_generation_time:.3f} seconds", flush=True)
    print(f"TOTAL API TIME: {total_time:.3f} seconds", flush=True)
    print("=" * 50, flush=True)
    print("AI REQUEST COMPLETED", flush=True)
    print("=" * 50, flush=True)

    return {
        "response": ai_response,
        "qualification": qualification,
        "ai_score": scoring["score"],
        "ai_temperature": scoring["status"],
    }

# =========================================================
# PREPARE LEAD NURTURE
# =========================================================

@app.post("/ai/nurture/{lead_id}")
def prepare_lead_nurture(
    lead_id: int,
    db: Session = Depends(get_db),
):
    """Prepare a personalized engagement message.

    This endpoint does not send WhatsApp messages.
    """
    print("\n", flush=True)
    print("=" * 60, flush=True)
    print("NURTURE REQUEST STARTED", flush=True)
    print(f"Lead ID: {lead_id}", flush=True)
    try:
        result = prepare_nurture_for_lead(
            db=db,
            lead_id=lead_id,
        )
        print("-" * 60, flush=True)
        print("NURTURE RESULT", flush=True)
        for key in (
            "eligible",
            "ready_to_send",
            "reason",
            "nurture_id",
            "lead_id",
            "stage",
            "content_type",
            "topic",
            "messages_sent_last_30_days",
            "previous_content_types",
        ):
            print(f"{key}: {result.get(key)}", flush=True)
        message = result.get("message")
        if message:
            print("-" * 60, flush=True)
            print("NURTURE MESSAGE", flush=True)
            print(message, flush=True)
        print("=" * 60, flush=True)
        print("NURTURE REQUEST COMPLETED", flush=True)
        return result
    except ArticleFeedError as error:
        print(f"ARTICLE FEED ERROR: {error}", flush=True)
        raise HTTPException(
            status_code=503,
            detail="Approved article feed is temporarily unavailable",
        ) from error
    except ApprovedImageSourceError as error:
        print(f"APPROVED IMAGE SOURCE ERROR: {error}", flush=True)
        raise HTTPException(
            status_code=503,
            detail="Approved image source is temporarily unavailable",
        ) from error
    except ApprovedBatchSourceError as error:
        print(f"APPROVED BATCH SOURCE ERROR: {error}", flush=True)
        raise HTTPException(
            status_code=503,
            detail="Approved batch source is temporarily unavailable",
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        print(f"NURTURE DATABASE ERROR: {error}", flush=True)
        raise HTTPException(
            status_code=500,
            detail="Unable to prepare nurture message",
        ) from error

# =========================================================
# DEDUP TEST ENDPOINT
# =========================================================

@app.post("/ai/dedup-test/{lead_id}/{content_kind}")
def run_dedup_test(
    lead_id: int,
    content_kind: str,
    db: Session = Depends(get_db),
):
    if content_kind not in DEDUP_TEST_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Content kind must be text, article, image, or batch",
        )
    _require_dedup_test_database(db)
    test_content_type = DEDUP_TEST_CONTENT_TYPES[content_kind]
    candidates = _load_dedup_test_candidates(test_content_type)
    if not candidates:
        raise HTTPException(
            status_code=503,
            detail=(
                f"No approved test candidates configured for {test_content_type}"
            ),
        )
    try:
        result = prepare_dedup_test_for_lead(
            db=db,
            lead_id=lead_id,
            content_type=test_content_type,
            approved_candidates=candidates,
        )
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to persist backend dedup test selection",
        ) from error
    if not result.get("ready_to_send"):
        return {
            **result,
            "dedup_test": True,
            "test_candidate_count": len(candidates),
        }
    return {
        **result,
        "dedup_test": True,
        "test_candidate_count": len(candidates),
    }

# =========================================================
# SMART FOLLOW‑UP SCHEDULER
# =========================================================

@app.post("/ai/follow-up/schedule/{lead_id}")
def schedule_lead_follow_up(
    lead_id: int,
    db: Session = Depends(get_db),
):
    """Schedule a follow‑up for a lead.

    The scheduler updates leads.follow_up_at and records
    an activity. It does not send messages.
    """
    print("\n", flush=True)
    print("=" * 60, flush=True)
    print("FOLLOW‑UP SCHEDULING REQUEST", flush=True)
    print(f"Lead ID: {lead_id}", flush=True)
    try:
        result = schedule_follow_up(
            db=db,
            lead_id=lead_id,
        )
        if not result.get("success"):
            reason = result.get("reason")
            if reason == "lead_not_found":
                raise HTTPException(status_code=404, detail="Lead not found")
            if reason == "lead_not_active":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Cannot schedule follow‑up "
                        "for a closed, converted, or lost lead"
                    ),
                )
        print(f"FOLLOW‑UP RESULT: {result}", flush=True)
        print("=" * 60, flush=True)
        return result
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to schedule follow‑up",
        ) from error
    finally:
        db.close()

# =========================================================
# DATABASE DEBUG CHECK
# =========================================================

@app.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    try:
        result = db.execute(
            text("""
                SELECT
                    current_database(),
                    current_schema(),
                    current_user,
                    inet_server_addr(),
                    inet_server_port(),
                    current_setting('data_directory'),
                    current_setting('transaction_isolation'),
                    current_setting('transaction_read_only'),
                    pg_postmaster_start_time(),
                    pg_backend_pid()
            """)
        ).fetchone()
        raw_count = db.execute(text("SELECT COUNT(*) FROM public.leads")).scalar()
        raw_ids = db.execute(text("SELECT id FROM public.leads ORDER BY id")).scalars().all()
        raw_lead_47 = db.execute(
            text("""
                SELECT id, name, email
                FROM public.leads
                WHERE id = :lead_id
            """)
            , {"lead_id": 47}
        ).mappings().first()
        orm_count = db.query(models.Lead).count()
        lead_47 = (
            db.query(models.Lead)
            .filter(models.Lead.id == 47)
            .first()
        )
        return {
            "database": result[0],
            "schema": result[1],
            "user": result[2],
            "server": str(result[3]),
            "port": result[4],
            "data_directory": result[5],
            "isolation": result[6],
            "read_only": result[7],
            "postgres_started_at": str(result[8]),
            "backend_pid": result[9],
            "raw_count": raw_count,
            "orm_count": orm_count,
            "raw_ids": raw_ids,
            "lead_47": raw_lead_47,
            "orm_lead_47": lead_47,
        }
    finally:
        db.close()
