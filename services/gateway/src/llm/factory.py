"""
TRJM Gateway - LLM Provider Factory
====================================
Factory for creating LLM provider instances based on configuration
"""

from typing import Optional

from ..core.config import settings
from ..core.logging import logger
from .mock import MockLLMProvider
from .openai import OpenAIProvider
from .provider import LLMProvider
from .vllm import VLLMProvider


class LLMProviderFactory:
    """
    Factory class for creating LLM provider instances.

    Provider selection is based on the LLM_PROVIDER environment variable.
    """

    _instance: Optional[LLMProvider] = None

    @classmethod
    def create(
        cls,
        provider_type: Optional[str] = None,
        **kwargs,
    ) -> LLMProvider:
        """
        Create an LLM provider instance.

        Args:
            provider_type: Provider type ('openai', 'vllm', 'mock')
                          Defaults to settings.llm_provider
            **kwargs: Additional provider-specific arguments

        Returns:
            Configured LLMProvider instance

        Raises:
            ValueError: If provider type is unknown
        """
        provider_type = (provider_type or settings.llm_provider).lower()

        logger.info("Creating LLM provider", provider_type=provider_type)

        if provider_type == "openai":
            return OpenAIProvider(**kwargs)

        elif provider_type == "vllm":
            return VLLMProvider(**kwargs)

        elif provider_type == "mock":
            return MockLLMProvider(**kwargs)

        else:
            raise ValueError(f"Unknown LLM provider type: {provider_type}")

    @classmethod
    def get_provider(cls) -> LLMProvider:
        """
        Get the singleton LLM provider instance.

        Creates a new instance if one doesn't exist.

        Returns:
            LLMProvider singleton instance
        """
        if cls._instance is None:
            cls._instance = cls.create()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    @classmethod
    async def close(cls) -> None:
        """Close the provider and reset singleton."""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None


def get_llm_provider() -> LLMProvider:
    """
    Dependency function to get the LLM provider.

    Usage:
        @app.get("/translate")
        async def translate(llm: LLMProvider = Depends(get_llm_provider)):
            ...
    """
    return LLMProviderFactory.get_provider()
