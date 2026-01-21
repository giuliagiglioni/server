from sqlalchemy import String, Boolean, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from app.db import Base

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="default")
    role: Mapped[str] = mapped_column(String(32), default="user")  # user/admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rpm_limit: Mapped[int] = mapped_column(Integer, default=0)     # 0 = no limit (MVP)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    logs = relationship("AuditLog", back_populates="api_key")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"), index=True)
    path: Mapped[str] = mapped_column(String(256))
    method: Mapped[str] = mapped_column(String(16))
    model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # opzionale: NON salvare prompt di default (sensibile)
    request_bytes: Mapped[int] = mapped_column(Integer, default=0)
    response_bytes: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    api_key = relationship("ApiKey", back_populates="logs")
