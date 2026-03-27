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
AI platform configuration for robotframework-aitester.

Defines supported AI platforms and their connection parameters,
including default models, API key environment variables, and
Strands Agents SDK provider identifiers.
"""

from enum import Enum


class Platforms(Enum):
    """Supported AI platforms with their configuration.

    Each platform value is a dict with:
    - default_model: Default model ID for this platform.
    - api_key_env: Environment variable name for the API key (None if not needed).
    - default_base_url: Default base URL (None for cloud defaults).
    - strands_provider: Strands Agents SDK provider identifier.
    """

    OpenAI = {
        "default_model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "default_base_url": "https://api.openai.com/v1",
        "strands_provider": "openai",
        "supports_tool_use": True,
    }

    Ollama = {
        "default_model": "llama3.3",
        "api_key_env": None,
        "default_base_url": "http://localhost:11434/v1",
        "strands_provider": "ollama",
        "supports_tool_use": True,
    }

    Gemini = {
        "default_model": "gemini-2.0-flash",
        "api_key_env": "GEMINI_API_KEY",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "strands_provider": "openai",
        "supports_tool_use": True,
    }

    Anthropic = {
        "default_model": "claude-sonnet-4-5",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_base_url": None,
        "strands_provider": "anthropic",
        "supports_tool_use": True,
    }

    Bedrock = {
        "default_model": "us.anthropic.claude-sonnet-4-5-20251101-v1:0",
        "api_key_env": None,
        "default_base_url": None,
        "strands_provider": "bedrock",
        "supports_tool_use": True,
    }

    Manual = {
        "default_model": None,
        "api_key_env": None,
        "default_base_url": None,
        "strands_provider": "openai",
        "supports_tool_use": True,
    }
