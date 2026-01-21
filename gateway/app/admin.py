from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import secrets

from app.db import get_db
from app.models import ApiKey
from app.security import hash_key, validate_api_key
from app.config import API_KEY_HEADER

router = APIRouter(prefix="/admin", tags=["admin"])

def require_admin(request: Request, db: Session) -> ApiKey:
    raw = request.headers.get(API_KEY_HEADER)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing API key")
    row = validate_api_key(db, raw)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    if row.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return row

class CreateKeyRequest(BaseModel):
    name: str = Field(default="api-key", max_length=128)
    role: str = Field(default="user", max_length=32)   # user/admin
    rpm_limit: int = Field(default=0, ge=0)            # 0 = unlimited
    is_active: bool = True

class CreateKeyResponse(BaseModel):
    id: int
    name: str
    role: str
    rpm_limit: int
    is_active: bool
    api_key: str  # raw key shown only once

class KeyInfo(BaseModel):
    id: int
    name: str
    role: str
    rpm_limit: int
    is_active: bool

@router.post("/keys", response_model=CreateKeyResponse)
def create_key(payload: CreateKeyRequest, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)

    # raw key: token sicuro, facile da copiare
    raw_key = secrets.token_hex(24)
    key_hash = hash_key(raw_key)

    row = ApiKey(
        key_hash=key_hash,
        name=payload.name,
        role=payload.role,
        rpm_limit=payload.rpm_limit,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return CreateKeyResponse(
        id=row.id,
        name=row.name,
        role=row.role,
        rpm_limit=row.rpm_limit,
        is_active=row.is_active,
        api_key=raw_key,  # IMPORTANT: mostrata una sola volta
    )

@router.post("/keys/{key_id}/revoke", response_model=KeyInfo)
def revoke_key(key_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)

    row = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Key not found")

    row.is_active = False
    db.commit()
    db.refresh(row)

    return KeyInfo(
        id=row.id, name=row.name, role=row.role, rpm_limit=row.rpm_limit, is_active=row.is_active
    )

@router.get("/keys", response_model=list[KeyInfo])
def list_keys(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    rows = db.query(ApiKey).order_by(ApiKey.id.desc()).all()
    return [KeyInfo(id=r.id, name=r.name, role=r.role, rpm_limit=r.rpm_limit, is_active=r.is_active) for r in rows]
