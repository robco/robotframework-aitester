# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Strands @tool decorated functions that bridge Robot Framework libraries.

Each tool module wraps a specific RF library's keywords as Strands tools,
enabling AI agents to interact with applications through the same
battle-tested RF libraries that manual tests use.
"""

from .web_tools import WEB_TOOLS
from .api_tools import API_TOOLS
from .mobile_tools import MOBILE_TOOLS
from .common_tools import COMMON_TOOLS
from .browser_analysis_tools import BROWSER_ANALYSIS_TOOLS
from .mobile_analysis_tools import MOBILE_ANALYSIS_TOOLS

__all__ = [
    "WEB_TOOLS",
    "API_TOOLS",
    "MOBILE_TOOLS",
    "COMMON_TOOLS",
    "BROWSER_ANALYSIS_TOOLS",
    "MOBILE_ANALYSIS_TOOLS",
]
