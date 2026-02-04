import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://gateway:gateway@gateway-db:5432/gateway")
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://vllm:8000")

# Header dove passerai la chiave (semplice e standard)
API_KEY_HEADER = os.getenv("API_KEY_HEADER", "X-API-Key")

# Logging: evita di salvare prompt (default OFF)
LOG_PROMPTS = os.getenv("LOG_PROMPTS", "false").lower() == "true"

# Embeddings service (internal)
EMBEDDINGS_BASE_URL = os.getenv("EMBEDDINGS_BASE_URL", "http://embeddings:8002")

# Reranker service (internal)
RERANKER_BASE_URL = os.getenv("RERANKER_BASE_URL", "http://reranker:8003")
