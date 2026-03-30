"""Tests for subagents and SKILL.md configurations in deepagents.

This module tests:
1. YAML frontmatter parsing from subagent .md files
2. SKILL.md metadata and content validation
3. Subagent configuration (tools, skills, system prompts)
4. Business logic validation in skills and subagents
"""

from pathlib import Path

import pytest
import yaml

from template_agent.src.core.agent import _parse_agent_frontmatter

# Path to agent config directory
CONFIG_DIR = Path(__file__).parent.parent / "template_agent" / "agent_config"
AGENTS_DIR = CONFIG_DIR / "agents"
SKILLS_DIR = CONFIG_DIR / "skills"


class TestSubagentParsing:
    """Test subagent .md file parsing and structure."""

    def test_bmi_analyst_frontmatter(self):
        """Test bmi-analyst subagent frontmatter parsing."""
        agent_file = AGENTS_DIR / "bmi-analyst.md"
        assert agent_file.exists(), f"Missing: {agent_file}"

        config = _parse_agent_frontmatter(agent_file)

        assert config["name"] == "bmi-analyst"
        assert "description" in config
        assert len(config["description"]) > 0
        assert "body" in config
        assert len(config["body"]) > 0

    def test_email_dispatcher_frontmatter(self):
        """Test email-dispatcher subagent frontmatter parsing."""
        agent_file = AGENTS_DIR / "email-dispatcher.md"
        assert agent_file.exists(), f"Missing: {agent_file}"

        config = _parse_agent_frontmatter(agent_file)

        assert config["name"] == "email-dispatcher"
        assert "description" in config
        assert "body" in config

    def test_bmi_analyst_has_required_tools(self):
        """Test bmi-analyst declares required tools."""
        agent_file = AGENTS_DIR / "bmi-analyst.md"
        config = _parse_agent_frontmatter(agent_file)

        assert "tools" in config
        assert "calculate_bmi" in config["tools"]
        assert "search_web" in config["tools"]

    def test_email_dispatcher_has_send_email_tool(self):
        """Test email-dispatcher declares send_email tool."""
        agent_file = AGENTS_DIR / "email-dispatcher.md"
        config = _parse_agent_frontmatter(agent_file)

        assert "tools" in config
        assert "send_email" in config["tools"]

    def test_bmi_analyst_has_bmi_report_skill(self):
        """Test bmi-analyst references bmi-report skill."""
        agent_file = AGENTS_DIR / "bmi-analyst.md"
        config = _parse_agent_frontmatter(agent_file)

        assert "skills" in config
        assert "bmi-report" in config["skills"]

    def test_email_dispatcher_has_email_formatter_skill(self):
        """Test email-dispatcher references email-formatter skill."""
        agent_file = AGENTS_DIR / "email-dispatcher.md"
        config = _parse_agent_frontmatter(agent_file)

        assert "skills" in config
        assert "email-formatter" in config["skills"]


class TestSkillMetadata:
    """Test SKILL.md frontmatter and metadata."""

    def test_client_intake_skill_metadata(self):
        """Test client-intake skill has valid metadata."""
        skill_file = SKILLS_DIR / "client-intake" / "SKILL.md"
        assert skill_file.exists(), f"Missing: {skill_file}"

        content = skill_file.read_text()
        assert content.startswith("---"), "Missing YAML frontmatter"

        parts = content.split("---", 2)
        assert len(parts) >= 3, "Invalid frontmatter format"

        metadata = yaml.safe_load(parts[1])
        assert metadata["name"] == "client-intake"
        assert "description" in metadata
        assert len(metadata["description"]) > 0

    def test_bmi_report_skill_metadata(self):
        """Test bmi-report skill has valid metadata."""
        skill_file = SKILLS_DIR / "bmi-report" / "SKILL.md"
        assert skill_file.exists(), f"Missing: {skill_file}"

        content = skill_file.read_text()
        parts = content.split("---", 2)
        metadata = yaml.safe_load(parts[1])

        assert metadata["name"] == "bmi-report"
        assert "description" in metadata

    def test_email_formatter_skill_metadata(self):
        """Test email-formatter skill has valid metadata."""
        skill_file = SKILLS_DIR / "email-formatter" / "SKILL.md"
        assert skill_file.exists(), f"Missing: {skill_file}"

        content = skill_file.read_text()
        parts = content.split("---", 2)
        metadata = yaml.safe_load(parts[1])

        assert metadata["name"] == "email-formatter"
        assert "description" in metadata


class TestSkillContentValidation:
    """Test business logic and content requirements in skills."""

    def test_bmi_report_has_bmi_categories(self):
        """Test bmi-report skill defines BMI categories."""
        skill_file = SKILLS_DIR / "bmi-report" / "SKILL.md"
        content = skill_file.read_text()

        # Check BMI category definitions
        assert "Underweight" in content
        assert "Normal" in content
        assert "Overweight" in content
        assert "Obese" in content
        assert "18.5" in content
        assert "24.9" in content

    def test_bmi_report_has_disclaimer_requirement(self):
        """Test bmi-report skill mandates disclaimer."""
        skill_file = SKILLS_DIR / "bmi-report" / "SKILL.md"
        content = skill_file.read_text()

        assert "disclaimer" in content.lower()
        assert "medical advice" in content.lower()
        assert "healthcare professional" in content.lower()

    def test_client_intake_has_unit_conversion_formulas(self):
        """Test client-intake skill provides unit conversion formulas."""
        skill_file = SKILLS_DIR / "client-intake" / "SKILL.md"
        content = skill_file.read_text()

        # Check for conversion formulas
        assert "inches" in content.lower() or "in" in content
        assert "feet" in content.lower() or "ft" in content
        assert "pounds" in content.lower() or "lbs" in content
        assert "Rational" in content  # sympy import

    def test_email_formatter_has_inline_css_requirement(self):
        """Test email-formatter skill specifies inline CSS."""
        skill_file = SKILLS_DIR / "email-formatter" / "SKILL.md"
        content = skill_file.read_text()

        assert "inline CSS" in content or "inline css" in content.lower()
        assert "Gmail" in content
        assert "600px" in content  # max width requirement

    def test_email_formatter_has_html_template(self):
        """Test email-formatter skill provides HTML template."""
        skill_file = SKILLS_DIR / "email-formatter" / "SKILL.md"
        content = skill_file.read_text()

        assert "```html" in content
        assert "<div" in content
        assert "Red Hat" in content
        assert "#CC0000" in content  # Red Hat brand color


class TestSubagentBusinessLogic:
    """Test business logic requirements in subagent prompts."""

    def test_bmi_analyst_requires_metric_units(self):
        """Test bmi-analyst expects cm and kg."""
        agent_file = AGENTS_DIR / "bmi-analyst.md"
        config = _parse_agent_frontmatter(agent_file)
        body = config["body"]

        assert "cm" in body.lower()
        assert "kg" in body.lower()
        assert "metric" in body.lower()

    def test_bmi_analyst_workflow_steps(self):
        """Test bmi-analyst defines complete workflow."""
        agent_file = AGENTS_DIR / "bmi-analyst.md"
        config = _parse_agent_frontmatter(agent_file)
        body = config["body"]

        # Check workflow steps
        assert "calculate_bmi" in body
        assert "search_web" in body

    def test_bmi_analyst_prohibits_inline_computation(self):
        """Test bmi-analyst forbids manual calculations."""
        agent_file = AGENTS_DIR / "bmi-analyst.md"
        config = _parse_agent_frontmatter(agent_file)
        body = config["body"]

        # Should explicitly say to use tools, not compute manually
        assert (
            "do not compute" in body.lower()
            or "never compute" in body.lower()
            or "not compute" in body.lower()
        )

    def test_email_dispatcher_sends_immediately(self):
        """Test email-dispatcher configured to send without confirmation."""
        agent_file = AGENTS_DIR / "email-dispatcher.md"
        config = _parse_agent_frontmatter(agent_file)
        body = config["body"]

        # Should say to send immediately
        assert (
            "immediately" in body.lower()
            or "do not ask" in body.lower()
            or "no confirmation" in body.lower()
        )

    def test_email_dispatcher_gmail_compatibility(self):
        """Test email-dispatcher emphasizes Gmail compatibility."""
        agent_file = AGENTS_DIR / "email-dispatcher.md"
        config = _parse_agent_frontmatter(agent_file)
        body = config["body"]

        assert "Gmail" in body or "gmail" in body.lower()
        assert "inline" in body.lower()


class TestSkillsDirectoryStructure:
    """Test skills directory structure and file organization."""

    def test_all_skills_have_skill_md(self):
        """Test every skill directory has a SKILL.md file."""
        for skill_dir in SKILLS_DIR.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                assert skill_file.exists(), f"Missing SKILL.md in {skill_dir.name}"

    def test_skill_names_match_directory_names(self):
        """Test skill metadata name matches directory name."""
        for skill_dir in SKILLS_DIR.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    content = skill_file.read_text()
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            metadata = yaml.safe_load(parts[1])
                            assert metadata["name"] == skill_dir.name, (
                                f"Skill name mismatch in {skill_dir.name}"
                            )


class TestSubagentCoordination:
    """Test subagent coordination and delegation rules."""

    def test_bmi_analyst_out_of_scope(self):
        """Test bmi-analyst defines out-of-scope items."""
        agent_file = AGENTS_DIR / "bmi-analyst.md"
        config = _parse_agent_frontmatter(agent_file)
        body = config["body"]

        assert "out of scope" in body.lower()

    def test_email_dispatcher_out_of_scope(self):
        """Test email-dispatcher defines out-of-scope items."""
        agent_file = AGENTS_DIR / "email-dispatcher.md"
        config = _parse_agent_frontmatter(agent_file)
        body = config["body"]

        assert "out of scope" in body.lower()


class TestSystemPromptIntegration:
    """Test system prompt references to skills and subagents."""

    def test_system_prompt_references_subagents(self):
        """Test system-prompt.md references subagents."""
        system_prompt_file = CONFIG_DIR / "system-prompt.md"
        content = system_prompt_file.read_text()

        assert "bmi-analyst" in content
        assert "email-dispatcher" in content

    def test_system_prompt_references_client_intake_skill(self):
        """Test system-prompt.md references client-intake skill."""
        system_prompt_file = CONFIG_DIR / "system-prompt.md"
        content = system_prompt_file.read_text()

        assert "client-intake" in content

    def test_system_prompt_defines_routing_rules(self):
        """Test system-prompt.md has routing logic."""
        system_prompt_file = CONFIG_DIR / "system-prompt.md"
        content = system_prompt_file.read_text()

        assert "routing" in content.lower() or "delegate" in content.lower()
        assert "imperial" in content.lower()  # unit conversion routing
