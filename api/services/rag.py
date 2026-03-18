"""Serviço de busca vetorial com RAG (Retrieval-Augmented Generation)."""

import time
import json
from typing import List, Optional
from database.connection import get_connection
from services.embeddings import generate_embedding
from logger import logger
from exceptions import DatabaseException, EmbeddingException


GLOBAL_RAG_MIN_SIMILARITY = 0.3


def search_similar(
    text: str,
    limit: int = 5,
    max_retries: int = 5,
    retry_delay: int = 2,
    exclude_session_docs: bool = False,
    min_similarity: float = 0.0
) -> Optional[str]:
    try:
        logger.debug("Gerando embedding para busca vetorial")
        embedding = generate_embedding(text)

    except EmbeddingException as e:
        logger.error(f"Erro ao gerar embedding para busca: {e}")
        raise

    conn = None
    for attempt in range(max_retries):
        try:
            conn = get_connection()
            if conn:
                logger.debug("Conexão estabelecida para busca vetorial")
                break
        except DatabaseException as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Tentativa {attempt + 1}/{max_retries} falhou. "
                    f"Aguardando {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                logger.error(f"Não foi possível conectar para busca após {max_retries} tentativas")
                raise DatabaseException(
                    "Não foi possível conectar ao banco para busca"
                ) from e
    
    if not conn:
        raise DatabaseException("Conexão com banco não estabelecida")

    try:
        cursor = conn.cursor()
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        logger.debug(f"Executando busca vetorial (limit={limit}, exclude_session_docs={exclude_session_docs})...")
        where_clause = "WHERE metadata->>'session_id' IS NULL" if exclude_session_docs else ""
        cursor.execute(
            f"""
            SELECT content, 1 - (embedding <-> %s) as similarity
            FROM documents
            {where_clause}
            ORDER BY embedding <-> %s
            LIMIT %s
            """,
            (embedding_str, embedding_str, limit)
        )
        
        results = cursor.fetchall()
        logger.debug(f"Busca retornou {len(results)} resultado(s)")

        if not results:
            logger.warning("Nenhum documento encontrado para a busca")
            return None

        if min_similarity > 0.0:
            results = [(content, sim) for content, sim in results if sim >= min_similarity]
            logger.debug(f"{len(results)} resultado(s) passaram o threshold de similaridade ({min_similarity})")

        if not results:
            logger.warning("Nenhum resultado acima do threshold de similaridade")
            return None

        concatenated = "\n\n---\n\n".join([r[0] for r in results])
        return concatenated

    except Exception as e:
        logger.error(f"Erro ao executar busca vetorial: {e}")
        raise DatabaseException(f"Erro na busca vetorial: {e}") from e

    finally:
        cursor.close()
        conn.close()


def get_latest_session_document(session_id: str) -> Optional[str]:
    try:
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT content
                FROM documents
                WHERE metadata->>'session_id' = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (session_id,)
            )

            row = cursor.fetchone()
            return row[0] if row else None

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logger.warning(f"Erro ao recuperar documento da sessão {session_id}: {e}")
        return None


def save_document(
    content: str,
    metadata: Optional[dict] = None
) -> int:
    try:
        logger.debug(f"Salvando documento ({len(content)} caracteres)...")

        embedding = generate_embedding(content)

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO documents (content, metadata, embedding)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (content, json.dumps(metadata or {}), str(embedding))
            )
            
            doc_id = cursor.fetchone()[0]
            conn.commit()

            logger.info(f"Documento salvo com sucesso (ID: {doc_id})")
            return doc_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao inserir documento: {e}")
            raise DatabaseException(f"Erro ao salvar documento: {e}") from e

        finally:
            cursor.close()
            conn.close()

    except (DatabaseException, EmbeddingException):
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar documento: {e}")
        raise DatabaseException(f"Erro inesperado: {e}") from e


def save_chat_history(
    session_id: str,
    question: str,
    answer: str,
    sources: Optional[List[str]] = None
) -> None:
    try:
        logger.debug(f"Salvando histórico da conversa para sessão {session_id}")

        conn = get_connection()
        cursor = conn.cursor()

        try:
            sources_str = ", ".join(sources) if sources else None

            cursor.execute(
                """
                INSERT INTO chat_history (session_id, question, answer, sources)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, question, answer, sources_str)
            )

            conn.commit()
            logger.debug(f"Histórico salvo para sessão {session_id}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao salvar histórico: {e}")
            raise DatabaseException(f"Erro ao salvar histórico: {e}") from e

        finally:
            cursor.close()
            conn.close()

    except DatabaseException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar histórico: {e}")
        raise DatabaseException(f"Erro inesperado: {e}") from e


def get_recent_chat_history(session_id: str, limit: int = 4) -> list[tuple[str, str]]:
    try:
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT question, answer
                FROM chat_history
                WHERE session_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (session_id, limit)
            )

            rows = cursor.fetchall()
            rows.reverse()
            return rows

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logger.warning(f"Erro ao recuperar histórico da sessão {session_id}: {e}")
        return []


def get_latest_scrape_document_by_url(url: str) -> Optional[int]:
    try:
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT id
                FROM documents
                WHERE metadata->>'source' = 'scrape'
                  AND metadata->>'url' = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (url,)
            )

            row = cursor.fetchone()
            return row[0] if row else None

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logger.warning(f"Erro ao buscar scrape por URL ({url}): {e}")
        return None
