# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for genai module."""

import os
import pytest
from unittest.mock import patch, MagicMock
from AIAgentic.platforms import Platforms
from AIAgentic.genai import GenAIProvider


class TestGenAIProvider:
    """Tests for GenAIProvider."""

    def test_init_with_defaults(self):
        provider = GenAIProvider(Platforms.OpenAI, api_key="test-key")
        assert provider.model_id == "gpt-4o"
        assert provider.api_key == "test-key"
        assert "openai.com" in provider.base_url

    def test_init_with_overrides(self):
        provider = GenAIProvider(
            Platforms.OpenAI,
            model="gpt-4o-mini",
            api_key="custom-key",
            base_url="https://custom.api.com/v1",
        )
        assert provider.model_id == "gpt-4o-mini"
        assert provider.api_key == "custom-key"
        assert provider.base_url == "https://custom.api.com/v1"

    def test_ollama_no_api_key(self):
        provider = GenAIProvider(Platforms.Ollama)
        assert provider.api_key is None
        assert provider.model_id == "llama3.3"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "env-key-123"})
    def test_resolve_api_key_from_env(self):
        provider = GenAIProvider(Platforms.OpenAI)
        assert provider.api_key == "env-key-123"

    def test_resolve_api_key_none(self):
        # Ollama doesn't need API key
        key = GenAIProvider._resolve_api_key(Platforms.Ollama)
        assert key is None

    def test_bedrock_no_base_url(self):
        provider = GenAIProvider(Platforms.Bedrock)
        assert provider.base_url is None

    def test_anthropic_provider(self):
        provider = GenAIProvider(Platforms.Anthropic, api_key="ant-key")
        assert provider.platform == Platforms.Anthropic
        assert "claude" in provider.model_id

    def test_gemini_uses_openai_provider(self):
        provider = GenAIProvider(Platforms.Gemini, api_key="gem-key")
        assert provider.platform.value["strands_provider"] == "openai"

    def test_manual_platform(self):
        provider = GenAIProvider(
            Platforms.Manual,
            model="custom-model",
            api_key="manual-key",
            base_url="https://my-llm.com/v1",
        )
        assert provider.model_id == "custom-model"
        assert provider.base_url == "https://my-llm.com/v1"
