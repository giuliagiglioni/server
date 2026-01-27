from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import torch
import gc

app = FastAPI(title="Embedding Service", version="1.0.0")

MODEL_NAME = "BAAI/bge-m3"
device = "cuda" if torch.cuda.is_available() else "cpu"

model = SentenceTransformer(MODEL_NAME, device=device)

class EmbedRequest(BaseModel):
    texts: list[str]
    normalize: bool = True

class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dim: int

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "device": device}

@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    if not req.texts:
        return EmbedResponse(embeddings=[], model=MODEL_NAME, dim=0)

    max_batch_size = 4
    internal_batch_size = 4

    all_embeddings = []

    try:
        with torch.inference_mode():
            for i in range(0, len(req.texts), max_batch_size):
                batch = req.texts[i:i + max_batch_size]
                vectors = model.encode(
                    batch,
                    normalize_embeddings=req.normalize,
                    convert_to_numpy=True,
                    batch_size=internal_batch_size,
                    show_progress_bar=False,
                )
                all_embeddings.extend(vectors.tolist())
                del vectors

    except torch.cuda.OutOfMemoryError as e:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        raise HTTPException(status_code=503, detail=f"CUDA OOM during embedding: {str(e)[:200]}")

    except Exception as e:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        raise HTTPException(status_code=500, detail=f"Embedding error: {str(e)[:200]}")

    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    dim = len(all_embeddings[0]) if all_embeddings else 0
    return EmbedResponse(embeddings=all_embeddings, model=MODEL_NAME, dim=dim)
