from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY
from app.database import Base


class IncidentMemory(Base):
    __tablename__ = "incident_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    symptoms: Mapped[list[str]] = mapped_column(ARRAY(Text))
    root_cause: Mapped[str] = mapped_column(Text)
    actions_taken: Mapped[list[str]] = mapped_column(ARRAY(Text))
    outcome: Mapped[str] = mapped_column(String(64))
    mttr_seconds: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())