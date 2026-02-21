from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    service: Mapped[str] = mapped_column(String(128))               # '*' = wildcard
    severity: Mapped[str] = mapped_column(String(32))               # '*' = wildcard
    min_autonomy_level: Mapped[str] = mapped_column(String(4))      # L0 | L1 | L2 | L3
    requires_approval: Mapped[bool] = mapped_column(default=True)
    reason: Mapped[str] = mapped_column(Text)