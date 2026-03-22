from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    file_content: Optional[str] = Field(None, description="Conteúdo extraído do arquivo")
    file_name: Optional[str] = Field(None, description="Nome do arquivo")
    session_id: Optional[str] = Field(None, description="ID da sessão para manter contexto")

    @validator("question")
    def question_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Pergunta não pode estar vazia")
        return v.strip()


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sources: Optional[List[str]] = None


class ScrapeRequest(BaseModel):
    url: str = Field(..., description="URL a ser scrapizada")

    @validator("url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL deve começar com http:// ou https://")
        return v


class ScrapeResponse(BaseModel):
    status: str
    message: str
    documents_count: int = 0
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
