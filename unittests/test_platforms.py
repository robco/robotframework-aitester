# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for platforms module."""

import pytest
from AIAgentic.platforms import Platforms


class TestPlatforms:
    """Tests for the Platforms enum."""

    def test_all_platforms_defined(self):
        """Verify all expected platforms are defined."""
        expected = {"Ollama", "OpenAI", "Gemini", "Anthropic", "Bedrock", "Manual"}
        actual = {p.name for p in Platforms}
        assert actual == expected

    def test_platform_has_required_keys(self):
        """Every platform must have the required configuration keys."""
        required_keys = {
            "default_model",
            "default_base_url",
            "api_key_env",
            "strands_provider",
            "supports_tool_use",
        }
        for platform in Platforms:
            actual_keys = set(platform.value.keys())
            assert required_keys.issubset(actual_keys), (
                f"{platform.name} missing keys: {required_keys - actual_keys}"
            )

    def test_openai_defaults(self):
        """OpenAI platform should have correct defaults."""
        config = Platforms.OpenAI.value
        assert config["default_model"] == "gpt-4o"
        assert "openai.com" in config["default_base_url"]
        assert config["api_key_env"] == "OPENAI_API_KEY"
        assert config["strands_provider"] == "openai"

    def test_ollama_defaults(self):
        """Ollama platform should have correct defaults."""
        config = Platforms.Ollama.value
        assert config["default_model"] == "llama3.3"
        assert "localhost" in config["default_base_url"]
        assert config["api_key_env"] is None
        assert config["strands_provider"] == "ollama"

    def test_anthropic_defaults(self):
        """Anthropic platform should have correct defaults."""
        config = Platforms.Anthropic.value
        assert "claude" in config["default_model"]
        assert config["api_key_env"] == "ANTHROPIC_API_KEY"
        assert config["strands_provider"] == "anthropic"

    def test_bedrock_defaults(self):
        """Bedrock platform should have correct defaults."""
        config = Platforms.Bedrock.value
        assert config["default_base_url"] is None
        assert config["api_key_env"] is None
        assert config["strands_provider"] == "bedrock"

    def test_gemini_defaults(self):
        """Gemini platform should have correct defaults."""
        config = Platforms.Gemini.value
        assert "gemini" in config["default_model"]
        assert config["api_key_env"] == "GEMINI_API_KEY"
        assert config["strands_provider"] == "openai"

    def test_manual_platform(self):
        """Manual platform should have None defaults."""
        config = Platforms.Manual.value
        assert config["default_model"] is None
        assert config["default_base_url"] is None

    def test_platform_lookup_by_name(self):
        """Platforms should be accessible by name."""
        assert Platforms["OpenAI"] == Platforms.OpenAI
        assert Platforms["Ollama"] == Platforms.Ollama

    def test_all_support_tool_use(self):
        """All platforms should support tool use for agentic testing."""
        for platform in Platforms:
            assert platform.value["supports_tool_use"] is True, (
                f"{platform.name} does not support tool use"
            )
