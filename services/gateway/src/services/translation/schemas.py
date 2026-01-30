"""
TRJM Gateway - Translation Pipeline Schemas
=============================================
Pydantic schemas for translation pipeline data
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class LanguageCode(str, Enum):
    """Supported language codes."""

    AUTO = "auto"
    ENGLISH = "en"
    ARABIC = "ar"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"


class StylePreset(str, Enum):
    """Translation style presets."""

    FORMAL_MSA = "formal_msa"
    NEUTRAL = "neutral"
    MARKETING = "marketing"
    GOVERNMENT_MEMO = "government_memo"


class ContentType(str, Enum):
    """Detected content types."""

    GENERAL = "general"
    EMAIL = "email"
    LEGAL = "legal"
    TECHNICAL = "technical"
    MARKETING = "marketing"
    UI_STRINGS = "ui_strings"
    GOVERNMENT = "government"


class FormalityLevel(str, Enum):
    """Formality levels."""

    INFORMAL = "informal"
    NEUTRAL = "neutral"
    FORMAL = "formal"
    HIGHLY_FORMAL = "highly_formal"


class IssueSeverity(str, Enum):
    """QA issue severity levels."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    SUGGESTION = "suggestion"


class IssueCategory(str, Enum):
    """QA issue categories."""

    MEANING = "meaning"
    OMISSION = "omission"
    ADDITION = "addition"
    NUMBERS = "numbers"
    ENTITIES = "entities"
    GLOSSARY = "glossary"
    PROTECTED_TOKENS = "protected_tokens"
    GRAMMAR = "grammar"
    PUNCTUATION = "punctuation"
    FORMATTING = "formatting"
    LEFTOVER_SOURCE = "leftover_source"
    CULTURAL = "cultural"


class SpecialElementType(str, Enum):
    """Special element types for protection."""

    URL = "url"
    EMAIL = "email"
    PLACEHOLDER = "placeholder"
    CODE = "code"
    HTML = "html"
    BRACKETED = "bracketed"
    NUMBER = "number"
    DATE = "date"
    CURRENCY = "currency"
    ENTITY = "entity"
    TECHNICAL_TERM = "technical_term"


# =============================================================================
# Common Schemas
# =============================================================================


class Position(BaseModel):
    """Text position."""

    start: int
    end: int


class SpecialElement(BaseModel):
    """Special element detected in text."""

    type: SpecialElementType
    value: str
    position: Optional[Position] = None
    protect: bool = True


class GlossaryEntry(BaseModel):
    """Glossary term entry."""

    source: str
    target: str
    case_sensitive: bool = False
    context: Optional[str] = None


# =============================================================================
# Router Agent Schemas
# =============================================================================


class RouterInput(BaseModel):
    """Input to the router agent."""

    text: str
    target_language: LanguageCode = LanguageCode.ARABIC
    style_hint: Optional[StylePreset] = None


class RouterOutput(BaseModel):
    """Output from the router agent."""

    source_language: LanguageCode
    source_language_confidence: float = Field(ge=0, le=1)
    content_type: ContentType
    formality_level: FormalityLevel
    special_elements: List[SpecialElement] = Field(default_factory=list)
    recommended_style: StylePreset
    complexity_score: float = Field(ge=0, le=1)
    notes: Optional[str] = None


# =============================================================================
# Translator Agent Schemas
# =============================================================================


class TranslatorInput(BaseModel):
    """Input to the translator agent."""

    text: str
    source_language: LanguageCode
    target_language: LanguageCode
    style_preset: StylePreset
    protected_tokens: List[str] = Field(default_factory=list)
    glossary_entries: List[GlossaryEntry] = Field(default_factory=list)


class ProtectedTokenStatus(BaseModel):
    """Status of a protected token."""

    original: str
    preserved: bool


class GlossaryTermApplied(BaseModel):
    """Applied glossary term."""

    source_term: str
    applied_translation: str
    count: int


class TranslatorOutput(BaseModel):
    """Output from the translator agent."""

    translation: str
    protected_tokens_preserved: List[ProtectedTokenStatus] = Field(default_factory=list)
    glossary_terms_applied: List[GlossaryTermApplied] = Field(default_factory=list)
    translator_notes: Optional[str] = None


# =============================================================================
# Reviewer Agent Schemas
# =============================================================================


class ReviewerInput(BaseModel):
    """Input to the reviewer agent."""

    source_text: str
    translation: str
    source_language: LanguageCode
    target_language: LanguageCode
    style_preset: StylePreset
    protected_tokens: List[str] = Field(default_factory=list)
    glossary_entries: List[GlossaryEntry] = Field(default_factory=list)


class QAIssue(BaseModel):
    """Quality assurance issue."""

    category: IssueCategory
    severity: IssueSeverity
    description: str
    source_segment: Optional[str] = None
    translation_segment: Optional[str] = None
    suggested_fix: Optional[str] = None


class RiskySpan(BaseModel):
    """Segment that may need human review."""

    text: str
    reason: str
    position: Optional[Position] = None
    risk_level: str = "medium"


class ReviewerOutput(BaseModel):
    """Output from the reviewer agent."""

    confidence_score: float = Field(ge=0, le=1)
    issues: List[QAIssue] = Field(default_factory=list)
    corrected_translation: str
    glossary_compliance: bool
    protected_tokens_intact: bool
    risky_spans: List[RiskySpan] = Field(default_factory=list)
    reviewer_notes: Optional[str] = None


# =============================================================================
# Post-Processor Schemas
# =============================================================================


class PostProcessorInput(BaseModel):
    """Input to the post-processor."""

    translation: str
    target_language: LanguageCode
    protected_tokens: List[str] = Field(default_factory=list)


class ChangeRecord(BaseModel):
    """Record of a post-processing change."""

    type: str
    original: str
    replacement: str
    count: int


class PostProcessorOutput(BaseModel):
    """Output from the post-processor."""

    processed_text: str
    changes_made: List[ChangeRecord] = Field(default_factory=list)
    rtl_markers_added: int = 0
    formatting_preserved: bool = True


# =============================================================================
# Pipeline Schemas
# =============================================================================


class TranslationRequest(BaseModel):
    """Translation API request."""

    text: str = Field(..., min_length=1, max_length=100000)
    source_language: LanguageCode = LanguageCode.AUTO
    target_language: LanguageCode = LanguageCode.ARABIC
    style_preset: StylePreset = StylePreset.NEUTRAL
    glossary_id: Optional[str] = None
    protected_patterns: List[str] = Field(default_factory=list)


class QAReport(BaseModel):
    """Full QA report."""

    confidence_score: float
    confidence_level: str  # excellent, good, acceptable, poor, unacceptable
    issues: List[QAIssue]
    glossary_compliance: bool
    protected_tokens_intact: bool
    risky_spans: List[RiskySpan]
    reviewer_notes: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class PipelineMetadata(BaseModel):
    """Pipeline execution metadata."""

    model_used: str
    retries: int
    total_tokens: int
    processing_time_ms: int
    agent_timings: Dict[str, int]


class TranslationResponse(BaseModel):
    """Translation API response."""

    job_id: str
    translation: str
    source_language: LanguageCode
    target_language: LanguageCode
    confidence: float
    qa_report: QAReport
    processing_time_ms: int
    retries: int
    metadata: Optional[PipelineMetadata] = None


class TranslationResult(BaseModel):
    """Internal translation result."""

    translation: str
    source_language: LanguageCode
    target_language: LanguageCode
    confidence: float
    qa_report: QAReport
    retries: int
    metadata: PipelineMetadata
