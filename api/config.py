"""Configuração centralizada daaplicação."""

import os
from typing import Optional

DB_HOST: str = os.getenv("DB_HOST", "postgres")
DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
DB_NAME: str = os.getenv("DB_NAME", "chatbot")
DB_USER: str = os.getenv("DB_USER", "postgres")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL: str = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"


OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "180"))

AVAILABLE_MODELS: list = ["llama3", "mistral", "phi", "neural-chat"]


EMBEDDING_DIMENSION: int = 4096
EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN")


SCRAPE_URL: str = os.getenv(
    "SCRAPE_URL",
    "https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial"
)

SCRAPE_TIMEOUT: int = int(os.getenv("SCRAPE_TIMEOUT", "30"))
SCRAPE_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
)


API_PORT: int = int(os.getenv("API_PORT", "8000"))
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")


DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO" if not DEBUG else "DEBUG")
LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")

RAG_MAX_DOCUMENTS: int = int(os.getenv("RAG_MAX_DOCUMENTS", "5"))

MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))


def validate_config() -> bool:
    """Valida configurações críticas."""
    critical_configs = {
        "DB_HOST": DB_HOST,
        "DB_NAME": DB_NAME,
        "OLLAMA_HOST": OLLAMA_HOST,
        "OLLAMA_MODEL": OLLAMA_MODEL,
    }
    
    for key, value in critical_configs.items():
        if not value:
            raise ValueError(f"Configuração crítica ausente: {key}")
    
    if OLLAMA_MODEL not in AVAILABLE_MODELS:
        print(f"Aviso: Modelo {OLLAMA_MODEL} não está na lista de suportados")
    
    return True
