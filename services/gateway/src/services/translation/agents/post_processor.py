"""
TRJM Gateway - Post-Processor Agent
=====================================
Applies final typography, RTL fixes, and formatting corrections
"""

import json
import re
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
from ..schemas import ChangeRecord, LanguageCode, PostProcessorInput, PostProcessorOutput


# Arabic punctuation mappings
ARABIC_PUNCTUATION = {
    ",": "،",
    ";": "؛",
    "?": "؟",
}


class PostProcessorAgent:
    """
    Post-processor agent for final text cleanup.

    Responsibilities:
    - Replace Western punctuation with Arabic equivalents
    - Fix RTL formatting issues
    - Add RTL/LTR markers for mixed content
    - Fix spacing around punctuation
    - Preserve protected tokens
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None, prompts_path: Optional[str] = None):
        """
        Initialize the post-processor agent.

        Args:
            llm_provider: Optional LLM provider (uses rule-based processing if None)
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

        return {
            "system_prompt": """You are a text post-processing specialist for Arabic and multilingual content.
Apply final formatting corrections without changing the meaning.

TASKS:
1. Replace Western punctuation with Arabic equivalents (comma → ،, semicolon → ؛, question mark → ؟)
2. Fix RTL formatting and add LTR/RTL markers where needed
3. Remove extra spaces and fix spacing around punctuation
4. Use proper Arabic quotation marks: « » or " "
5. Preserve protected tokens exactly as-is

DO NOT:
- Change the meaning of any text
- Modify protected tokens
- Add or remove content
- Translate anything

Respond with JSON: {processed_text, changes_made, rtl_markers_added, formatting_preserved}""",
            "user_prompt_template": """Apply post-processing to the following {target_language} text:

---
{translation}
---

PROTECTED TOKENS (keep exactly as-is):
{protected_tokens}

Apply typography, punctuation, and RTL formatting corrections.""",
        }

    async def process(self, input_data: PostProcessorInput) -> PostProcessorOutput:
        """
        Post-process a translation.

        Args:
            input_data: Post-processor input with translation

        Returns:
            PostProcessorOutput with processed text
        """
        logger.info(
            "Post-processor processing",
            text_length=len(input_data.translation),
            target_language=input_data.target_language.value,
        )

        # For Arabic, use rule-based processing with optional LLM enhancement
        if input_data.target_language == LanguageCode.ARABIC:
            return self._process_arabic(input_data)

        # For other languages, minimal processing
        return PostProcessorOutput(
            processed_text=input_data.translation,
            changes_made=[],
            rtl_markers_added=0,
            formatting_preserved=True,
        )

    def _process_arabic(self, input_data: PostProcessorInput) -> PostProcessorOutput:
        """Apply Arabic-specific post-processing rules."""
        text = input_data.translation
        changes = []
        rtl_markers_added = 0

        # Create a map of protected token positions
        protected_positions = set()
        for token in input_data.protected_tokens:
            start = 0
            while True:
                pos = text.find(token, start)
                if pos == -1:
                    break
                for i in range(pos, pos + len(token)):
                    protected_positions.add(i)
                start = pos + 1

        # Replace punctuation (avoiding protected tokens)
        processed_chars = []
        for i, char in enumerate(text):
            if i in protected_positions:
                processed_chars.append(char)
            elif char in ARABIC_PUNCTUATION:
                replacement = ARABIC_PUNCTUATION[char]
                processed_chars.append(replacement)
                # Track change
                existing_change = next(
                    (c for c in changes if c.type == "punctuation" and c.original == char),
                    None,
                )
                if existing_change:
                    existing_change.count += 1
                else:
                    changes.append(
                        ChangeRecord(
                            type="punctuation",
                            original=char,
                            replacement=replacement,
                            count=1,
                        )
                    )
            else:
                processed_chars.append(char)

        text = "".join(processed_chars)

        # Fix spacing around Arabic punctuation (no space before, space after)
        text = re.sub(r"\s+([،؛؟])", r"\1", text)  # Remove space before
        text = re.sub(r"([،؛؟])(?!\s|$)", r"\1 ", text)  # Add space after if missing

        # Fix double spaces
        original_text = text
        text = re.sub(r" {2,}", " ", text)
        if text != original_text:
            changes.append(
                ChangeRecord(
                    type="spacing",
                    original="  ",
                    replacement=" ",
                    count=len(original_text) - len(text),
                )
            )

        # Handle mixed LTR/RTL content
        # Add RLM (Right-to-Left Mark) after numbers in Arabic context
        def add_rtl_marker(match):
            nonlocal rtl_markers_added
            # Check if this is within a protected token
            start = match.start()
            if any(start + i in protected_positions for i in range(len(match.group()))):
                return match.group()
            rtl_markers_added += 1
            return match.group() + "\u200f"  # RLM

        # Add markers after standalone numbers followed by Arabic text
        text = re.sub(
            r"(\d+)(?=\s*[\u0600-\u06FF])",
            add_rtl_marker,
            text,
        )

        # Replace straight quotes with Arabic guillemets for quoted text
        # Match text between quotes
        def replace_quotes(match):
            quoted = match.group(1) or match.group(2)
            return f"«{quoted}»"

        # Only if not in protected tokens
        if not any('"' in token or "'" in token for token in input_data.protected_tokens):
            original_text = text
            text = re.sub(r'"([^"]+)"', replace_quotes, text)
            text = re.sub(r"'([^']+)'", replace_quotes, text)
            if text != original_text:
                changes.append(
                    ChangeRecord(
                        type="typography",
                        original='"..."',
                        replacement="«...»",
                        count=1,
                    )
                )

        return PostProcessorOutput(
            processed_text=text.strip(),
            changes_made=changes,
            rtl_markers_added=rtl_markers_added,
            formatting_preserved=True,
        )

    async def process_with_llm(self, input_data: PostProcessorInput) -> PostProcessorOutput:
        """
        Post-process using LLM for complex cases.

        Args:
            input_data: Post-processor input

        Returns:
            PostProcessorOutput with LLM-processed text
        """
        if not self.llm:
            return await self.process(input_data)

        # Format protected tokens
        protected_tokens_str = (
            "\n".join(f"- {token}" for token in input_data.protected_tokens)
            if input_data.protected_tokens
            else "None"
        )

        user_prompt = self.prompts["user_prompt_template"].format(
            target_language=input_data.target_language.value,
            translation=input_data.translation,
            protected_tokens=protected_tokens_str,
        )

        messages = [
            Message(role=MessageRole.SYSTEM, content=self.prompts["system_prompt"]),
            Message(role=MessageRole.USER, content=user_prompt),
        ]

        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=8192,
            response_format=ResponseFormat(type=ResponseFormatType.JSON_OBJECT),
        )

        try:
            data = json.loads(response.content)
            changes = [
                ChangeRecord(**c) for c in data.get("changes_made", []) if isinstance(c, dict)
            ]
            return PostProcessorOutput(
                processed_text=data.get("processed_text", input_data.translation),
                changes_made=changes,
                rtl_markers_added=data.get("rtl_markers_added", 0),
                formatting_preserved=data.get("formatting_preserved", True),
            )
        except json.JSONDecodeError:
            logger.warning("Post-processor: LLM response not valid JSON, using rule-based")
            return await self.process(input_data)
