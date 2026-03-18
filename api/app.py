"""API Principal do Chatbot com RAG - Litestar."""

from typing import Annotated
from litestar import Litestar, post, get
from litestar.enums import RequestEncodingType
from litestar.openapi.config import OpenAPIConfig
from litestar.params import Body

from logger import logger
from exceptions import ChatbotException
from models import ChatResponse, ScrapeRequest, ScrapeResponse, ErrorResponse
from database.connection import init_db
from routes.chat import chat
from routes.scrape import scrape_page
from config import SCRAPE_URL

async def inicializar_sistema() -> None:
    """Hook executado na inicialização do servidor Litestar."""
    logger.info("=" * 50)
    logger.info("Iniciando sistema de Chatbot com RAG")
    logger.info("=" * 50)

    try:
        logger.debug("Inicializando banco de dados")
        init_db()

        if SCRAPE_URL:
            logger.info(f"Indexando URL de startup: {SCRAPE_URL}")
            try:
                result = scrape_page(SCRAPE_URL)
                logger.info(f"Scrape de startup concluido: {result.get('message', 'ok')}")
            except Exception as e:
                logger.warning(f"Scrape de startup falhou (nao critico): {e}")

        logger.info("Sistema inicializado com sucesso")

    except Exception as e:
        logger.error(f"Erro critico na inicializacao: {e}")
        raise


async def teste_saude() -> str:
    return "Sistema rodando normalmente"

@post(
    "/chat",
    name="chat_endpoint",
    description="Endpoint de chat com suporte a upload de arquivos e RAG"
)
def chat_endpoint(
    data: Annotated[dict, Body(media_type=RequestEncodingType.MULTI_PART)]
) -> ChatResponse | ErrorResponse:
    try:
        logger.info("Requisicao POST /chat recebida")

        question = data.get("question", "").strip()
        file = data.get("file")
        session_id = data.get("session_id")

        if question.startswith("="):
            question = question[1:].lstrip()
        if isinstance(session_id, str) and session_id.startswith("="):
            session_id = session_id[1:].lstrip()

        if not question:
            logger.warning("Pergunta vazia recebida")
            return ErrorResponse(
                error="Pergunta obrigatória",
                detail="Campo 'question' não pode estar vazio"
            )

        logger.debug(f"Pergunta: {question[:100]}...")

        file_content = None
        file_name = None

        if file:
            try:
                logger.debug(f"Arquivo recebido: {file.filename}")
                file_content = file.file.read()
                file_name = file.filename
                logger.debug(f"Tamanho do arquivo: {len(file_content)} bytes")
            except Exception as e:
                logger.error(f"Erro ao ler arquivo: {e}")

        logger.debug("Processando chat...")
        answer, returned_session_id = chat(
            question=question,
            file_content=file_content,
            file_name=file_name,
            session_id=session_id
        )

        logger.info(f"Chat processado com sucesso (Sessao: {returned_session_id})")

        return ChatResponse(
            response=answer,
            session_id=returned_session_id
        )

    except ChatbotException as e:
        logger.warning(f"Erro de negócio: {e}")
        return ErrorResponse(error="Erro ao processar chat", detail=str(e))

    except Exception as e:
        logger.error(f"Erro inesperado em /chat: {e}", exc_info=True)
        return ErrorResponse(
            error="Erro interno do servidor",
            detail="Verifique os logs para mais detalhes"
        )


@post(
    "/scrape",
    name="scrape_endpoint",
    description="Realiza web scraping de uma URL e armazena embeddings"
)
def scrape_endpoint(data: ScrapeRequest) -> ScrapeResponse | ErrorResponse:
    try:
        logger.info(f"Requisicao POST /scrape recebida para URL: {data.url}")

        result = scrape_page(data.url)

        logger.info("Scraping concluido com sucesso")

        return ScrapeResponse(
            status=result.get("status", "success"),
            message=result.get("message", ""),
            documents_count=1
        )

    except ChatbotException as e:
        logger.warning(f"Erro no scraping: {e}")
        return ErrorResponse(error="Erro ao fazer scraping", detail=str(e))

    except Exception as e:
        logger.error(f"Erro inesperado em /scrape: {e}", exc_info=True)
        return ErrorResponse(
            error="Erro interno do servidor",
            detail="Verifique os logs para mais detalhes"
        )


@get(
    "/health",
    name="health_check",
    description="Verifica saúde da API"
)
def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "chatbot-api",
        "version": "1.0.0"
    }

app = Litestar(
    route_handlers=[
        chat_endpoint,
        scrape_endpoint,
        health_check,
    ],
    on_startup=[inicializar_sistema],
    openapi_config=OpenAPIConfig(
        title="Chatbot API",
        version="1.0.0",
        description="API de Chatbot com RAG - Recuperacao de documentos e geracao aumentada",
    ),
)

logger.info("Aplicação Litestar configurada com sucesso")
logger.info("Endpoints disponíveis: POST /chat, POST /scrape, GET /health")
