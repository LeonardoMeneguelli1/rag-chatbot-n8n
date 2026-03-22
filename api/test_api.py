import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))


class TestConfig:
    
    def test_load_config(self):
        from config import DB_HOST, OLLAMA_MODEL, API_PORT
        
        assert DB_HOST is not None
        assert OLLAMA_MODEL is not None
        assert API_PORT > 0


class TestExceptions:
    
    def test_chatbot_exception(self):
        from exceptions import ChatbotException
        with pytest.raises(ChatbotException):
            raise ChatbotException("Test error")


class TestEmbeddings:
    def test_embedding_with_empty_text(self):
        from services.embeddings import generate_embedding
        from exceptions import EmbeddingException
        
        with pytest.raises(EmbeddingException):
            generate_embedding("")


class TestFileParser:
    
    def test_parse_file_unsupported_format(self):
        from services.file_parser import parse_file
        from exceptions import ParseException
        
        with pytest.raises(ParseException):
            parse_file("conteudo".encode("utf-8"), "arquivo.txt")


class TestModels:
    
    def test_chat_request_valid(self):
        from models import ChatRequest
        
        request = ChatRequest(question="Olá, como você está?")
        assert request.question == "Olá, como você está?"
        assert request.session_id is None
        assert request.file_content is None
    
    def test_chat_request_empty_question(self):
        from models import ChatRequest
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            ChatRequest(question="")
    
    def test_scrape_request_valid(self):
        from models import ScrapeRequest
        request = ScrapeRequest(url="https://example.com")
        assert request.url == "https://example.com"
    
    def test_scrape_request_invalid_url(self):
        from models import ScrapeRequest
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            ScrapeRequest(url="example.com")


class TestDatabase:
    def test_database_config_exists(self):
        from config import DATABASE_URL
        
        assert "postgresql://" in DATABASE_URL
        assert "@" in DATABASE_URL


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
