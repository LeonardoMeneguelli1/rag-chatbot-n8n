import threading
import requests
from bs4 import BeautifulSoup
from logger import logger
from exceptions import ScrapeException
from config import SCRAPE_TIMEOUT, SCRAPE_USER_AGENT
from services.rag import get_latest_scrape_document_by_url, save_document_chunks


SCRAPE_TEXT_LIMIT = 12000


def _persist_scrape_async(content: str, url: str) -> None:
    def _save() -> None:
        try:
            result = save_document_chunks(
                content=content,
                metadata={"source": "scrape", "url": url}
            )
            logger.info(
                f"Scrape armazenado em background "
                f"(Grupo: {result['document_group_id']}, chunks: {result['chunk_count']})"
            )
        except Exception as e:
            logger.error(f"Erro ao armazenar scrape em background: {e}")

    threading.Thread(target=_save, daemon=True).start()


def scrape_page(url: str) -> dict:
    try:
        logger.info(f"Iniciando scraping de: {url}")

        cached_doc_id = get_latest_scrape_document_by_url(url)
        if cached_doc_id:
            logger.info(f"URL já ingerida anteriormente. Reutilizando Doc ID: {cached_doc_id}")
            return {
                "status": "success",
                "message": "URL já estava indexada; reutilizando conteúdo existente",
                "document_id": cached_doc_id,
                "characters_scraped": 0,
            }

        try:
            logger.debug("Fazendo request HTTP...")
            response = requests.get(
                url,
                timeout=SCRAPE_TIMEOUT,
                headers={"User-Agent": SCRAPE_USER_AGENT},
            )
            response.raise_for_status()
            logger.debug(f"Response status: {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"Erro ao fazer request: {e}")
            raise ScrapeException(f"Erro ao acessar URL: {e}") from e

        try:
            logger.debug("Parseando HTML com BeautifulSoup...")
            soup = BeautifulSoup(response.text, "html.parser")

            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text(separator=" ", strip=True)

            text = " ".join(text.split())

            if len(text) > SCRAPE_TEXT_LIMIT:
                logger.debug(
                    f"Conteúdo muito grande ({len(text)} chars); truncando para {SCRAPE_TEXT_LIMIT}"
                )
                text = text[:SCRAPE_TEXT_LIMIT] + " ...[conteudo truncado]"

            if not text:
                logger.warning("Nenhum conteúdo foi extraído do HTML")
                raise ScrapeException("HTML não contém conteúdo de texto")

            logger.debug(f"Conteúdo extraído: {len(text)} caracteres")

        except Exception as e:
            logger.error(f"Erro ao parsear HTML: {e}")
            raise ScrapeException(f"Erro ao parsear HTML: {e}") from e

        try:
            logger.debug("Iniciando persistencia em background")
            _persist_scrape_async(content=text, url=url)

            logger.info("Scraping concluido com sucesso; indexacao em background iniciada")

            return {
                "status": "success",
                "message": "Scraping concluido; indexacao de embeddings iniciada em background",
                "document_id": None,
                "characters_scraped": len(text)
            }

        except Exception as e:
            logger.error(f"Erro ao salvar documento: {e}")
            raise ScrapeException(f"Erro ao armazenar conteúdo: {e}") from e

    except ScrapeException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado no scraping: {e}")
        raise ScrapeException(f"Erro inesperado: {e}") from e

