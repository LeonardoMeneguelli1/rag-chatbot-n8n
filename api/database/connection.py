import time
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
from logger import logger
from exceptions import DatabaseException


def get_connection(
    max_retries: int = 5,
    retry_delay: int = 2
) -> psycopg2.extensions.connection:
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=10
            )
            logger.info("Conexao com banco de dados estabelecida com sucesso")
            return conn
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Falha ao conectar ao banco (tentativa {attempt + 1}/{max_retries}). "
                    f"Aguardando {retry_delay}s... Erro: {e}"
                )
                time.sleep(retry_delay)
            else:
                logger.error(f"Falha permanente ao conectar ao banco após {max_retries} tentativas")
                raise DatabaseException(
                    f"Não foi possível conectar ao banco de dados após {max_retries} tentativas"
                ) from e


def init_db() -> None:
    try:
        conn = get_connection()
        cur = conn.cursor()

        try:
            logger.debug("Criando extensao pgvector...")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            logger.debug("Criando tabela documents...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    embedding vector(4096),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            logger.warning(
                "Pulando criacao de indice ivfflat para embedding(4096); "
                "se necessario, reduza dimensao ou use estrategia de indice compativel"
            )

            logger.debug("Criando tabela chat_history...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    sources TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_history_session_id
                ON chat_history(session_id);
            """)

            conn.commit()
            logger.info("Banco de dados inicializado com sucesso")

        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao inicializar banco: {e}")
            raise DatabaseException(f"Erro na inicializacao do banco: {e}") from e
        finally:
            cur.close()
            conn.close()

    except DatabaseException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado na inicializacao: {e}")
        raise DatabaseException(f"Erro inesperado na inicializacao: {e}") from e