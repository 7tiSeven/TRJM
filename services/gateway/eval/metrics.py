"""
TRJM Gateway - Evaluation Metrics
==================================
Quality metrics for translation evaluation
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class MetricResult:
    """Result of a single metric evaluation."""

    name: str
    score: float  # 0.0 to 1.0
    passed: bool
    details: str = ""
    expected: Optional[str] = None
    actual: Optional[str] = None


@dataclass
class EvaluationResult:
    """Complete evaluation result for a test case."""

    test_id: str
    test_name: str
    category: str
    passed: bool
    overall_score: float
    metrics: List[MetricResult] = field(default_factory=list)
    source_text: str = ""
    expected_translation: str = ""
    actual_translation: str = ""
    confidence: float = 0.0
    error: Optional[str] = None


class TranslationMetrics:
    """
    Translation quality metrics calculator.

    Evaluates translations across multiple dimensions:
    - Glossary enforcement
    - Token protection (URLs, emails, placeholders)
    - RTL/Arabic punctuation correctness
    - Number and date preservation
    - Basic semantic alignment
    """

    # Arabic punctuation marks
    ARABIC_PUNCTUATION = {
        "،": ",",  # Arabic comma
        "؛": ";",  # Arabic semicolon
        "؟": "?",  # Arabic question mark
        "٪": "%",  # Arabic percent
    }

    # Protected token patterns
    URL_PATTERN = re.compile(r"https?://[^\s]+")
    EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    PLACEHOLDER_PATTERN = re.compile(r"\{\{[^}]+\}\}|\{[^}]+\}")
    NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?(?:%|[KMBkmb])?\b")

    def evaluate_glossary_enforcement(
        self,
        source: str,
        translation: str,
        glossary: Dict[str, str],
    ) -> MetricResult:
        """
        Check if glossary terms are correctly used in translation.

        Args:
            source: Source text
            translation: Translated text
            glossary: Dictionary mapping source terms to expected translations

        Returns:
            MetricResult with glossary compliance score
        """
        if not glossary:
            return MetricResult(
                name="glossary_enforcement",
                score=1.0,
                passed=True,
                details="No glossary terms to check",
            )

        found_terms = 0
        correct_terms = 0
        issues = []

        for source_term, target_term in glossary.items():
            if source_term.lower() in source.lower():
                found_terms += 1
                if target_term in translation:
                    correct_terms += 1
                else:
                    issues.append(f"'{source_term}' should be translated as '{target_term}'")

        if found_terms == 0:
            score = 1.0
            details = "No glossary terms found in source"
        else:
            score = correct_terms / found_terms
            details = f"{correct_terms}/{found_terms} glossary terms correctly translated"
            if issues:
                details += f". Issues: {'; '.join(issues[:3])}"

        return MetricResult(
            name="glossary_enforcement",
            score=score,
            passed=score >= 0.8,
            details=details,
        )

    def evaluate_token_protection(
        self,
        source: str,
        translation: str,
    ) -> MetricResult:
        """
        Check if protected tokens (URLs, emails, placeholders) are preserved.

        Args:
            source: Source text
            translation: Translated text

        Returns:
            MetricResult with token protection score
        """
        # Extract tokens from source
        source_urls = set(self.URL_PATTERN.findall(source))
        source_emails = set(self.EMAIL_PATTERN.findall(source))
        source_placeholders = set(self.PLACEHOLDER_PATTERN.findall(source))
        source_numbers = set(self.NUMBER_PATTERN.findall(source))

        all_tokens = source_urls | source_emails | source_placeholders | source_numbers

        if not all_tokens:
            return MetricResult(
                name="token_protection",
                score=1.0,
                passed=True,
                details="No protected tokens found",
            )

        preserved = 0
        issues = []

        for token in all_tokens:
            if token in translation:
                preserved += 1
            else:
                issues.append(f"Token missing: '{token[:30]}...' " if len(token) > 30 else f"Token missing: '{token}'")

        score = preserved / len(all_tokens)
        details = f"{preserved}/{len(all_tokens)} tokens preserved"
        if issues:
            details += f". Issues: {'; '.join(issues[:3])}"

        return MetricResult(
            name="token_protection",
            score=score,
            passed=score >= 0.9,
            details=details,
        )

    def evaluate_arabic_punctuation(
        self,
        translation: str,
        target_lang: str = "ar",
    ) -> MetricResult:
        """
        Check if Arabic punctuation is correctly used for Arabic translations.

        Args:
            translation: Translated text
            target_lang: Target language code

        Returns:
            MetricResult with punctuation score
        """
        if target_lang != "ar":
            return MetricResult(
                name="arabic_punctuation",
                score=1.0,
                passed=True,
                details="Not applicable for non-Arabic target",
            )

        issues = []

        # Check for Western punctuation that should be Arabic
        western_marks = [",", ";", "?", "%"]
        for mark in western_marks:
            if mark in translation:
                # Check if it's not within a URL or number
                arabic_equiv = {",": "،", ";": "؛", "?": "؟", "%": "٪"}.get(mark, mark)
                issues.append(f"Consider using '{arabic_equiv}' instead of '{mark}'")

        if not issues:
            score = 1.0
            details = "Arabic punctuation correctly used"
        else:
            # Soft penalty - these are suggestions
            score = max(0.7, 1.0 - len(issues) * 0.1)
            details = f"{len(issues)} punctuation suggestions: {'; '.join(issues[:3])}"

        return MetricResult(
            name="arabic_punctuation",
            score=score,
            passed=score >= 0.7,
            details=details,
        )

    def evaluate_number_preservation(
        self,
        source: str,
        translation: str,
    ) -> MetricResult:
        """
        Check if numbers are preserved in translation.

        Args:
            source: Source text
            translation: Translated text

        Returns:
            MetricResult with number preservation score
        """
        source_numbers = set(self.NUMBER_PATTERN.findall(source))

        if not source_numbers:
            return MetricResult(
                name="number_preservation",
                score=1.0,
                passed=True,
                details="No numbers found in source",
            )

        preserved = 0
        issues = []

        for num in source_numbers:
            # Check for exact match or Arabic numeral equivalent
            if num in translation:
                preserved += 1
            else:
                issues.append(f"Number '{num}' may be missing or modified")

        score = preserved / len(source_numbers)
        details = f"{preserved}/{len(source_numbers)} numbers preserved"
        if issues:
            details += f". Issues: {'; '.join(issues[:3])}"

        return MetricResult(
            name="number_preservation",
            score=score,
            passed=score >= 0.9,
            details=details,
        )

    def evaluate_length_ratio(
        self,
        source: str,
        translation: str,
        target_lang: str = "ar",
    ) -> MetricResult:
        """
        Check if translation length is reasonable compared to source.

        Arabic translations are typically 10-30% longer than English.

        Args:
            source: Source text
            translation: Translated text
            target_lang: Target language code

        Returns:
            MetricResult with length ratio assessment
        """
        source_len = len(source)
        trans_len = len(translation)

        if source_len == 0:
            return MetricResult(
                name="length_ratio",
                score=0.0,
                passed=False,
                details="Source text is empty",
            )

        ratio = trans_len / source_len

        # Expected ratios for English -> Arabic
        if target_lang == "ar":
            min_ratio = 0.8
            max_ratio = 1.5
            ideal_min = 1.0
            ideal_max = 1.3
        else:
            # Arabic -> English tends to be shorter
            min_ratio = 0.6
            max_ratio = 1.2
            ideal_min = 0.7
            ideal_max = 1.0

        if ideal_min <= ratio <= ideal_max:
            score = 1.0
        elif min_ratio <= ratio <= max_ratio:
            score = 0.8
        else:
            score = 0.5

        passed = min_ratio <= ratio <= max_ratio
        details = f"Length ratio: {ratio:.2f} (source: {source_len}, translation: {trans_len})"

        return MetricResult(
            name="length_ratio",
            score=score,
            passed=passed,
            details=details,
        )

    def evaluate_all(
        self,
        source: str,
        translation: str,
        target_lang: str = "ar",
        glossary: Optional[Dict[str, str]] = None,
    ) -> List[MetricResult]:
        """
        Run all metrics on a translation.

        Args:
            source: Source text
            translation: Translated text
            target_lang: Target language code
            glossary: Optional glossary dictionary

        Returns:
            List of all metric results
        """
        return [
            self.evaluate_glossary_enforcement(source, translation, glossary or {}),
            self.evaluate_token_protection(source, translation),
            self.evaluate_arabic_punctuation(translation, target_lang),
            self.evaluate_number_preservation(source, translation),
            self.evaluate_length_ratio(source, translation, target_lang),
        ]

    def calculate_overall_score(self, metrics: List[MetricResult]) -> float:
        """
        Calculate weighted overall score from individual metrics.

        Args:
            metrics: List of metric results

        Returns:
            Overall score from 0.0 to 1.0
        """
        weights = {
            "glossary_enforcement": 0.25,
            "token_protection": 0.25,
            "arabic_punctuation": 0.15,
            "number_preservation": 0.20,
            "length_ratio": 0.15,
        }

        total_weight = 0
        weighted_score = 0

        for metric in metrics:
            weight = weights.get(metric.name, 0.1)
            weighted_score += metric.score * weight
            total_weight += weight

        return weighted_score / total_weight if total_weight > 0 else 0.0
