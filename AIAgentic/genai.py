# Apache License 2.0
#
# Copyright (c) 2026 Róbert Malovec
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
GenAI provider adapter for Strands Agents SDK.

Creates Strands-compatible model instances based on platform configuration.
Reuses the proven pattern from robotframework-aivision but maps to Strands
model providers instead of direct OpenAI client usage.
"""

import os
import logging

from .platforms import Platforms

logger = logging.getLogger(__name__)


class GenAIProvider:
    """Creates Strands model instances based on platform configuration.

    This module adapts the platform configuration into Strands-compatible
    model instances, supporting OpenAI, Ollama, Gemini, Anthropic, and Bedrock.
    """

    def __init__(self, platform, model=None, api_key=None, base_url=None):
        """Initialize the GenAI provider.

        Args:
            platform: Platforms enum value specifying the AI provider.
            model: Model ID override (uses platform default if None).
            api_key: API key override (resolves from env if None).
            base_url: Base URL override (uses platform default if None).
        """
        self.platform = platform
        self.model_id = model or platform.value["default_model"]
        self.api_key = api_key or self._resolve_api_key(platform)
        self.base_url = base_url or platform.value["default_base_url"]

        logger.info(
            "GenAIProvider initialized: platform=%s, model=%s",
            platform.name,
            self.model_id,
        )

    def create_model(self):
        """Create and return a Strands-compatible model instance.

        Returns:
            A Strands Model instance configured for the selected platform.

        Raises:
            ValueError: If the provider is unsupported.
            ImportError: If required provider package is not installed.
        """
        provider = self.platform.value["strands_provider"]

        if provider == "openai":
            return self._create_openai_model()
        elif provider == "ollama":
            return self._create_ollama_model()
        elif provider == "anthropic":
            return self._create_anthropic_model()
        elif provider == "bedrock":
            return self._create_bedrock_model()
        else:
            raise ValueError(f"Unsupported Strands provider: {provider}")

    def _create_openai_model(self):
        """Create an OpenAI-compatible Strands model.

        Used for OpenAI, Gemini (via OpenAI-compatible endpoint), and Manual platforms.
        """
        try:
            from strands.models.openai import OpenAIModel
        except ImportError:
            raise ImportError(
                "strands-agents with OpenAI support is required. "
                "Install with: pip install 'strands-agents[openai]'"
            )

        client_args = {}
        if self.api_key:
            client_args["api_key"] = self.api_key
        if self.base_url:
            client_args["base_url"] = self.base_url

        logger.debug(
            "Creating OpenAIModel: model_id=%s, base_url=%s",
            self.model_id,
            self.base_url,
        )

        return OpenAIModel(
            model_id=self.model_id,
            client_args=client_args if client_args else None,
        )

    def _create_ollama_model(self):
        """Create an Ollama Strands model for local model inference."""
        try:
            from strands.models.ollama import OllamaModel
        except ImportError:
            raise ImportError(
                "strands-agents with Ollama support is required. "
                "Install with: pip install 'strands-agents[ollama]'"
            )

        host = self.base_url or "http://localhost:11434"

        logger.debug(
            "Creating OllamaModel: model_id=%s, host=%s",
            self.model_id,
            host,
        )

        return OllamaModel(
            host=host,
            model_id=self.model_id,
        )

    def _create_anthropic_model(self):
        """Create an Anthropic Strands model."""
        try:
            from strands.models.anthropic import AnthropicModel
        except ImportError:
            raise ImportError(
                "strands-agents with Anthropic support is required. "
                "Install with: pip install 'strands-agents[anthropic]'"
            )

        client_args = {}
        if self.api_key:
            client_args["api_key"] = self.api_key

        logger.debug(
            "Creating AnthropicModel: model_id=%s",
            self.model_id,
        )

        return AnthropicModel(
            model_id=self.model_id,
            max_tokens=4096,
            client_args=client_args if client_args else None,
        )

    def _create_bedrock_model(self):
        """Create a Bedrock Strands model (uses AWS credentials)."""
        try:
            from strands.models.bedrock import BedrockModel
        except ImportError:
            raise ImportError(
                "strands-agents with Bedrock support is required. "
                "Install with: pip install 'strands-agents[bedrock]'"
            )

        logger.debug(
            "Creating BedrockModel: model_id=%s",
            self.model_id,
        )

        return BedrockModel(model_id=self.model_id)

    @staticmethod
    def _resolve_api_key(platform):
        """Resolve API key from environment variables.

        Args:
            platform: Platforms enum value.

        Returns:
            API key string or None if not configured.
        """
        env_var = platform.value.get("api_key_env")
        if env_var:
            key = os.environ.get(env_var)
            if key:
                logger.debug("API key resolved from environment variable: %s", env_var)
            return key
        return None
