from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


# =========================================================
# LEAD MODEL
# =========================================================

class Lead(Base):
    __tablename__ = "leads"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    name = Column(
        String(100),
        nullable=False,
    )

    phone = Column(
        String(20),
        nullable=False,
    )

    email = Column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
    )

    source = Column(
        String(50),
        nullable=False,
    )

    status = Column(
        String(50),
        nullable=False,
        default="new",
    )

    notes = Column(
        Text,
        nullable=True,
    )

    follow_up_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    lead_score = Column(
        Integer,
        nullable=False,
        default=0,
    )

    lead_temperature = Column(
        String(20),
        nullable=False,
        default="cold",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    activities = relationship(
        "LeadActivity",
        back_populates="lead",
        cascade="all, delete-orphan",
    )

    conversations = relationship(
        "Conversation",
        back_populates="lead",
        cascade="all, delete-orphan",
    )


# =========================================================
# LEAD ACTIVITY MODEL
# =========================================================

class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    activity_type = Column(
        String(50),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    lead = relationship(
        "Lead",
        back_populates="activities",
    )


# =========================================================
# CONVERSATION MODEL
# =========================================================

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role = Column(
        String(20),
        nullable=False,
    )

    message = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    lead = relationship(
        "Lead",
        back_populates="conversations",
    )
