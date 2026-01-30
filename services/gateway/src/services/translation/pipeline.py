"""
TRJM Gateway - Translation Pipeline Orchestrator
=================================================
Orchestrates the multi-agent translation pipeline
"""

import re
import time
from typing import List, Optional

from ...core.config import settings
from ...core.logging import logger
from ...llm.factory import get_llm_provider
from ...llm.provider import LLMProvider
from .agents.post_processor import PostProcessorAgent
from .agents.reviewer import ReviewerAgent
from .agents.router import RouterAgent
from .agents.translator import TranslatorAgent
from .schemas import (
    GlossaryEntry,
    IssueCategory,
    IssueSeverity,
    LanguageCode,
    PipelineMetadata,
    PostProcessorInput,
    QAIssue,
    QAReport,
    ReviewerInput,
    RouterInput,
    StylePreset,
    TranslationRequest,
    TranslationResult,
    TranslatorInput,
)


# Confidence level mapping
def get_confidence_level(score: float) -> str:
    """Map confidence score to level string."""
    if score >= 0.90:
        return "excellent"
    elif score >= 0.75:
        return "good"
    elif score >= 0.50:
        return "acceptable"
    elif score >= 0.25:
        return "poor"
    else:
        return "unacceptable"


# Default protected token patterns
DEFAULT_PROTECTED_PATTERNS = [
    r"\{[^}]+\}",  # {placeholders}
    r"\{\{[^}]+\}\}",  # {{placeholders}}
    r"%[sd]",  # %s, %d format strings
    r"https?://[^\s]+",  # URLs
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # Emails
    r"<[^>]+>",  # HTML tags
    r"\[DO NOT TRANSLATE\][^\[]*\[/DO NOT TRANSLATE\]",  # Bracketed segments
    r"`[^`]+`",  # Inline code
]


class TranslationPipeline:
    """
    Orchestrates the translation pipeline.

    Pipeline flow:
    1. Router Agent -> Analyze text, detect language and content type
    2. Translator Agent -> Generate draft translation
    3. Reviewer Agent -> QA validation and scoring
    4. If confidence < threshold -> Retry (max 2 times)
    5. Post-Processor -> Apply RTL fixes and typography
    6. Package result with QA report
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        confidence_threshold: float = 0.75,
        max_retries: int = 2,
    ):
        """
        Initialize the translation pipeline.

        Args:
            llm_provider: LLM provider instance (uses factory if None)
            confidence_threshold: Minimum confidence to accept translation
            max_retries: Maximum retry attempts for low-confidence translations
        """
        self.llm = llm_provider or get_llm_provider()
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries

        # Initialize agents
        self.router = RouterAgent(self.llm)
        self.translator = TranslatorAgent(self.llm)
        self.reviewer = ReviewerAgent(self.llm)
        self.post_processor = PostProcessorAgent()  # Rule-based by default

        logger.info(
            "Translation pipeline initialized",
            provider=self.llm.provider_name,
            model=self.llm.default_model,
            confidence_threshold=confidence_threshold,
            max_retries=max_retries,
        )

    async def translate(
        self,
        request: TranslationRequest,
        glossary_entries: Optional[List[GlossaryEntry]] = None,
    ) -> TranslationResult:
        """
        Execute the full translation pipeline.

        Args:
            request: Translation request
            glossary_entries: Optional glossary entries to enforce

        Returns:
            TranslationResult with translation and QA report
        """
        start_time = time.time()
        agent_timings = {}
        total_tokens = 0
        retries = 0

        glossary_entries = glossary_entries or []

        logger.info(
            "Translation pipeline started",
            text_length=len(request.text),
            source_language=request.source_language.value,
            target_language=request.target_language.value,
            style=request.style_preset.value,
        )

        # Step 1: Router Agent - Analyze input
        router_start = time.time()
        router_input = RouterInput(
            text=request.text,
            target_language=request.target_language,
            style_hint=request.style_preset,
        )
        router_output = await self.router.analyze(router_input)
        agent_timings["router_ms"] = int((time.time() - router_start) * 1000)

        # Determine source language
        source_language = (
            router_output.source_language
            if request.source_language == LanguageCode.AUTO
            else request.source_language
        )

        # Extract protected tokens from text
        protected_tokens = self._extract_protected_tokens(
            request.text,
            request.protected_patterns,
            router_output.special_elements,
        )

        # Determine style (use router recommendation if no explicit preference)
        style = request.style_preset or router_output.recommended_style

        logger.debug(
            "Router analysis complete",
            detected_language=source_language.value,
            content_type=router_output.content_type.value,
            protected_tokens_count=len(protected_tokens),
            complexity=router_output.complexity_score,
        )

        # Step 2: Translator Agent - Generate translation
        translator_start = time.time()
        translator_input = TranslatorInput(
            text=request.text,
            source_language=source_language,
            target_language=request.target_language,
            style_preset=style,
            protected_tokens=protected_tokens,
            glossary_entries=glossary_entries,
        )
        translator_output = await self.translator.translate(translator_input)
        agent_timings["translator_ms"] = int((time.time() - translator_start) * 1000)

        # Step 3: Reviewer Agent - QA validation
        reviewer_start = time.time()
        reviewer_input = ReviewerInput(
            source_text=request.text,
            translation=translator_output.translation,
            source_language=source_language,
            target_language=request.target_language,
            style_preset=style,
            protected_tokens=protected_tokens,
            glossary_entries=glossary_entries,
        )
        reviewer_output = await self.reviewer.review(reviewer_input)
        agent_timings["reviewer_ms"] = int((time.time() - reviewer_start) * 1000)

        # Step 4: Retry if confidence is low
        current_translation = reviewer_output.corrected_translation
        current_confidence = reviewer_output.confidence_score
        current_issues = reviewer_output.issues

        while current_confidence < self.confidence_threshold and retries < self.max_retries:
            retries += 1
            logger.info(
                "Retrying translation due to low confidence",
                confidence=current_confidence,
                retry_number=retries,
            )

            # Re-translate with stricter constraints
            retry_translator_input = TranslatorInput(
                text=request.text,
                source_language=source_language,
                target_language=request.target_language,
                style_preset=style,
                protected_tokens=protected_tokens,
                glossary_entries=glossary_entries,
            )
            retry_output = await self.translator.translate(retry_translator_input)

            # Re-review
            retry_reviewer_input = ReviewerInput(
                source_text=request.text,
                translation=retry_output.translation,
                source_language=source_language,
                target_language=request.target_language,
                style_preset=style,
                protected_tokens=protected_tokens,
                glossary_entries=glossary_entries,
            )
            retry_review = await self.reviewer.review(retry_reviewer_input)

            # Use the better result
            if retry_review.confidence_score > current_confidence:
                current_translation = retry_review.corrected_translation
                current_confidence = retry_review.confidence_score
                current_issues = retry_review.issues
                reviewer_output = retry_review

        # Step 5: Post-Processor - Apply final formatting
        post_processor_start = time.time()
        post_processor_input = PostProcessorInput(
            translation=current_translation,
            target_language=request.target_language,
            protected_tokens=protected_tokens,
        )
        post_processor_output = await self.post_processor.process(post_processor_input)
        agent_timings["post_processor_ms"] = int((time.time() - post_processor_start) * 1000)

        # Build QA report
        qa_report = QAReport(
            confidence_score=current_confidence,
            confidence_level=get_confidence_level(current_confidence),
            issues=current_issues,
            glossary_compliance=reviewer_output.glossary_compliance,
            protected_tokens_intact=reviewer_output.protected_tokens_intact,
            risky_spans=reviewer_output.risky_spans,
            reviewer_notes=reviewer_output.reviewer_notes,
            metrics={
                "source_char_count": len(request.text),
                "translation_char_count": len(post_processor_output.processed_text),
                "length_ratio": len(post_processor_output.processed_text) / len(request.text)
                if request.text
                else 0,
                "total_issues": len(current_issues),
                "critical_issues": sum(
                    1 for i in current_issues if i.severity == IssueSeverity.CRITICAL
                ),
                "major_issues": sum(
                    1 for i in current_issues if i.severity == IssueSeverity.MAJOR
                ),
                "minor_issues": sum(
                    1 for i in current_issues if i.severity == IssueSeverity.MINOR
                ),
                "suggestions": sum(
                    1 for i in current_issues if i.severity == IssueSeverity.SUGGESTION
                ),
            },
        )

        # Build metadata
        processing_time_ms = int((time.time() - start_time) * 1000)
        metadata = PipelineMetadata(
            model_used=self.llm.default_model,
            retries=retries,
            total_tokens=total_tokens,
            processing_time_ms=processing_time_ms,
            agent_timings=agent_timings,
        )

        logger.info(
            "Translation pipeline completed",
            confidence=current_confidence,
            confidence_level=qa_report.confidence_level,
            retries=retries,
            processing_time_ms=processing_time_ms,
            issues_count=len(current_issues),
        )

        return TranslationResult(
            translation=post_processor_output.processed_text,
            source_language=source_language,
            target_language=request.target_language,
            confidence=current_confidence,
            qa_report=qa_report,
            retries=retries,
            metadata=metadata,
        )

    def _extract_protected_tokens(
        self,
        text: str,
        custom_patterns: List[str],
        special_elements,
    ) -> List[str]:
        """Extract all tokens that should be protected from translation."""
        protected = set()

        # Extract from special elements
        for element in special_elements:
            if element.protect:
                protected.add(element.value)

        # Extract using default patterns
        for pattern in DEFAULT_PROTECTED_PATTERNS:
            try:
                matches = re.findall(pattern, text)
                protected.update(matches)
            except re.error:
                continue

        # Extract using custom patterns
        for pattern in custom_patterns:
            try:
                matches = re.findall(pattern, text)
                protected.update(matches)
            except re.error:
                logger.warning(f"Invalid custom pattern: {pattern}")
                continue

        return list(protected)


# =============================================================================
# Singleton Pipeline Instance
# =============================================================================

_pipeline: Optional[TranslationPipeline] = None


def get_pipeline() -> TranslationPipeline:
    """Get or create the translation pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = TranslationPipeline()
    return _pipeline
