"""
TRJM Gateway - Mock LLM Provider
==================================
Mock provider for testing without real API calls
"""

import json
import time
from typing import Any, Dict, List, Optional

from ..core.logging import logger
from .provider import (
    CompletionChoice,
    CompletionResponse,
    CompletionUsage,
    LLMProvider,
    Message,
    MessageRole,
    ResponseFormat,
    ResponseFormatType,
)


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider for testing.

    Returns predefined or template-based responses without making real API calls.
    Useful for unit testing and development without API costs.
    """

    def __init__(
        self,
        model: str = "mock-model",
        responses: Optional[Dict[str, str]] = None,
        default_response: Optional[str] = None,
        latency_ms: int = 100,
    ):
        """
        Initialize mock provider.

        Args:
            model: Mock model name
            responses: Dict mapping prompts to responses
            default_response: Default response if no match found
            latency_ms: Simulated latency in milliseconds
        """
        self._model = model
        self.responses = responses or {}
        self.default_response = default_response or self._get_default_response()
        self.latency_ms = latency_ms
        self.call_history: List[Dict[str, Any]] = []

        logger.info("Mock LLM provider initialized", model=model)

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return self._model

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
        Generate a mock chat completion.

        Args:
            messages: List of chat messages
            model: Model (ignored for mock)
            temperature: Temperature (ignored for mock)
            max_tokens: Max tokens (ignored for mock)
            response_format: Response format
            **kwargs: Additional parameters (ignored)

        Returns:
            Mock CompletionResponse
        """
        # Simulate latency
        import asyncio

        await asyncio.sleep(self.latency_ms / 1000)

        # Record the call
        self.call_history.append(
            {
                "messages": [m.to_dict() for m in messages],
                "model": model or self._model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format.to_dict() if response_format else None,
                "timestamp": time.time(),
            }
        )

        # Get last user message for matching
        last_user_message = ""
        for msg in reversed(messages):
            if msg.role == MessageRole.USER:
                last_user_message = msg.content
                break

        # Find response
        response_content = self._find_response(last_user_message, response_format)

        logger.debug(
            "Mock LLM response",
            input_preview=last_user_message[:100] if last_user_message else "",
            response_preview=response_content[:100],
        )

        # Build response
        return CompletionResponse(
            id=f"mock-{int(time.time() * 1000)}",
            model=model or self._model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=Message(
                        role=MessageRole.ASSISTANT,
                        content=response_content,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=len(last_user_message.split()),
                completion_tokens=len(response_content.split()),
                total_tokens=len(last_user_message.split()) + len(response_content.split()),
            ),
            created=int(time.time()),
        )

    def _find_response(
        self, prompt: str, response_format: Optional[ResponseFormat]
    ) -> str:
        """Find matching response for prompt."""
        # Check for exact match
        if prompt in self.responses:
            return self.responses[prompt]

        # Check for partial match
        prompt_lower = prompt.lower()
        for key, value in self.responses.items():
            if key.lower() in prompt_lower:
                return value

        # Return format-appropriate default
        if response_format and response_format.type == ResponseFormatType.JSON_OBJECT:
            return self._get_json_response(prompt)

        return self.default_response

    def _get_json_response(self, prompt: str) -> str:
        """Generate a JSON response based on context."""
        prompt_lower = prompt.lower()

        # Router agent response
        if "analyze" in prompt_lower and "language" in prompt_lower:
            return json.dumps(
                {
                    "source_language": "en",
                    "source_language_confidence": 0.98,
                    "content_type": "general",
                    "formality_level": "neutral",
                    "special_elements": [],
                    "recommended_style": "neutral",
                    "complexity_score": 0.3,
                    "notes": "Mock analysis",
                }
            )

        # Translator agent response
        if "translate" in prompt_lower:
            return json.dumps(
                {
                    "translation": "هذا نص مترجم للاختبار",
                    "protected_tokens_preserved": [],
                    "glossary_terms_applied": [],
                    "translator_notes": "Mock translation",
                }
            )

        # Reviewer agent response
        if "review" in prompt_lower:
            return json.dumps(
                {
                    "confidence_score": 0.92,
                    "issues": [],
                    "corrected_translation": "هذا نص مترجم للاختبار",
                    "glossary_compliance": True,
                    "protected_tokens_intact": True,
                    "risky_spans": [],
                    "reviewer_notes": "Mock review - no issues found",
                }
            )

        # Post-processor response
        if "post-process" in prompt_lower or "typography" in prompt_lower:
            return json.dumps(
                {
                    "processed_text": "هذا نص مترجم للاختبار",
                    "changes_made": [],
                    "rtl_markers_added": 0,
                    "formatting_preserved": True,
                }
            )

        # Generic JSON response
        return json.dumps({"result": "mock_response", "success": True})

    def _get_default_response(self) -> str:
        """Get default non-JSON response."""
        return "This is a mock response from the test LLM provider."

    async def health_check(self) -> bool:
        """Mock health check always returns True."""
        return True

    async def close(self) -> None:
        """No cleanup needed for mock."""
        pass

    def reset(self) -> None:
        """Reset call history."""
        self.call_history.clear()

    def add_response(self, prompt: str, response: str) -> None:
        """Add a response mapping."""
        self.responses[prompt] = response
