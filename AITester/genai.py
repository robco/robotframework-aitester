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

import logging
import os

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
            api_key: API key override (resolves from env if None, unless the
                platform defines a fixed API key).
            base_url: Base URL override (uses platform default if None).
        """
        self.platform = platform
        self.model_id = model or platform.value["default_model"]
        self.api_key = self._resolve_effective_api_key(platform, api_key)
        self.base_url = base_url or platform.value["default_base_url"]

        logger.info(
            "GenAIProvider initialized: platform=%s, model=%s",
            platform.name,
            self.model_id,
        )

    @classmethod
    def _resolve_effective_api_key(cls, platform, api_key):
        """Resolve the API key used to create the provider client."""
        fixed_api_key = platform.value.get("fixed_api_key")
        if fixed_api_key is not None:
            if api_key and api_key != fixed_api_key:
                logger.debug(
                    "Ignoring custom api_key for %s and using fixed value.",
                    platform.name,
                )
            return fixed_api_key
        return api_key or cls._resolve_api_key(platform)

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

        class SafeOpenAIModel(OpenAIModel):
            """OpenAI model wrapper that normalizes missing usage fields.

            Some OpenAI-compatible backends return ``None`` for token usage
            fields in streaming metadata. Strands later accumulates these
            counters with ``+=``, which crashes on ``int += None``. Coerce
            missing or invalid values to ``0`` before passing them on.
            """

            @staticmethod
            def _coerce_usage_int(data, *names):
                for name in names:
                    if isinstance(data, dict):
                        value = data.get(name)
                    else:
                        value = getattr(data, name, None)
                    if value is None:
                        continue
                    try:
                        return int(value)
                    except (TypeError, ValueError):
                        return 0
                return 0

            def format_chunk(self, event, **kwargs):
                if event.get("chunk_type") == "metadata":
                    usage_data = event.get("data")
                    input_tokens = self._coerce_usage_int(
                        usage_data, "prompt_tokens", "inputTokens"
                    )
                    output_tokens = self._coerce_usage_int(
                        usage_data, "completion_tokens", "outputTokens"
                    )
                    total_tokens = self._coerce_usage_int(
                        usage_data, "total_tokens", "totalTokens"
                    )
                    if total_tokens == 0 and (input_tokens or output_tokens):
                        total_tokens = input_tokens + output_tokens
                    return {
                        "metadata": {
                            "usage": {
                                "inputTokens": input_tokens,
                                "outputTokens": output_tokens,
                                "totalTokens": total_tokens,
                            },
                            "metrics": {
                                "latencyMs": 0,
                            },
                        },
                    }
                return super().format_chunk(event, **kwargs)

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

        return SafeOpenAIModel(
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
        if host.endswith("/v1"):
            host = host[: -len("/v1")]
        if host.endswith("/v1/"):
            host = host[: -len("/v1/")]

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
