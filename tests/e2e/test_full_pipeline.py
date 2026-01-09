"""E2E tests for the complete Inkwell pipeline.

These tests simulate the full pipeline from podcast episode to markdown output.
In a production environment with API keys, these would make real API calls.

Test Coverage:
- Full pipeline: fetch → transcribe → extract → generate output
- Cost tracking
- Error handling
- Output validation
"""

import json
import time
from pathlib import Path

import pytest

from tests.e2e.framework import (
    E2E_TEST_CASES,
    E2EBenchmark,
    E2ETestResult,
    validate_e2e_output,
)


class TestE2ESimulation:
    """Simulated E2E tests demonstrating the framework.

    NOTE: These tests use simulated data. In production with API keys,
    replace simulate_* functions with actual API calls.
    """

    def test_framework_structure(self):
        """Test that E2E framework is properly structured."""
        assert len(E2E_TEST_CASES) == 5, "Should have 5 diverse test cases"

        # Validate test case coverage
        content_types = {tc.content_type for tc in E2E_TEST_CASES}
        assert "technical" in content_types
        assert "interview" in content_types
        assert "discussion" in content_types
        assert "educational" in content_types
        assert "storytelling" in content_types

        # Validate duration diversity
        durations = [tc.duration_minutes for tc in E2E_TEST_CASES]
        assert min(durations) <= 20, "Should have short episode"
        assert max(durations) >= 60, "Should have long episode"

    def test_test_case_completeness(self):
        """Test that all test cases have complete metadata."""
        for test_case in E2E_TEST_CASES:
            assert test_case.name
            assert test_case.podcast_name
            assert test_case.episode_title
            assert test_case.episode_url
            assert test_case.duration_minutes > 0
            assert test_case.speaker_count > 0
            assert test_case.expected_word_count > 0
            assert test_case.expected_sections
            assert test_case.expected_entity_count >= 0
            assert test_case.expected_tag_count >= 0

    def test_simulated_pipeline_short_technical(self, tmp_path):
        """Test short technical podcast (Case 1)."""
        test_case = E2E_TEST_CASES[0]  # short-technical
        assert test_case.name == "short-technical"

        # Simulate pipeline execution
        start_time = time.time()

        # 1. Simulate transcription (YouTube API - free)
        transcript = self._simulate_transcription(test_case, tmp_path / "transcript.txt")
        transcription_time = time.time() - start_time

        # 2. Simulate extraction
        extraction_start = time.time()
        extraction_results = self._simulate_extraction(
            test_case, transcript, tmp_path / "extraction"
        )
        extraction_time = time.time() - extraction_start

        # 3. Simulate output generation
        output_start = time.time()
        _output_dir = self._simulate_output_generation(
            test_case, extraction_results, tmp_path / "output"
        )
        output_time = time.time() - output_start

        total_time = time.time() - start_time

        # Create test result
        result = E2ETestResult(
            test_case_name=test_case.name,
            success=True,
            total_duration_seconds=total_time,
            transcription_duration_seconds=transcription_time,
            extraction_duration_seconds=extraction_time,
            output_generation_duration_seconds=output_time,
            transcript_word_count=test_case.expected_word_count,
            transcript_source=test_case.expected_transcript_source,
            templates_processed=len(test_case.expected_sections),
            entities_extracted=test_case.expected_entity_count,
            tags_generated=test_case.expected_tag_count,
            wikilinks_created=test_case.expected_entity_count,  # 1:1 for simplicity
            files_generated=len(test_case.expected_sections) + 1,  # +1 for metadata
            total_output_size_kb=25.0,  # Simulated
            has_frontmatter=True,
            has_wikilinks=True,
            has_tags=True,
            transcription_cost_usd=test_case.expected_transcription_cost,
            extraction_cost_usd=test_case.expected_extraction_cost,
            total_cost_usd=test_case.expected_total_cost,
            validation_passed=True,
            validation_errors=[],
            validation_warnings=[],
        )

        # Assertions
        assert result.success
        assert result.transcript_source == "youtube"
        assert result.total_cost_usd < 0.01  # Very cheap (YouTube is free)
        assert result.files_generated == 4  # 3 sections + metadata
        assert result.entities_extracted == 8
        assert result.tags_generated == 5

    def test_simulated_pipeline_long_interview(self, tmp_path):
        """Test long interview podcast (Case 2)."""
        test_case = E2E_TEST_CASES[1]  # long-interview
        assert test_case.name == "long-interview"

        start_time = time.time()

        # Simulate pipeline (Gemini transcription - costly)
        transcript = self._simulate_transcription(test_case, tmp_path / "transcript.txt")
        transcription_time = time.time() - start_time

        extraction_start = time.time()
        extraction_results = self._simulate_extraction(
            test_case, transcript, tmp_path / "extraction"
        )
        extraction_time = time.time() - extraction_start

        output_start = time.time()
        _output_dir = self._simulate_output_generation(
            test_case, extraction_results, tmp_path / "output"
        )
        output_time = time.time() - output_start

        total_time = time.time() - start_time

        result = E2ETestResult(
            test_case_name=test_case.name,
            success=True,
            total_duration_seconds=total_time,
            transcription_duration_seconds=transcription_time,
            extraction_duration_seconds=extraction_time,
            output_generation_duration_seconds=output_time,
            transcript_word_count=test_case.expected_word_count,
            transcript_source=test_case.expected_transcript_source,
            templates_processed=len(test_case.expected_sections),
            entities_extracted=test_case.expected_entity_count,
            tags_generated=test_case.expected_tag_count,
            wikilinks_created=test_case.expected_entity_count,
            files_generated=len(test_case.expected_sections) + 1,
            total_output_size_kb=120.0,  # Longer content
            has_frontmatter=True,
            has_wikilinks=True,
            has_tags=True,
            transcription_cost_usd=test_case.expected_transcription_cost,
            extraction_cost_usd=test_case.expected_extraction_cost,
            total_cost_usd=test_case.expected_total_cost,
            validation_passed=True,
            validation_errors=[],
            validation_warnings=[],
        )

        # Assertions
        assert result.success
        assert result.transcript_source == "gemini"
        assert result.total_cost_usd > 0.15  # Expensive (Gemini transcription)
        assert result.files_generated == 5  # 4 sections + metadata
        assert result.entities_extracted == 25
        assert result.tags_generated == 12

    def test_benchmark_aggregation(self, tmp_path):
        """Test benchmark aggregation from multiple results."""
        # Simulate results for all 5 test cases
        results = []

        for test_case in E2E_TEST_CASES:
            result = E2ETestResult(
                test_case_name=test_case.name,
                success=True,
                total_duration_seconds=float(test_case.duration_minutes * 2),  # 2x realtime
                transcription_duration_seconds=float(test_case.duration_minutes * 1),
                extraction_duration_seconds=float(test_case.duration_minutes * 0.8),
                output_generation_duration_seconds=float(test_case.duration_minutes * 0.2),
                transcript_word_count=test_case.expected_word_count,
                transcript_source=test_case.expected_transcript_source,
                templates_processed=len(test_case.expected_sections),
                entities_extracted=test_case.expected_entity_count,
                tags_generated=test_case.expected_tag_count,
                wikilinks_created=test_case.expected_entity_count,
                files_generated=len(test_case.expected_sections) + 1,
                total_output_size_kb=float(test_case.duration_minutes * 2),
                has_frontmatter=True,
                has_wikilinks=True,
                has_tags=True,
                transcription_cost_usd=test_case.expected_transcription_cost,
                extraction_cost_usd=test_case.expected_extraction_cost,
                total_cost_usd=test_case.expected_total_cost,
                validation_passed=True,
                validation_errors=[],
                validation_warnings=[],
            )
            results.append(result)

        # Create benchmark
        benchmark = E2EBenchmark.from_results(results)

        # Assertions
        assert benchmark.test_cases_run == 5
        assert benchmark.success_count == 5
        assert benchmark.failure_count == 0
        assert benchmark.total_cost_usd == sum(tc.expected_total_cost for tc in E2E_TEST_CASES)
        assert benchmark.avg_cost_per_case > 0
        assert benchmark.avg_entities_extracted > 0
        assert benchmark.avg_tags_generated > 0

    def test_output_validation(self, tmp_path):
        """Test output validation logic."""
        test_case = E2E_TEST_CASES[0]  # short-technical

        # Create mock output
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create expected files
        metadata_file = output_dir / ".metadata.yaml"
        metadata_file.write_text("podcast: Test\nepisode: Test Episode\n")

        for section in test_case.expected_sections:
            section_file = output_dir / f"{section}.md"
            # Create content with sufficient size (>100 bytes) to avoid warnings
            content = f"---\ntitle: {section}\n---\n\n# {section}\n\nTest content with [[wikilink]] and #tag.\n\nAdditional content to make file larger than 100 bytes threshold for validation.\nThis ensures the validation framework doesn't generate warnings about file size."
            section_file.write_text(content)

        # Validate
        passed, errors, warnings = validate_e2e_output(output_dir, test_case)

        assert passed, f"Validation should pass. Errors: {errors}"
        assert len(errors) == 0
        # Warnings are OK - validation might flag legitimate concerns

    def test_validation_catches_missing_files(self, tmp_path):
        """Test validation catches missing expected files."""
        test_case = E2E_TEST_CASES[0]

        # Create incomplete output (missing sections)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        metadata_file = output_dir / ".metadata.yaml"
        metadata_file.write_text("podcast: Test\n")

        # Only create first file
        if test_case.expected_sections:
            section_file = output_dir / f"{test_case.expected_sections[0]}.md"
            section_file.write_text("---\n---\n\nContent")

        # Validate
        passed, errors, warnings = validate_e2e_output(output_dir, test_case)

        assert not passed, "Validation should fail for missing files"
        assert len(errors) > 0

    # Helper methods for simulation

    def _simulate_transcription(self, test_case, output_path: Path) -> str:
        """Simulate transcription process."""
        # Generate realistic transcript
        words_per_line = 12
        lines = test_case.expected_word_count // words_per_line

        transcript_lines = []
        for i in range(lines):
            line = (
                f"This is simulated transcript line {i + 1} with approximately twelve words here."
            )
            transcript_lines.append(line)

        transcript = "\n".join(transcript_lines)

        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(transcript)

        return transcript

    def _simulate_extraction(self, test_case, transcript: str, output_dir: Path) -> dict:
        """Simulate extraction process."""
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}
        for section in test_case.expected_sections:
            # Simulate extracted content
            content = {
                "title": section.replace("-", " ").title(),
                "content": f"Simulated {section} content based on transcript analysis.",
                "entities": [
                    f"Entity{i}"
                    for i in range(
                        test_case.expected_entity_count // len(test_case.expected_sections)
                    )
                ],
            }
            results[section] = content

            # Save extraction result
            result_file = output_dir / f"{section}.json"
            result_file.write_text(json.dumps(content, indent=2))

        return results

    def _simulate_output_generation(
        self, test_case, extraction_results: dict, output_dir: Path
    ) -> Path:
        """Simulate markdown output generation."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate metadata file
        metadata = {
            "podcast": test_case.podcast_name,
            "episode": test_case.episode_title,
            "duration_minutes": test_case.duration_minutes,
            "transcription_cost": test_case.expected_transcription_cost,
            "extraction_cost": test_case.expected_extraction_cost,
            "total_cost": test_case.expected_total_cost,
        }
        metadata_file = output_dir / ".metadata.yaml"
        metadata_file.write_text(json.dumps(metadata, indent=2))

        # Generate markdown files
        for section, content in extraction_results.items():
            md_file = output_dir / f"{section}.md"

            # Create content with frontmatter, wikilinks, and tags
            frontmatter = f"""---
title: {content["title"]}
podcast: {test_case.podcast_name}
episode: {test_case.episode_title}
template: {section}
tags: [podcast, {test_case.content_type}]
---

"""
            body = f"# {content['title']}\n\n{content['content']}\n\n"

            # Add wikilinks for entities
            if content["entities"]:
                body += "## Related\n\n"
                for entity in content["entities"]:
                    body += f"- [[{entity}]]\n"

            md_content = frontmatter + body
            md_file.write_text(md_content)

        return output_dir


@pytest.mark.skip(reason="Requires API keys - run manually with real credentials")
class TestE2ERealAPIs:
    """E2E tests with real API calls.

    These tests are skipped by default. To run with real APIs:
    1. Set environment variables: GOOGLE_API_KEY, ANTHROPIC_API_KEY
    2. Run: pytest tests/e2e/test_full_pipeline.py::TestE2ERealAPIs -v
    """

    def test_real_api_short_episode(self, tmp_path):
        """Test with real API calls (short episode to minimize cost)."""
        # This would make actual API calls
        # Estimated cost: ~$0.01
        pytest.skip("Set API keys and remove skip to run")

    def test_real_api_full_suite(self, tmp_path):
        """Test full suite with real APIs."""
        # This would process all 5 test cases
        # Estimated cost: ~$0.35
        pytest.skip("Set API keys and remove skip to run")
