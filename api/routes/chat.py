import threading
import uuid
from typing import Optional
from logger import logger
from exceptions import OllamaException
from services.rag import (
    GLOBAL_RAG_MIN_SIMILARITY,
    get_latest_session_document,
    get_recent_chat_history,
    save_chat_history,
    save_document_chunks,
    search_similar_chunks,
)
from services.file_parser import parse_file
from config import OLLAMA_MODEL

try:
    import ollama
except ImportError:
    logger.error("Ollama não está instalado")
    ollama = None


DIRECT_FILE_CONTEXT_LIMIT = 6000
ACTIVE_DOCUMENT_CONTEXT_LIMIT = 5000
RECENT_HISTORY_LIMIT = 10
GLOBAL_RAG_RESULT_LIMIT = 3
GLOBAL_RAG_CONTEXT_LIMIT = 3500
MAX_RESPONSE_TOKENS = 180


def _format_source_label(metadata: dict) -> str:
    source = metadata.get("source") or metadata.get("type") or "documento"

    if source == "scrape":
        return metadata.get("url") or "URL desconhecida"

    if source == "upload":
        return metadata.get("filename") or "arquivo enviado"

    return metadata.get("filename") or metadata.get("url") or "fonte desconhecida"


def _format_search_results(results: list[dict], max_chars: int) -> str:
    if not results:
        return ""

    sections = []
    used_chars = 0

    for index, item in enumerate(results, start=1):
        metadata = item.get("metadata", {})
        score = item.get("similarity", 0.0)
        snippet = item.get("content", "")
        section = (
            f"Fonte {index}\n"
            f"Origem: {_format_source_label(metadata)}\n"
            f"Relevancia: {score:.2f}\n"
            f"Trecho: {snippet}"
        )

        projected_size = used_chars + len(section)
        if sections and projected_size > max_chars:
            break

        sections.append(section)
        used_chars = projected_size

    return "\n\n".join(sections)


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[conteudo truncado]"


def _format_recent_history(session_id: str) -> str:
    history_rows = get_recent_chat_history(session_id, limit=RECENT_HISTORY_LIMIT)

    if not history_rows:
        return "Sem histórico recente."

    formatted_rows = []
    for question, answer in history_rows:
        formatted_rows.append(f"Usuario: {question}\nAssistente: {answer}")

    return "\n\n".join(formatted_rows)


def _persist_document_async(content: str, file_name: str, session_id: str) -> None:
    def _save() -> None:
        try:
            result = save_document_chunks(
                content=content,
                metadata={
                    "source": "upload",
                    "type": "upload",
                    "filename": file_name,
                    "session_id": session_id,
                }
            )
            logger.info(
                "Arquivo processado e armazenado em background "
                f"(Grupo: {result['document_group_id']}, chunks: {result['chunk_count']})"
            )
        except Exception as e:
            logger.error(f"Erro ao salvar documento em background: {e}")

    threading.Thread(target=_save, daemon=True).start()


def chat(
    question: str,
    file_content: Optional[bytes] = None,
    file_name: Optional[str] = None,
    session_id: Optional[str] = None
) -> tuple[str, str]:
    try:
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.debug(f"Nova sessão criada: {session_id}")
        else:
            logger.debug(f"Usando sessão existente: {session_id}")
        
        file_context = None

        if file_content and file_name:
            try:
                logger.info(f"Processando arquivo: {file_name}")
                extracted_text = parse_file(file_content, file_name)
                file_context = _truncate_text(extracted_text, DIRECT_FILE_CONTEXT_LIMIT)

                logger.debug("Salvando documento em background")
                _persist_document_async(extracted_text, file_name, session_id)
            except Exception as e:
                logger.error(f"Erro ao processar arquivo: {e}")

        recent_history = _format_recent_history(session_id)

        if file_context:
            logger.debug("Usando contexto direto do arquivo enviado na requisição atual")
            document_context = file_context
        else:
            document_context = None
            active_document = get_latest_session_document(session_id)

            if active_document:
                logger.debug("Usando documento mais recente da sessão como contexto principal")
                document_context = _truncate_text(active_document, ACTIVE_DOCUMENT_CONTEXT_LIMIT)
            else:
                logger.debug("Sem documento na sessão; executando busca RAG global")
                search_results = search_similar_chunks(
                    question,
                    limit=GLOBAL_RAG_RESULT_LIMIT,
                    exclude_session_docs=True,
                    min_similarity=GLOBAL_RAG_MIN_SIMILARITY
                )
                global_context = _format_search_results(search_results, GLOBAL_RAG_CONTEXT_LIMIT)
                if global_context:
                    document_context = global_context

        if document_context:
            prompt = f"""Você é um assistente que responde usando prioritariamente o contexto fornecido.

Regras:
- Use o contexto quando ele for suficiente.
- Não invente fatos que não estejam no contexto.
- Se o contexto for insuficiente, deixe isso explícito.
- Responda de forma objetiva em no máximo 6 frases.

Histórico recente:
{recent_history}

Contexto documental:
{document_context}

Pergunta:
{question}"""
        else:
            logger.debug("Sem contexto documental relevante; respondendo com conhecimento próprio")
            prompt = f"""Responda à pergunta abaixo com base no seu próprio conhecimento.
Se não tiver segurança, deixe claro que a resposta é geral e não baseada em documentos da base.
Responda de forma objetiva em no máximo 6 frases.

Histórico recente:
{recent_history}

Pergunta:
{question}"""

        logger.debug(f"Prompt preparado ({len(prompt)} caracteres)")

        try:
            logger.debug(f"Chamando LLM ({OLLAMA_MODEL})...")

            if not ollama:
                raise OllamaException("Ollama não está disponível")

            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": MAX_RESPONSE_TOKENS, "temperature": 0.2},
                stream=False
            )

            answer = response.get("message", {}).get("content", "")

            if not answer:
                logger.warning("LLM retornou resposta vazia")
                answer = "Desculpe, não consegui gerar uma resposta."

            logger.debug(f"Resposta gerada ({len(answer)} caracteres)")

        except Exception as e:
            logger.error(f"Erro ao chamar LLM: {e}")
            raise OllamaException(f"Erro ao gerar resposta com LLM: {e}") from e

        try:
            logger.debug("Salvando interação no histórico...")
            save_chat_history(
                session_id=session_id,
                question=question,
                answer=answer,
                sources=None
            )
        except Exception as e:
            logger.warning(f"Erro ao salvar histórico (não crítico): {e}")

        logger.info(f"Chat processado com sucesso (Sessão: {session_id})")
        return answer, session_id

    except OllamaException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado no chat: {e}")
        raise OllamaException(f"Erro inesperado no chat: {e}") from e
