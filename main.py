from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import models
import schemas
from database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/leads")
def create_lead(
    lead: schemas.LeadCreate,
    db: Session = Depends(get_db)
):
    new_lead = models.Lead(
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        source=lead.source,
        status=lead.status
    )

    db.add(new_lead)

    try:
        db.commit()
        db.refresh(new_lead)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Lead with this email already exists"
        )

    return {
        "message": "Lead created successfully",
        "lead": {
            "id": new_lead.id,
            "name": new_lead.name,
            "phone": new_lead.phone,
            "email": new_lead.email,
            "source": new_lead.source,
            "status": new_lead.status,
            "created_at": new_lead.created_at,
            "updated_at": new_lead.updated_at
        }
    }

@app.get("/leads/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    return lead
@app.put("/leads/{lead_id}")
@app.put("/leads/{lead_id}")
def update_lead(
    lead_id: int,
    lead: schemas.LeadUpdate,
    db: Session = Depends(get_db)
):
    existing_lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id
    ).first()

    if not existing_lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    existing_lead.name = lead.name
    existing_lead.phone = lead.phone
    existing_lead.email = lead.email
    existing_lead.source = lead.source
    existing_lead.status = lead.status

    try:
        db.commit()
        db.refresh(existing_lead)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This email is already used by another lead"
        )

    return {
        "message": "Lead updated successfully",
        "lead": existing_lead
    }
    db.commit()
    db.refresh(existing_lead)

    return {
        "message": "Lead updated successfully",
        "lead": existing_lead
    }
@app.delete("/leads/{lead_id}")
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db)
):
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    db.delete(lead)
    db.commit()

    return {
        "message": "Lead deleted successfully",
        "deleted_id": lead_id
    }
@app.get("/leads")
def get_leads(
    status: str | None = None,
    source: str | None = None,
    name: str | None = None,
    email: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(models.Lead)

    # Filter by status
    if status:
        query = query.filter(
            models.Lead.status == status
        )

    # Filter by source
    if source:
        query = query.filter(
            models.Lead.source == source
        )

    # Search by name
    if name:
        query = query.filter(
            models.Lead.name.ilike(f"%{name}%")
        )
    # Search by email
    if email:
         query = query.filter(
            models.Lead.email.ilike(f"%{email}%")
        )    

    leads = query.offset(skip).limit(limit).all()

    return {
        "count": len(leads),
        "leads": leads
    }




