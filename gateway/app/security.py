import hashlib
from sqlalchemy.orm import Session
from app.models import ApiKey

def hash_key(raw: str) -> str:
    # MVP: SHA-256 (sufficiente per un gateway interno; se vuoi puoi passare a HMAC/argon2 più avanti)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def validate_api_key(db: Session, raw_key: str) -> ApiKey | None:
    h = hash_key(raw_key)
    row = db.query(ApiKey).filter(ApiKey.key_hash == h, ApiKey.is_active == True).first()
    return row
