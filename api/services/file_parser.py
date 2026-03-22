import pandas as pd
import pdfplumber
import io
from typing import Optional
from logger import logger
from exceptions import ParseException


def parse_pdf(file_content: bytes) -> str:
    try:
        logger.debug("Parseando arquivo PDF...")
        text = ""

        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            logger.debug(f"PDF tem {len(pdf.pages)} página(s)")
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- Página {i+1} ---\n{page_text}"

        if not text.strip():
            logger.warning("Nenhum texto foi extraído do PDF")
            raise ParseException("Não foi possível extrair texto do PDF")

        logger.debug(f"PDF parseado com sucesso ({len(text)} caracteres)")
        return text.strip()

    except Exception as e:
        logger.error(f"Erro ao parsear PDF: {e}")
        raise ParseException(f"Erro ao parsear PDF: {e}") from e


def parse_csv(file_content: bytes, encoding: str = "utf-8") -> str:
    try:
        logger.debug("Parseando arquivo CSV...")

        df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
        logger.debug(f"CSV parseado com {len(df)} linhas e {len(df.columns)} colunas")

        text = df.to_string()
        return text

    except Exception as e:
        logger.error(f"Erro ao parsear CSV: {e}")
        raise ParseException(f"Erro ao parsear CSV: {e}") from e


def parse_excel(file_content: bytes) -> str:
    try:
        logger.debug("Parseando arquivo Excel...")

        excel_file = io.BytesIO(file_content)
        xls = pd.ExcelFile(excel_file)
        logger.debug(f"Excel tem {len(xls.sheet_names)} planilha(s)")

        text = ""
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            text += f"\n--- Planilha: {sheet_name} ---\n{df.to_string()}\n"

        return text.strip()

    except Exception as e:
        logger.error(f"Erro ao parsear Excel: {e}")
        raise ParseException(f"Erro ao parsear Excel: {e}") from e


def parse_file(file_content: bytes, filename: str) -> str:
    filename_lower = filename.lower()

    try:
        if filename_lower.endswith(".pdf"):
            return parse_pdf(file_content)
        elif filename_lower.endswith(".csv"):
            return parse_csv(file_content)
        elif filename_lower.endswith((".xlsx", ".xls")):
            return parse_excel(file_content)
        else:
            logger.error(f"Formato de arquivo não suportado: {filename}")
            raise ParseException(
                f"Formato não suportado: {filename}. "
                f"Suportados: PDF, CSV, XLSX, XLS"
            )
    except ParseException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao parsear {filename}: {e}")
        raise ParseException(f"Erro ao parsear arquivo: {e}") from e
