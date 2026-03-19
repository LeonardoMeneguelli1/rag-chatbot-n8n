"""Serviço de busca vetorial com RAG (Retrieval-Augmented Generation)."""

import time
import json
import uuid
from typing import Any, List, Optional
from database.connection import get_connection
from services.embeddings import generate_embedding
from logger import logger
from exceptions import DatabaseException, EmbeddingException


GLOBAL_RAG_MIN_SIMILARITY = 0.3
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 250
DEFAULT_SEARCH_CANDIDATES = 8


def chunk_text(
    content: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list[str]:
    normalized = " ".join(content.split())
    if not normalized:
        return []

    if len(normalized) <= chunk_size:
        return [normalized]

    chunks = []
    start = 0

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(normalized):
            break

        start = max(end - chunk_overlap, start + 1)

    return chunks


def _insert_document_chunk(content: str, metadata: Optional[dict] = None) -> int:
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
        return doc_id

    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao inserir chunk do documento: {e}")
        raise DatabaseException(f"Erro ao salvar chunk do documento: {e}") from e

    finally:
        cursor.close()
        conn.close()


def save_document_chunks(
    content: str,
    metadata: Optional[dict] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
) -> dict[str, Any]:
    try:
        base_metadata = dict(metadata or {})
        chunks = chunk_text(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        if not chunks:
            raise DatabaseException("Conteúdo vazio para indexação")

        document_group_id = str(uuid.uuid4())
        chunk_ids = []

        logger.debug(
            f"Salvando documento em chunks ({len(content)} caracteres, {len(chunks)} chunk(s))..."
        )

        for index, chunk in enumerate(chunks, start=1):
            chunk_metadata = {
                **base_metadata,
                "document_group_id": document_group_id,
                "chunk_index": index,
                "chunk_count": len(chunks),
            }
            chunk_ids.append(_insert_document_chunk(chunk, chunk_metadata))

        logger.info(
            f"Documento salvo em {len(chunks)} chunk(s) com sucesso "
            f"(Grupo: {document_group_id})"
        )

        return {
            "document_group_id": document_group_id,
            "chunk_ids": chunk_ids,
            "chunk_count": len(chunks),
        }

    except (DatabaseException, EmbeddingException):
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar documento em chunks: {e}")
        raise DatabaseException(f"Erro inesperado: {e}") from e


def search_similar_chunks(
    text: str,
    limit: int = 5,
    search_candidates: int = DEFAULT_SEARCH_CANDIDATES,
    max_retries: int = 5,
    retry_delay: int = 2,
    exclude_session_docs: bool = False,
    min_similarity: float = 0.0
) -> list[dict[str, Any]]:
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

        logger.debug(
            "Executando busca vetorial "
            f"(limit={limit}, search_candidates={search_candidates}, "
            f"exclude_session_docs={exclude_session_docs})..."
        )

        where_clause = "WHERE metadata->>'session_id' IS NULL" if exclude_session_docs else ""
        cursor.execute(
            f"""
            SELECT content, metadata, 1 - (embedding <-> %s) as similarity
            FROM documents
            {where_clause}
            ORDER BY embedding <-> %s
            LIMIT %s
            """,
            (embedding_str, embedding_str, search_candidates)
        )

        rows = cursor.fetchall()
        logger.debug(f"Busca retornou {len(rows)} candidato(s)")

        if not rows:
            logger.warning("Nenhum documento encontrado para a busca")
            return []

        results = []
        seen_keys = set()

        for content, metadata, similarity in rows:
            metadata_dict = metadata or {}
            if isinstance(metadata_dict, str):
                metadata_dict = json.loads(metadata_dict)

            if min_similarity > 0.0 and similarity < min_similarity:
                continue

            dedupe_key = (
                metadata_dict.get("document_group_id"),
                metadata_dict.get("chunk_index"),
                content[:120],
            )
            if dedupe_key in seen_keys:
                continue

            seen_keys.add(dedupe_key)
            results.append(
                {
                    "content": content,
                    "metadata": metadata_dict,
                    "similarity": float(similarity),
                }
            )

            if len(results) >= limit:
                break

        logger.debug(f"Busca retornou {len(results)} resultado(s) finais")
        return results

    except Exception as e:
        logger.error(f"Erro ao executar busca vetorial: {e}")
        raise DatabaseException(f"Erro na busca vetorial: {e}") from e

    finally:
        cursor.close()
        conn.close()


def search_similar(
    text: str,
    limit: int = 5,
    max_retries: int = 5,
    retry_delay: int = 2,
    exclude_session_docs: bool = False,
    min_similarity: float = 0.0
) -> Optional[str]:
    results = search_similar_chunks(
        text=text,
        limit=limit,
        max_retries=max_retries,
        retry_delay=retry_delay,
        exclude_session_docs=exclude_session_docs,
        min_similarity=min_similarity,
    )

    if not results:
        return None

    return "\n\n---\n\n".join(item["content"] for item in results)


def get_latest_session_document(session_id: str) -> Optional[str]:
    try:
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT metadata->>'document_group_id', content
                FROM documents
                WHERE metadata->>'session_id' = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (session_id,)
            )

            row = cursor.fetchone()
            if not row:
                return None

            document_group_id, fallback_content = row
            if not document_group_id:
                return fallback_content

            cursor.execute(
                """
                SELECT content
                FROM documents
                WHERE metadata->>'document_group_id' = %s
                ORDER BY (metadata->>'chunk_index')::int ASC, id ASC
                """,
                (document_group_id,)
            )

            chunks = [chunk_row[0] for chunk_row in cursor.fetchall()]
            return "\n\n".join(chunks) if chunks else fallback_content

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

        doc_id = _insert_document_chunk(content, metadata)

        logger.info(f"Documento salvo com sucesso (ID: {doc_id})")
        return doc_id

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
