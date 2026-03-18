"""Exceções customizadas da aplicação."""


class ChatbotException(Exception):
    pass


class DatabaseException(ChatbotException):
    pass


class EmbeddingException(ChatbotException):
    pass


class ParseException(ChatbotException):
    pass


class ScrapeException(ChatbotException):
    pass


class OllamaException(ChatbotException):
    pass
