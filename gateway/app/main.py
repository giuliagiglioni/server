import time
from fastapi import FastAPI, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.admin import router as admin_router
from app.db import get_db
from app.config import API_KEY_HEADER
from app.ratelimit import enforce_rpm_limit
from app.security import validate_api_key
from app.proxy import forward_to_vllm, forward_to_embeddings
from app.models import AuditLog

app = FastAPI(title="LLM Gateway", version="0.1.0")

app.include_router(admin_router)

@app.get("/health")
def health():
    return {"status": "ok"}

def get_api_key_or_401(request: Request, db: Session):
    raw = request.headers.get(API_KEY_HEADER)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing API key")
    row = validate_api_key(db, raw)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    return row

@app.api_route("/embeddings/{full_path:path}", methods=["GET","POST"])
async def embeddings_proxy(full_path: str, request: Request, db: Session = Depends(get_db)):
    api_key_row = get_api_key_or_401(request, db)

    enforce_rpm_limit(api_key_row.id, api_key_row.rpm_limit)

    path = f"/{full_path}"
    try:
        return await forward_to_embeddings(request, path)
    except Exception:
        raise HTTPException(status_code=502, detail="Embeddings upstream unavailable")


@app.api_route("/v1/{full_path:path}", methods=["GET","POST","PUT","PATCH","DELETE"])
async def v1_proxy(full_path: str, request: Request, db: Session = Depends(get_db)):
    api_key_row = get_api_key_or_401(request, db)

    # rate limit per API key
    enforce_rpm_limit(api_key_row.id, api_key_row.rpm_limit)

    api_key_id = api_key_row.id

    t0 = time.perf_counter()
    path = f"/v1/{full_path}"

    # (MVP) prova a leggere il model dal JSON se presente
    model = None
    req_bytes = 0
    try:
        body = await request.body()
        req_bytes = len(body or b"")
        if body:
            import json
            j = json.loads(body.decode("utf-8"))
            model = j.get("model")
    except Exception:
        pass

    try:
        resp = await forward_to_vllm(request, path)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        log = AuditLog(
            api_key_id=api_key_id,
            path=path,
            method=request.method,
            model=model,
            status_code=resp.status_code,
            latency_ms=latency_ms,
            request_bytes=req_bytes,
            response_bytes=len(resp.body or b""),
            error=None if resp.status_code < 500 else "Upstream error",
        )
        db.add(log)
        db.commit()

        return resp

    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        log = AuditLog(
            api_key_id=api_key_id,
            path=path,
            method=request.method,
            model=model,
            status_code=502,
            latency_ms=latency_ms,
            request_bytes=req_bytes,
            response_bytes=0,
            error=str(e),
        )
        db.add(log)
        db.commit()
        raise HTTPException(status_code=502, detail="Upstream unavailable")
