from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from database import Base


class Lead(Base):
    __tablename__ = "leads"

    # Unique ID - automatically 1, 2, 3, 4...
    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True
    )

    # Customer name
    name = Column(
        String(100),
        nullable=False
    )

    # Customer phone number
    phone = Column(
        String(20),
        nullable=False
    )

    # Customer email
    email = Column(
        String(150),
        nullable=False,
        unique=True
    )

    # Lead source - Instagram, Website, Facebook etc.
    source = Column(
        String(50),
        nullable=False
    )

    # Lead status - new, contacted, converted etc.
    status = Column(
        String(50),
        nullable=False,
        default="new"
    )

    # Lead created time
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Last updated time
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )