"""
TRJM Gateway - Router Agent
============================
Analyzes input text to determine language, content type, and translation strategy
"""

import json
from typing import Optional

import yaml

from ....core.logging import logger
from ....llm.provider import (
    LLMProvider,
    Message,
    MessageRole,
    ResponseFormat,
    ResponseFormatType,
)
from ..schemas import (
    ContentType,
    FormalityLevel,
    LanguageCode,
    RouterInput,
    RouterOutput,
    SpecialElement,
    SpecialElementType,
    StylePreset,
)


class RouterAgent:
    """
    Router agent for analyzing input text.

    Responsibilities:
    - Detect source language
    - Detect content type (email, legal, technical, etc.)
    - Identify special elements that need protection
    - Recommend translation style and strategy
    """

    def __init__(self, llm_provider: LLMProvider, prompts_path: Optional[str] = None):
        """
        Initialize the router agent.

        Args:
            llm_provider: LLM provider instance
            prompts_path: Path to prompts YAML file
        """
        self.llm = llm_provider
        self.prompts = self._load_prompts(prompts_path)

    def _load_prompts(self, path: Optional[str]) -> dict:
        """Load prompt templates from YAML."""
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Failed to load prompts from {path}: {e}")

        # Default prompts
        return {
            "system_prompt": """You are a language analysis and routing agent for an enterprise translation system.
Your task is to analyze the input text and provide structured analysis.

You must respond with a valid JSON object containing:
1. source_language: The detected source language (ISO 639-1 code: en, ar, fr, de, es)
2. source_language_confidence: Confidence score 0.0-1.0
3. content_type: One of [general, email, legal, technical, marketing, ui_strings, government]
4. formality_level: One of [informal, neutral, formal, highly_formal]
5. special_elements: List of detected special elements
6. recommended_style: One of [formal_msa, neutral, marketing, government_memo]
7. complexity_score: Text complexity 0.0-1.0
8. notes: Any special observations

Special elements to detect:
- URLs (type: url)
- Email addresses (type: email)
- Placeholders like {variable} or {{variable}} (type: placeholder)
- Code blocks (type: code)
- HTML tags (type: html)
- Bracketed segments [DO NOT TRANSLATE] (type: bracketed)
- Numbers with units (type: number)
- Dates and times (type: date)
- Currency amounts (type: currency)
- Named entities (type: entity)
- Technical terms (type: technical_term)

For each special element, specify: type, value, protect (boolean)""",
            "user_prompt_template": """Analyze the following text for translation routing:

---
{input_text}
---

Target language: {target_language}
{style_hint}

Respond with a JSON object following the schema exactly.""",
        }

    async def analyze(self, input_data: RouterInput) -> RouterOutput:
        """
        Analyze input text and determine routing strategy.

        Args:
            input_data: Router input containing text and target language

        Returns:
            RouterOutput with analysis results
        """
        logger.info(
            "Router agent analyzing",
            text_length=len(input_data.text),
            target_language=input_data.target_language.value,
        )

        # Build messages
        style_hint = ""
        if input_data.style_hint:
            style_hint = f"Style preference: {input_data.style_hint.value}"

        user_prompt = self.prompts["user_prompt_template"].format(
            input_text=input_data.text[:5000],  # Limit for analysis
            target_language=input_data.target_language.value,
            style_hint=style_hint,
        )

        messages = [
            Message(role=MessageRole.SYSTEM, content=self.prompts["system_prompt"]),
            Message(role=MessageRole.USER, content=user_prompt),
        ]

        # Call LLM
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
            response_format=ResponseFormat(type=ResponseFormatType.JSON_OBJECT),
        )

        # Parse response
        try:
            data = json.loads(response.content)
            return self._parse_output(data)
        except json.JSONDecodeError as e:
            logger.error("Router agent: Failed to parse JSON response", error=str(e))
            # Return default analysis
            return self._get_default_output(input_data)

    def _parse_output(self, data: dict) -> RouterOutput:
        """Parse LLM response into RouterOutput."""
        # Parse special elements
        special_elements = []
        for elem in data.get("special_elements", []):
            try:
                special_elements.append(
                    SpecialElement(
                        type=SpecialElementType(elem.get("type", "entity")),
                        value=elem.get("value", ""),
                        protect=elem.get("protect", True),
                    )
                )
            except (ValueError, KeyError):
                continue

        # Map string values to enums safely
        source_lang = data.get("source_language", "en")
        try:
            source_language = LanguageCode(source_lang)
        except ValueError:
            source_language = LanguageCode.ENGLISH

        content_type_str = data.get("content_type", "general")
        try:
            content_type = ContentType(content_type_str)
        except ValueError:
            content_type = ContentType.GENERAL

        formality_str = data.get("formality_level", "neutral")
        try:
            formality_level = FormalityLevel(formality_str)
        except ValueError:
            formality_level = FormalityLevel.NEUTRAL

        style_str = data.get("recommended_style", "neutral")
        try:
            recommended_style = StylePreset(style_str)
        except ValueError:
            recommended_style = StylePreset.NEUTRAL

        return RouterOutput(
            source_language=source_language,
            source_language_confidence=float(data.get("source_language_confidence", 0.9)),
            content_type=content_type,
            formality_level=formality_level,
            special_elements=special_elements,
            recommended_style=recommended_style,
            complexity_score=float(data.get("complexity_score", 0.5)),
            notes=data.get("notes"),
        )

    def _get_default_output(self, input_data: RouterInput) -> RouterOutput:
        """Return default analysis when LLM fails."""
        return RouterOutput(
            source_language=LanguageCode.ENGLISH,
            source_language_confidence=0.5,
            content_type=ContentType.GENERAL,
            formality_level=FormalityLevel.NEUTRAL,
            special_elements=[],
            recommended_style=input_data.style_hint or StylePreset.NEUTRAL,
            complexity_score=0.5,
            notes="Default analysis due to LLM error",
        )
