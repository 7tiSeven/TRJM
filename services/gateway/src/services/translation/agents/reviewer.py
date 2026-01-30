"""
TRJM Gateway - Reviewer/QA Agent
==================================
Validates translation quality and provides corrections
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
    IssueCategory,
    IssueSeverity,
    QAIssue,
    ReviewerInput,
    ReviewerOutput,
    RiskySpan,
)


class ReviewerAgent:
    """
    Reviewer/QA agent for validating translations.

    Responsibilities:
    - Validate meaning preservation
    - Check for omissions and additions
    - Verify numbers, dates, currencies
    - Ensure glossary compliance
    - Check protected token preservation
    - Validate Arabic punctuation and RTL
    - Detect leftover source language
    - Calculate confidence score
    """

    def __init__(self, llm_provider: LLMProvider, prompts_path: Optional[str] = None):
        """
        Initialize the reviewer agent.

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
            "system_prompt": """You are a senior translation quality assurance specialist.
Your task is to review translations and identify issues.

REVIEW CRITERIA:
1. MEANING PRESERVATION: Does the translation convey the same meaning?
2. OMISSIONS: Is any content missing from the translation?
3. ADDITIONS: Is there any content added that wasn't in the source?
4. NUMBERS & DATES: Are all numbers, dates, and currencies accurate?
5. NAMED ENTITIES: Are proper nouns and names handled correctly?
6. GLOSSARY COMPLIANCE: Were glossary terms used correctly?
7. PROTECTED TOKENS: Were protected tokens preserved unchanged?
8. GRAMMAR & SPELLING: Is the target language grammatically correct?
9. PUNCTUATION: Is punctuation appropriate for the target language?
10. RTL/FORMATTING: Is RTL text properly formatted?
11. LEFTOVER SOURCE: Is there any untranslated source language text?
12. CULTURAL APPROPRIATENESS: Is the translation culturally suitable?

For Arabic specifically, check:
- Correct Arabic punctuation (، ؛ ؟ instead of , ; ?)
- Proper RTL flow
- No broken Arabic letters or encoding issues
- Appropriate formality level

CONFIDENCE SCORING:
- 0.90-1.00: Excellent, no issues found
- 0.75-0.89: Good, minor issues only
- 0.50-0.74: Acceptable, some corrections needed
- 0.25-0.49: Poor, significant issues
- 0.00-0.24: Unacceptable, major rework needed

If you find issues, provide a corrected translation.

Respond with JSON containing:
1. confidence_score (0.0-1.0)
2. issues (list with category, severity, description)
3. corrected_translation
4. glossary_compliance (boolean)
5. protected_tokens_intact (boolean)
6. risky_spans (segments needing human review)
7. reviewer_notes""",
            "user_prompt_template": """Review the following translation:

SOURCE TEXT ({source_language}):
---
{source_text}
---

TRANSLATION ({target_language}):
---
{translation}
---

PROTECTED TOKENS (should be unchanged):
{protected_tokens}

GLOSSARY TERMS (should be used):
{glossary_entries}

STYLE: {style_preset}

Provide your review as a JSON object.""",
        }

    async def review(self, input_data: ReviewerInput) -> ReviewerOutput:
        """
        Review a translation for quality.

        Args:
            input_data: Reviewer input with source text and translation

        Returns:
            ReviewerOutput with QA results
        """
        logger.info(
            "Reviewer agent processing",
            source_length=len(input_data.source_text),
            translation_length=len(input_data.translation),
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

        # Build user prompt
        user_prompt = self.prompts["user_prompt_template"].format(
            source_language=input_data.source_language.value,
            target_language=input_data.target_language.value,
            source_text=input_data.source_text,
            translation=input_data.translation,
            protected_tokens=protected_tokens_str,
            glossary_entries=glossary_str,
            style_preset=input_data.style_preset.value,
        )

        messages = [
            Message(role=MessageRole.SYSTEM, content=self.prompts["system_prompt"]),
            Message(role=MessageRole.USER, content=user_prompt),
        ]

        # Call LLM
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=4096,
            response_format=ResponseFormat(type=ResponseFormatType.JSON_OBJECT),
        )

        # Parse response
        try:
            data = json.loads(response.content)
            return self._parse_output(data, input_data.translation)
        except json.JSONDecodeError as e:
            logger.error("Reviewer agent: Failed to parse JSON response", error=str(e))
            # Return default review with original translation
            return ReviewerOutput(
                confidence_score=0.7,
                issues=[
                    QAIssue(
                        category=IssueCategory.GRAMMAR,
                        severity=IssueSeverity.MINOR,
                        description="Unable to perform automated review",
                    )
                ],
                corrected_translation=input_data.translation,
                glossary_compliance=True,
                protected_tokens_intact=True,
                reviewer_notes="Warning: Automated review failed",
            )

    def _parse_output(self, data: dict, original_translation: str) -> ReviewerOutput:
        """Parse LLM response into ReviewerOutput."""
        # Parse issues
        issues = []
        for issue in data.get("issues", []):
            if isinstance(issue, dict):
                try:
                    issues.append(
                        QAIssue(
                            category=IssueCategory(issue.get("category", "grammar")),
                            severity=IssueSeverity(issue.get("severity", "minor")),
                            description=issue.get("description", ""),
                            source_segment=issue.get("source_segment"),
                            translation_segment=issue.get("translation_segment"),
                            suggested_fix=issue.get("suggested_fix"),
                        )
                    )
                except (ValueError, KeyError):
                    continue

        # Parse risky spans
        risky_spans = []
        for span in data.get("risky_spans", []):
            if isinstance(span, dict):
                risky_spans.append(
                    RiskySpan(
                        text=span.get("text", ""),
                        reason=span.get("reason", ""),
                        risk_level=span.get("risk_level", "medium"),
                    )
                )

        # Get corrected translation or use original
        corrected = data.get("corrected_translation", original_translation)
        if not corrected:
            corrected = original_translation

        return ReviewerOutput(
            confidence_score=float(data.get("confidence_score", 0.8)),
            issues=issues,
            corrected_translation=corrected,
            glossary_compliance=data.get("glossary_compliance", True),
            protected_tokens_intact=data.get("protected_tokens_intact", True),
            risky_spans=risky_spans,
            reviewer_notes=data.get("reviewer_notes"),
        )
