"""
TRJM Gateway - Evaluation Runner
=================================
Run evaluation test cases against the translation pipeline
"""

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from .metrics import EvaluationResult, MetricResult, TranslationMetrics


class EvaluationRunner:
    """
    Run evaluation test cases against the translation pipeline.

    Usage:
        runner = EvaluationRunner()
        results = await runner.run_all()
        runner.print_report(results)
    """

    def __init__(
        self,
        test_cases_dir: Optional[Path] = None,
        pipeline=None,
    ):
        """
        Initialize the evaluation runner.

        Args:
            test_cases_dir: Path to directory containing test case JSON files
            pipeline: Translation pipeline instance (optional, will be created if not provided)
        """
        self.test_cases_dir = test_cases_dir or Path(__file__).parent / "test_cases"
        self.pipeline = pipeline
        self.metrics = TranslationMetrics()

    def load_test_cases(self) -> List[Dict]:
        """Load all test cases from JSON files."""
        test_cases = []

        if not self.test_cases_dir.exists():
            print(f"Warning: Test cases directory not found: {self.test_cases_dir}")
            return []

        for json_file in self.test_cases_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        test_cases.extend(data)
                    else:
                        test_cases.append(data)
            except Exception as e:
                print(f"Error loading {json_file}: {e}")

        return test_cases

    async def run_test_case(self, test_case: Dict) -> EvaluationResult:
        """
        Run a single test case.

        Args:
            test_case: Test case dictionary with source, expected, glossary, etc.

        Returns:
            EvaluationResult with all metrics
        """
        test_id = test_case.get("id", "unknown")
        test_name = test_case.get("name", "Unnamed Test")
        category = test_case.get("category", "general")
        source_text = test_case.get("source", "")
        expected_translation = test_case.get("expected", "")
        target_lang = test_case.get("target_language", "ar")
        glossary = test_case.get("glossary", {})

        try:
            # Get translation from pipeline
            if self.pipeline:
                from ..services.translation.schemas import (
                    LanguageCode,
                    StylePreset,
                    TranslationRequest,
                )

                request = TranslationRequest(
                    text=source_text,
                    source_language=LanguageCode.AUTO,
                    target_language=LanguageCode(target_lang),
                    style_preset=StylePreset.NEUTRAL,
                )

                # Convert glossary to list of entries
                glossary_entries = [
                    {"source_term": k, "target_term": v}
                    for k, v in glossary.items()
                ]

                result = await self.pipeline.translate(request, glossary_entries)
                actual_translation = result.translation
                confidence = result.confidence
            else:
                # Mock translation for testing metrics only
                actual_translation = expected_translation
                confidence = 0.9

            # Run all metrics
            metric_results = self.metrics.evaluate_all(
                source=source_text,
                translation=actual_translation,
                target_lang=target_lang,
                glossary=glossary,
            )

            # Calculate overall score
            overall_score = self.metrics.calculate_overall_score(metric_results)

            # Check if passed (all critical metrics passed and score above threshold)
            critical_metrics = ["glossary_enforcement", "token_protection"]
            critical_passed = all(
                m.passed for m in metric_results if m.name in critical_metrics
            )
            passed = critical_passed and overall_score >= 0.7

            return EvaluationResult(
                test_id=test_id,
                test_name=test_name,
                category=category,
                passed=passed,
                overall_score=overall_score,
                metrics=metric_results,
                source_text=source_text,
                expected_translation=expected_translation,
                actual_translation=actual_translation,
                confidence=confidence,
            )

        except Exception as e:
            return EvaluationResult(
                test_id=test_id,
                test_name=test_name,
                category=category,
                passed=False,
                overall_score=0.0,
                source_text=source_text,
                expected_translation=expected_translation,
                actual_translation="",
                error=str(e),
            )

    async def run_all(self) -> List[EvaluationResult]:
        """
        Run all test cases.

        Returns:
            List of evaluation results
        """
        test_cases = self.load_test_cases()
        results = []

        for test_case in test_cases:
            result = await self.run_test_case(test_case)
            results.append(result)

        return results

    def print_report(self, results: List[EvaluationResult]) -> None:
        """Print evaluation report to console."""
        print("\n" + "=" * 70)
        print("TRJM Translation Evaluation Report")
        print("=" * 70 + "\n")

        # Summary
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        avg_score = sum(r.overall_score for r in results) / total if total > 0 else 0

        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)" if total > 0 else "Passed: 0")
        print(f"Failed: {failed}")
        print(f"Average Score: {avg_score:.2%}")
        print()

        # Group by category
        categories: Dict[str, List[EvaluationResult]] = {}
        for result in results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)

        for category, cat_results in categories.items():
            print(f"\n--- Category: {category} ---")
            for result in cat_results:
                status = "PASS" if result.passed else "FAIL"
                print(f"  [{status}] {result.test_name} (Score: {result.overall_score:.2%})")

                if not result.passed:
                    if result.error:
                        print(f"        Error: {result.error}")
                    else:
                        for metric in result.metrics:
                            if not metric.passed:
                                print(f"        - {metric.name}: {metric.details}")

        print("\n" + "=" * 70)

    def export_results(self, results: List[EvaluationResult], output_path: Path) -> None:
        """Export results to JSON file."""
        data = []
        for result in results:
            result_dict = {
                "test_id": result.test_id,
                "test_name": result.test_name,
                "category": result.category,
                "passed": result.passed,
                "overall_score": result.overall_score,
                "confidence": result.confidence,
                "metrics": [asdict(m) for m in result.metrics],
            }
            if result.error:
                result_dict["error"] = result.error
            data.append(result_dict)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Results exported to {output_path}")


async def main():
    """Main entry point for running evaluations."""
    # Check if pipeline is available
    try:
        from ..services.translation.pipeline import get_pipeline

        pipeline = get_pipeline()
        print("Using actual translation pipeline")
    except Exception as e:
        print(f"Pipeline not available ({e}), running metrics-only evaluation")
        pipeline = None

    runner = EvaluationRunner(pipeline=pipeline)
    results = await runner.run_all()
    runner.print_report(results)

    # Export results
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    runner.export_results(results, output_dir / "evaluation_results.json")

    # Exit with error if any tests failed
    failed = sum(1 for r in results if not r.passed)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
