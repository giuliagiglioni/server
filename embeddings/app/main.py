from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import torch

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
    vectors = model.encode(
        req.texts,
        normalize_embeddings=req.normalize,
        convert_to_numpy=True
    )

    return EmbedResponse(
        embeddings=vectors.tolist(),
        model=MODEL_NAME,
        dim=int(vectors.shape[1]),
    )
