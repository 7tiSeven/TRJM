"""
TRJM Gateway - Translator Agent
=================================
Produces draft translations with glossary and token protection
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
    GlossaryTermApplied,
    ProtectedTokenStatus,
    StylePreset,
    TranslatorInput,
    TranslatorOutput,
)


# Style instruction templates
STYLE_INSTRUCTIONS = {
    StylePreset.FORMAL_MSA: """Use formal Modern Standard Arabic (الفصحى). Maintain elevated register.
Avoid colloquialisms. Use formal pronouns and verb forms.
Suitable for official documents, academic texts, and formal correspondence.""",
    StylePreset.NEUTRAL: """Use clear, professional Modern Standard Arabic.
Balance formality with accessibility. Suitable for business communication.""",
    StylePreset.MARKETING: """Use engaging, persuasive Arabic. Adapt idioms for cultural relevance.
Maintain brand voice while ensuring natural Arabic flow.
May use slightly less formal register for accessibility.""",
    StylePreset.GOVERNMENT_MEMO: """Use highly formal bureaucratic Arabic. Follow official terminology.
Use passive voice where appropriate. Maintain impersonal tone.
Reference official document conventions.""",
}


class TranslatorAgent:
    """
    Translator agent for producing translations.

    Responsibilities:
    - Generate accurate translations
    - Enforce glossary terms
    - Preserve protected tokens unchanged
    - Apply style guidelines
    """

    def __init__(self, llm_provider: LLMProvider, prompts_path: Optional[str] = None):
        """
        Initialize the translator agent.

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
            "system_prompt": """You are an expert translator specializing in English-Arabic translation.
You produce high-quality, culturally appropriate translations.

CRITICAL RULES:
1. PROTECTED TOKENS: Never translate items marked as protected. Keep them exactly as provided.
2. GLOSSARY: Always use the provided glossary translations for specified terms.
3. PRESERVE FORMATTING: Maintain markdown, lists, paragraphs, and structure.
4. CULTURAL ADAPTATION: Adapt idioms and expressions appropriately for the target culture.
5. CONSISTENCY: Use consistent terminology throughout the translation.

For Arabic (ar) translations:
- Use Modern Standard Arabic (MSA) unless otherwise specified
- Apply proper Arabic punctuation (، ؛ ؟)
- Ensure correct RTL text flow
- Handle mixed LTR/RTL content properly (numbers, Latin text)

Your response must be a valid JSON object with:
1. translation: The translated text
2. protected_tokens_preserved: List of {original, preserved: bool}
3. glossary_terms_applied: List of {source_term, applied_translation, count}
4. translator_notes: Any notes about translation decisions""",
            "user_prompt_template": """Translate the following text from {source_language} to {target_language}.

STYLE: {style_preset}
{style_instructions}

PROTECTED TOKENS (DO NOT TRANSLATE - keep exactly as shown):
{protected_tokens}

GLOSSARY (USE THESE EXACT TRANSLATIONS):
{glossary_entries}

SOURCE TEXT:
---
{input_text}
---

Provide your translation as a JSON object.""",
        }

    async def translate(self, input_data: TranslatorInput) -> TranslatorOutput:
        """
        Generate a translation.

        Args:
            input_data: Translator input with text and configuration

        Returns:
            TranslatorOutput with translation and metadata
        """
        logger.info(
            "Translator agent processing",
            text_length=len(input_data.text),
            source=input_data.source_language.value,
            target=input_data.target_language.value,
            style=input_data.style_preset.value,
        )

        # Format protected tokens
        protected_tokens_str = (
            "\n".join(f"- {token}" for token in input_data.protected_tokens)
            if input_data.protected_tokens
            else "None"
        )

        # Format glossary entries
        glossary_str = (
            "\n".join(
                f"- {entry.source} → {entry.target}" for entry in input_data.glossary_entries
            )
            if input_data.glossary_entries
            else "None"
        )

        # Get style instructions
        style_instructions = STYLE_INSTRUCTIONS.get(
            input_data.style_preset, STYLE_INSTRUCTIONS[StylePreset.NEUTRAL]
        )

        # Build user prompt
        user_prompt = self.prompts["user_prompt_template"].format(
            source_language=input_data.source_language.value,
            target_language=input_data.target_language.value,
            style_preset=input_data.style_preset.value,
            style_instructions=style_instructions,
            protected_tokens=protected_tokens_str,
            glossary_entries=glossary_str,
            input_text=input_data.text,
        )

        messages = [
            Message(role=MessageRole.SYSTEM, content=self.prompts["system_prompt"]),
            Message(role=MessageRole.USER, content=user_prompt),
        ]

        # Call LLM
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=8192,
            response_format=ResponseFormat(type=ResponseFormatType.JSON_OBJECT),
        )

        # Parse response
        try:
            data = json.loads(response.content)
            return self._parse_output(data)
        except json.JSONDecodeError as e:
            logger.error("Translator agent: Failed to parse JSON response", error=str(e))
            # Try to extract translation from raw response
            return TranslatorOutput(
                translation=response.content,
                translator_notes="Warning: Failed to parse structured response",
            )

    def _parse_output(self, data: dict) -> TranslatorOutput:
        """Parse LLM response into TranslatorOutput."""
        # Parse protected tokens status
        protected_tokens = []
        for token in data.get("protected_tokens_preserved", []):
            if isinstance(token, dict):
                protected_tokens.append(
                    ProtectedTokenStatus(
                        original=token.get("original", ""),
                        preserved=token.get("preserved", True),
                    )
                )

        # Parse glossary terms applied
        glossary_terms = []
        for term in data.get("glossary_terms_applied", []):
            if isinstance(term, dict):
                glossary_terms.append(
                    GlossaryTermApplied(
                        source_term=term.get("source_term", ""),
                        applied_translation=term.get("applied_translation", ""),
                        count=term.get("count", 1),
                    )
                )

        return TranslatorOutput(
            translation=data.get("translation", ""),
            protected_tokens_preserved=protected_tokens,
            glossary_terms_applied=glossary_terms,
            translator_notes=data.get("translator_notes"),
        )
