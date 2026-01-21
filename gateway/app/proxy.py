import httpx
import os
from fastapi import Request, Response
from app.config import VLLM_BASE_URL, EMBEDDINGS_BASE_URL
VLLM_UPSTREAM_API_KEY = os.getenv("VLLM_UPSTREAM_API_KEY", "").strip()

HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade"
}

DROP_HEADERS = HOP_BY_HOP_HEADERS | {"date", "server", "content-length"}

async def forward_to_vllm(request: Request, new_path: str) -> Response:
    url = f"{VLLM_BASE_URL}{new_path}"
    params = dict(request.query_params)

    headers = {}
    for k, v in request.headers.items():
        lk = k.lower()
        if lk in HOP_BY_HOP_HEADERS:
            continue
        if lk == "x-api-key":
            continue
        headers[k] = v

    body = await request.body()

    if VLLM_UPSTREAM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_UPSTREAM_API_KEY}"

    async with httpx.AsyncClient(timeout=httpx.Timeout(3600.0)) as client:
        r = await client.request(
            method=request.method,
            url=url,
            params=params,
            content=body,
            headers=headers,
        )

    return Response(
        content=r.content,
        status_code=r.status_code,
        headers={k: v for k, v in r.headers.items() if k.lower() not in DROP_HEADERS},
        media_type=r.headers.get("content-type"),
    )

async def forward_to_embeddings(request: Request, new_path: str) -> Response:
    """
    Proxy requests to the internal embeddings service.
    Authentication is handled at the gateway level.
    """
    url = f"{EMBEDDINGS_BASE_URL}{new_path}"
    params = dict(request.query_params)

    headers = {}
    for k, v in request.headers.items():
        lk = k.lower()
        if lk in HOP_BY_HOP_HEADERS:
            continue
        if lk == "x-api-key":
            continue
        headers[k] = v

    body = await request.body()

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        r = await client.request(
            method=request.method,
            url=url,
            params=params,
            content=body,
            headers=headers,
        )

    return Response(
        content=r.content,
        status_code=r.status_code,
        headers={k: v for k, v in r.headers.items() if k.lower() not in DROP_HEADERS},
        media_type=r.headers.get("content-type"),
    )
