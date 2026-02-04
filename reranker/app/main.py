from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from sentence_transformers import CrossEncoder
import torch
import gc

app = FastAPI(title="Reranker Service", version="1.0.0")

MODEL_NAME = "BAAI/bge-reranker-v2-m3"
device = "cuda" if torch.cuda.is_available() else "cpu"

model = CrossEncoder(MODEL_NAME, device=device)

class ScoreRequest(BaseModel):
    query: str = Field(..., min_length=1)
    docs: List[str] = Field(default_factory=list)
    batch_size: int = 16

class ScoreResponse(BaseModel):
    query: str
    model: str
    device: str
    scores: List[float]

class RerankRequest(BaseModel):
    query: str = Field(..., min_length=1)
    docs: List[str] = Field(default_factory=list)
    top_k: Optional[int] = None
    batch_size: int = 16

class RerankItem(BaseModel):
    doc: str
    score: float
    rank: int
    index: int

class RerankResponse(BaseModel):
    query: str
    model: str
    device: str
    results: List[RerankItem]

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "device": device}

def _cleanup():
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()

@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest):
    if not req.docs:
        return ScoreResponse(query=req.query, model=MODEL_NAME, device=device, scores=[])

    try:
        pairs = [(req.query, d) for d in req.docs]
        all_scores: List[float] = []

        with torch.inference_mode():
            for i in range(0, len(pairs), max(1, req.batch_size)):
                chunk = pairs[i:i + req.batch_size]
                s = model.predict(chunk)
                if hasattr(s, "tolist"):
                    all_scores.extend([float(x) for x in s.tolist()])
                else:
                    all_scores.extend([float(x) for x in s])

        return ScoreResponse(query=req.query, model=MODEL_NAME, device=device, scores=all_scores)

    except torch.cuda.OutOfMemoryError as e:
        _cleanup()
        raise HTTPException(status_code=503, detail=f"CUDA OOM during scoring: {str(e)[:200]}")
    except Exception as e:
        _cleanup()
        raise HTTPException(status_code=500, detail=f"Reranker scoring error: {str(e)[:200]}")
    finally:
        _cleanup()

@app.post("/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest):
    if not req.docs:
        return RerankResponse(query=req.query, model=MODEL_NAME, device=device, results=[])

    try:
        pairs = [(req.query, d) for d in req.docs]
        scores: List[float] = []

        with torch.inference_mode():
            for i in range(0, len(pairs), max(1, req.batch_size)):
                chunk = pairs[i:i + req.batch_size]
                s = model.predict(chunk)
                if hasattr(s, "tolist"):
                    scores.extend([float(x) for x in s.tolist()])
                else:
                    scores.extend([float(x) for x in s])

        indexed = list(enumerate(scores))  # (idx, score)
        indexed.sort(key=lambda x: x[1], reverse=True)

        if req.top_k is not None:
            k = max(0, min(req.top_k, len(indexed)))
            indexed = indexed[:k]

        results: List[RerankItem] = []
        for rank, (idx, sc) in enumerate(indexed, start=1):
            results.append(RerankItem(doc=req.docs[idx], score=sc, rank=rank, index=idx))

        return RerankResponse(query=req.query, model=MODEL_NAME, device=device, results=results)

    except torch.cuda.OutOfMemoryError as e:
        _cleanup()
        raise HTTPException(status_code=503, detail=f"CUDA OOM during rerank: {str(e)[:200]}")
    except Exception as e:
        _cleanup()
        raise HTTPException(status_code=500, detail=f"Reranker error: {str(e)[:200]}")
    finally:
        _cleanup()
