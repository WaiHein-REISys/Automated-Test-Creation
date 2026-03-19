"""Tests for story completeness validation (feature-generatable check)."""

import pytest

from atc.core.models import check_story_completeness


class TestStoryCompleteness:
    """Stories with user + goal + benefit are feature-generatable."""

    @pytest.mark.parametrize(
        ("description", "acceptance_criteria"),
        [
            # Classic "As a … I want … so that …"
            (
                "As a grants applicant, I want to submit my SF424 form online "
                "so that I can apply for federal funding.",
                "",
            ),
            # User in description, goal + benefit in AC
            (
                "The administrator needs to manage user accounts.",
                "User should be able to create new accounts. "
                "This is to ensure compliance with access policies.",
            ),
            # HTML-wrapped content from ADO rich-text editor
            (
                "<div>As a reviewer</div><p>I want to approve submitted applications</p>",
                "<div>so that the grants process moves forward</div>",
            ),
            # Mixed phrasing
            (
                "As an admin user of the grants portal",
                "I need to configure roles. In order to improve security.",
            ),
            # Benefit phrased with "to allow"
            (
                "As a customer",
                "I want to search grants by keyword to allow faster discovery.",
            ),
        ],
        ids=[
            "classic-format",
            "split-across-fields",
            "html-wrapped",
            "mixed-phrasing",
            "to-allow-benefit",
        ],
    )
    def test_generatable(self, description: str, acceptance_criteria: str) -> None:
        result = check_story_completeness(description, acceptance_criteria)
        assert result.is_generatable, f"Expected generatable, but missing: {result.missing}"

    @pytest.mark.parametrize(
        ("description", "acceptance_criteria", "expected_missing"),
        [
            # Completely empty
            ("", "", ["user/actor", "goal/action", "benefit/purpose"]),
            # Has user but no goal or benefit
            ("As a user", "", ["goal/action", "benefit/purpose"]),
            # Has goal but no user or benefit
            ("", "I want to submit the form", ["user/actor", "benefit/purpose"]),
            # Has benefit but no user or goal
            ("", "so that compliance is met", ["user/actor", "goal/action"]),
            # Vague text with no structure
            (
                "Fix the bug in the login page",
                "It should work correctly",
                ["user/actor", "goal/action", "benefit/purpose"],
            ),
            # Has user + goal but no benefit
            (
                "As a reviewer",
                "I want to view application details",
                ["benefit/purpose"],
            ),
        ],
        ids=[
            "empty",
            "user-only",
            "goal-only",
            "benefit-only",
            "vague-text",
            "missing-benefit",
        ],
    )
    def test_not_generatable(
        self,
        description: str,
        acceptance_criteria: str,
        expected_missing: list[str],
    ) -> None:
        result = check_story_completeness(description, acceptance_criteria)
        assert not result.is_generatable
        assert result.missing == expected_missing

    def test_attachments_do_not_substitute_for_text(self) -> None:
        """Attachments alone don't make a story generatable."""
        result = check_story_completeness("", "", has_attachments=True)
        assert not result.is_generatable

    def test_missing_property(self) -> None:
        """The missing property lists exactly what's absent."""
        result = check_story_completeness("As a user", "I want to edit records", has_attachments=False)
        assert result.has_user is True
        assert result.has_goal is True
        assert result.has_benefit is False
        assert result.missing == ["benefit/purpose"]
