"""
TRJM Gateway - LLM Provider Abstract Interface
===============================================
Base class for all LLM providers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel


# =============================================================================
# Message Types
# =============================================================================


class MessageRole(str, Enum):
    """Chat message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """Chat message structure."""

    role: MessageRole
    content: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for API calls."""
        return {"role": self.role.value, "content": self.content}


# =============================================================================
# Response Types
# =============================================================================


@dataclass
class CompletionChoice:
    """Single completion choice."""

    index: int
    message: Message
    finish_reason: str


@dataclass
class CompletionUsage:
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class CompletionResponse:
    """LLM completion response."""

    id: str
    model: str
    choices: List[CompletionChoice]
    usage: CompletionUsage
    created: int

    @property
    def content(self) -> str:
        """Get the content of the first choice."""
        if self.choices:
            return self.choices[0].message.content
        return ""

    @property
    def finish_reason(self) -> str:
        """Get the finish reason of the first choice."""
        if self.choices:
            return self.choices[0].finish_reason
        return ""


# =============================================================================
# Response Format
# =============================================================================


class ResponseFormatType(str, Enum):
    """Response format types."""

    TEXT = "text"
    JSON_OBJECT = "json_object"


@dataclass
class ResponseFormat:
    """Response format specification."""

    type: ResponseFormatType = ResponseFormatType.TEXT

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for API calls."""
        return {"type": self.type.value}


# =============================================================================
# Provider Interface
# =============================================================================


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers must implement this interface to ensure
    provider-agnostic operation of the translation pipeline.
    """

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[ResponseFormat] = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        """
        Generate a chat completion.

        Args:
            messages: List of chat messages
            model: Model identifier (uses default if not specified)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional response format specification
            **kwargs: Additional provider-specific parameters

        Returns:
            CompletionResponse with generated content

        Raises:
            LLMProviderError: If the request fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and accessible.

        Returns:
            True if healthy, False otherwise
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model for this provider."""
        pass


# =============================================================================
# Exceptions
# =============================================================================


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retry_after = retry_after


class LLMAuthenticationError(LLMProviderError):
    """Authentication failed with the LLM provider."""

    pass


class LLMRateLimitError(LLMProviderError):
    """Rate limit exceeded."""

    pass


class LLMTimeoutError(LLMProviderError):
    """Request timed out."""

    pass


class LLMContentFilterError(LLMProviderError):
    """Content was filtered by the provider."""

    pass


class LLMInvalidResponseError(LLMProviderError):
    """Invalid response from the provider."""

    pass
