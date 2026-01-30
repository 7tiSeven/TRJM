"""
TRJM Gateway - vLLM Provider
=============================
vLLM OpenAI-compatible API implementation for local inference
"""

import time
from typing import Any, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..core.config import settings
from ..core.logging import logger
from .provider import (
    CompletionChoice,
    CompletionResponse,
    CompletionUsage,
    LLMInvalidResponseError,
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    Message,
    MessageRole,
    ResponseFormat,
)


class VLLMProvider(LLMProvider):
    """
    vLLM OpenAI-compatible API provider.

    Supports local inference with Qwen2.5 and other models via vLLM's
    OpenAI-compatible API endpoint.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        """
        Initialize vLLM provider.

        Args:
            base_url: vLLM server URL (defaults to settings)
            api_key: API key (optional for vLLM, defaults to settings)
            model: Default model (defaults to settings)
            timeout: Request timeout in seconds (defaults to settings)
            max_retries: Max retry attempts (defaults to settings)
        """
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key or "not-needed"
        self._default_model = model or settings.llm_model
        self.timeout = timeout or settings.llm_timeout
        self.max_retries = max_retries or settings.llm_max_retries

        # Create HTTP client
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "not-needed":
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers=headers,
        )

        logger.info(
            "vLLM provider initialized",
            base_url=self.base_url,
            model=self._default_model,
        )

    @property
    def provider_name(self) -> str:
        return "vllm"

    @property
    def default_model(self) -> str:
        return self._default_model

    @retry(
        retry=retry_if_exception_type(LLMTimeoutError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
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
        Generate a chat completion using vLLM's OpenAI-compatible API.

        Args:
            messages: List of chat messages
            model: Model to use (defaults to configured model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Response format specification
            **kwargs: Additional parameters

        Returns:
            CompletionResponse with generated content
        """
        model = model or self._default_model

        # Build request payload (OpenAI-compatible format)
        payload = {
            "model": model,
            "messages": [msg.to_dict() for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Add response format if specified
        if response_format:
            payload["response_format"] = response_format.to_dict()

        # Add any additional parameters
        payload.update(kwargs)

        logger.debug(
            "vLLM request",
            model=model,
            message_count=len(messages),
            temperature=temperature,
        )

        try:
            start_time = time.time()

            response = await self.client.post(
                "/chat/completions",
                json=payload,
            )

            duration_ms = (time.time() - start_time) * 1000

            # Handle errors
            if response.status_code >= 500:
                raise LLMProviderError(
                    f"vLLM server error: {response.status_code}",
                    provider=self.provider_name,
                    status_code=response.status_code,
                )

            if response.status_code >= 400:
                error_detail = response.text
                raise LLMProviderError(
                    f"vLLM error ({response.status_code}): {error_detail}",
                    provider=self.provider_name,
                    status_code=response.status_code,
                )

            response.raise_for_status()

            # Parse response
            data = response.json()
            result = self._parse_response(data)

            logger.debug(
                "vLLM response",
                model=model,
                tokens=result.usage.total_tokens,
                duration_ms=round(duration_ms, 2),
            )

            return result

        except httpx.TimeoutException as e:
            logger.warning("vLLM request timeout", model=model)
            raise LLMTimeoutError(
                f"Request timed out after {self.timeout}s",
                provider=self.provider_name,
            ) from e

        except httpx.ConnectError as e:
            logger.error("vLLM connection error", base_url=self.base_url)
            raise LLMProviderError(
                f"Cannot connect to vLLM server at {self.base_url}",
                provider=self.provider_name,
            ) from e

        except Exception as e:
            if isinstance(e, LLMProviderError):
                raise
            logger.exception("vLLM unexpected error", error=str(e))
            raise LLMProviderError(
                f"Unexpected error: {str(e)}",
                provider=self.provider_name,
            ) from e

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Parse vLLM API response into CompletionResponse."""
        try:
            choices = []
            for choice_data in data.get("choices", []):
                message_data = choice_data.get("message", {})
                choices.append(
                    CompletionChoice(
                        index=choice_data.get("index", 0),
                        message=Message(
                            role=MessageRole(message_data.get("role", "assistant")),
                            content=message_data.get("content", ""),
                        ),
                        finish_reason=choice_data.get("finish_reason", "stop"),
                    )
                )

            usage_data = data.get("usage", {})
            usage = CompletionUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

            return CompletionResponse(
                id=data.get("id", ""),
                model=data.get("model", self._default_model),
                choices=choices,
                usage=usage,
                created=data.get("created", int(time.time())),
            )

        except (KeyError, TypeError, ValueError) as e:
            raise LLMInvalidResponseError(
                f"Failed to parse response: {str(e)}",
                provider=self.provider_name,
            ) from e

    async def health_check(self) -> bool:
        """Check if vLLM server is accessible."""
        try:
            response = await self.client.get("/health")
            if response.status_code == 200:
                return True

            # Try models endpoint as fallback
            response = await self.client.get("/v1/models")
            return response.status_code == 200

        except Exception as e:
            logger.warning("vLLM health check failed", error=str(e))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
