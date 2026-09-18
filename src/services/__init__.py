# Namespace package for service-layer wrappers
from __future__ import annotations

from typing import Optional

from config import Config
from utils import LLMService


_global_llm_service: Optional[LLMService] = None


def get_global_llm_service() -> LLMService:
    # Create the shared LLM service on first use, not at import time.
    global _global_llm_service
    if _global_llm_service is None:
        _global_llm_service = LLMService(Config())
    return _global_llm_service


class LazyLLMService:
    # Backward-compatible proxy for modules importing global_llm_service.

    def __getattr__(self, name):
        return getattr(get_global_llm_service(), name)

    def invoke(self, *args, **kwargs):
        return get_global_llm_service().invoke(*args, **kwargs)

    def print_statistics(self, *args, **kwargs):
        return get_global_llm_service().print_statistics(*args, **kwargs)


global_llm_service = LazyLLMService()
