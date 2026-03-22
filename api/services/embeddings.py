import ollama
from typing import List
from logger import logger
from exceptions import EmbeddingException
from config import OLLAMA_MODEL


def generate_embedding(text: str) -> List[float]:
    if not text or not text.strip():
        raise EmbeddingException("Texto não pode estar vazio")

    try:
        logger.debug(f"Gerando embedding usando modelo {OLLAMA_MODEL}...")

        try:
            response = ollama.embeddings(model=OLLAMA_MODEL, prompt=text)
            embedding = response.get("embedding")
            if embedding:
                logger.debug(f"Embedding gerado com sucesso (dimensões: {len(embedding)})")
                return embedding
        except Exception as method1_error:
            logger.debug(f"Método 1 falhou, tentando método alternativo: {method1_error}")

            response = ollama.embed(model=OLLAMA_MODEL, input=text)
            embedding = response.get("embeddings", [[]])[0]
            if embedding:
                logger.debug(f"Embedding gerado com sucesso via método alternativo")
                return embedding

        raise EmbeddingException("Resposta inválida do serviço de embeddings")

    except ollama.ResponseError as e:
        logger.error(f"Erro do Ollama ao gerar embedding: {e}")
        raise EmbeddingException(f"Erro do Ollama: {e}") from e
    except Exception as e:
        logger.error(f"Erro inesperado ao gerar embedding: {e}")
        raise EmbeddingException(f"Erro ao gerar embedding: {e}") from e
