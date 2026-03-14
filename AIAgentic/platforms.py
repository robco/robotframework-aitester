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
AI platform configuration enum for robotframework-aiagentic.

Defines supported AI platforms with their Strands provider mappings,
default models, API key environment variables, and base URLs.
"""

from enum import Enum


class Platforms(Enum):
    """Supported AI platforms for agentic test execution.

    Each platform value is a dict with:
    - strands_provider: The Strands Agents SDK provider name.
    - default_model: Default model ID for this platform.
    - api_key_env: Environment variable name for the API key.
    - default_base_url: Base URL override (None = use provider default).
    """

    OpenAI = {
        "strands_provider": "openai",
        "default_model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "default_base_url": None,
    }

    Ollama = {
        "strands_provider": "ollama",
        "default_model": "llama3.3",
        "api_key_env": None,
        "default_base_url": "http://localhost:11434",
    }

    Gemini = {
        "strands_provider": "openai",
        "default_model": "gemini-2.0-flash",
        "api_key_env": "GEMINI_API_KEY",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    }

    Anthropic = {
        "strands_provider": "anthropic",
        "default_model": "claude-3-7-sonnet-20250219",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_base_url": None,
    }

    Bedrock = {
        "strands_provider": "bedrock",
        "default_model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        "api_key_env": None,
        "default_base_url": None,
    }

    Manual = {
        "strands_provider": "openai",
        "default_model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "default_base_url": None,
    }
