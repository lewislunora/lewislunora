import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class PlatformConnector(ABC):
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.name = "base"

    @abstractmethod
    def post(self, text: str, media_urls: list = None) -> dict:
        pass

    @abstractmethod
    def verify(self) -> bool:
        pass

    def truncate(self, text: str, max_len: int = 2000) -> str:
        if len(text) > max_len:
            return text[:max_len-3] + "..."
        return text
