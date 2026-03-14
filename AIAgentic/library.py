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
Main Robot Framework library class for robotframework-aiagentic.

This is the public interface of the library, exposing Robot Framework keywords
such as Run Agentic Test, Run Agentic Exploration, and Run Agentic API Test
that testers invoke from .robot files.
"""

import logging
import os

from robot.api.deco import keyword
from robot.api import logger as rf_logger
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .platforms import Platforms
from .genai import GenAIProvider
from .orchestrator import AgentOrchestrator
from .executor import (
    TestSession,
    SessionStatus,
    SafetyGuard,
    create_session,
    record_step,
    StepStatus,
)
from .reporter import TestReporter

logger = logging.getLogger(__name__)


class AIAgentic:
    """AI Agentic Testing Library for Robot Framework.

    Enables fully autonomous, AI-driven test automation by combining
    the Strands Agents SDK with native RF library integration. Users
    supply a test objective and the AI agent autonomously designs,
    executes, and reports on test scenarios.

    Supported test modes:
    - web: Selenium-based browser testing (requires SeleniumLibrary)
    - api: REST API testing (requires RequestsLibrary)
    - mobile: Appium-based mobile testing (requires AppiumLibrary)

    Supported AI platforms: OpenAI, Ollama, Gemini, Anthropic, Bedrock

    Examples:
    | Library | AIAgentic | platform=OpenAI | api_key=%{OPENAI_API_KEY} | model=gpt-4o |
    | Library | AIAgentic | platform=Ollama | model=llama3.3 |
    """

    ROBOT_LIBRARY_SCOPE = "GLOBAL"
    ROBOT_LIBRARY_VERSION = "0.1.0"

    def __init__(
        self,
        platform: str = "OpenAI",
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        max_iterations: int = 50,
        test_mode: str = "web",
        headless: bool = False,
        screenshot_on_action: bool = True,
        verbose: bool = False,
        report_formats: str = "text,json,html",
        timeout_seconds: float = 600,
        max_cost_usd: float = None,
    ):
        """Initialize the AIAgentic library.

        Args:
            platform: AI platform name (OpenAI, Ollama, Gemini, Anthropic, Bedrock, Manual).
            model: Model ID override. Uses platform default if not specified.
            api_key: API key override. Resolves from environment if not specified.
            base_url: Base URL override. Uses platform default if not specified.
            max_iterations: Maximum agent iterations per test run. Default 50.
            test_mode: Default testing mode (web, api, mobile). Default web.
            headless: Run browser in headless mode. Default False.
            screenshot_on_action: Capture screenshots after actions. Default True.
            verbose: Enable verbose agent logging. Default False.
            report_formats: Comma-separated report formats (text, json, html, junit).
            timeout_seconds: Session timeout in seconds. Default 600 (10 min).
            max_cost_usd: Maximum session cost in USD. None for unlimited.
        """
        # Resolve platform enum
        try:
            self.platform = Platforms[platform]
        except KeyError:
            valid = ", ".join(p.name for p in Platforms)
            raise ValueError(
                f"Unknown platform '{platform}'. Valid options: {valid}"
            )

        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_iterations = int(max_iterations)
        self.test_mode = test_mode
        self.headless = headless
        self.screenshot_on_action = screenshot_on_action
        self.verbose = verbose
        self.report_formats = [f.strip() for f in report_formats.split(",")]
        self.timeout_seconds = float(timeout_seconds)
        self.max_cost_usd = float(max_cost_usd) if max_cost_usd else None

        # Lazy-initialized components
        self._orchestrator = None
        self._genai_provider = None
        self._reporter = None
        self._safety_guard = None

        logger.info(
            "AIAgentic initialized: platform=%s, model=%s, test_mode=%s",
            platform,
            model or self.platform.value["default_model"],
            test_mode,
        )

    def _get_available_libraries(self):
        """Discover which RF libraries are loaded.

        Returns:
            Dict mapping library name to library instance.
        """
        libs = {}
        for name in ["SeleniumLibrary", "AppiumLibrary", "RequestsLibrary"]:
            try:
                libs[name] = BuiltIn().get_library_instance(name)
            except (RuntimeError, RobotNotRunningError):
                pass
        return libs

    def _ensure_orchestrator(self):
        """Lazy initialization of the agent orchestrator."""
        if self._orchestrator is None:
            # Create GenAI provider
            self._genai_provider = GenAIProvider(
                platform=self.platform,
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
            )
            model = self._genai_provider.create_model()

            # Discover available libraries
            available_libs = self._get_available_libraries()
            if not available_libs:
                logger.warning(
                    "No testing libraries (SeleniumLibrary, RequestsLibrary, AppiumLibrary) "
                    "detected. Agent will have limited tool capabilities."
                )

            # Build orchestrator
            self._orchestrator = AgentOrchestrator(
                model=model,
                available_libraries=available_libs,
                verbose=self.verbose,
            )

            # Initialize reporter
            self._reporter = TestReporter()

            # Initialize safety guard
            self._safety_guard = SafetyGuard(
                max_iterations=self.max_iterations,
                timeout_seconds=self.timeout_seconds,
                max_cost_usd=self.max_cost_usd,
            )

            logger.info(
                "Orchestrator initialized with libraries: %s",
                list(available_libs.keys()),
            )

    @keyword
    def run_agentic_test(
        self,
        test_objective: str,
        app_context: str = "",
        max_iterations: int = None,
        test_mode: str = None,
    ) -> str:
        """Runs an autonomous AI agentic test based on the given objective.

        The AI agent will autonomously design test scenarios, execute test
        steps, capture evidence, and generate a structured test report.

        Args:
            test_objective: Natural language description of what to test
                (e.g., "Test the login functionality including valid and invalid credentials").
            app_context: Description of the application under test
                (e.g., "E-commerce web application with email/password login").
            max_iterations: Override max agent iterations for this run.
            test_mode: Override test mode for this run (web, api, mobile).

        Returns:
            Structured test report as a string.

        Examples:
        | ${report}= | Run Agentic Test |
        | ... | test_objective=Test login with valid and invalid credentials |
        | ... | app_context=Web application with email/password login |
        | ... | max_iterations=50 |
        """
        self._ensure_orchestrator()

        mode = test_mode or self.test_mode
        iters = int(max_iterations) if max_iterations else self.max_iterations

        rf_logger.info(
            f"Starting agentic test: mode={mode}, max_iterations={iters}",
        )
        rf_logger.info(f"Objective: {test_objective}")
        rf_logger.info(f"App context: {app_context}")

        try:
            result = self._orchestrator.run(
                objective=test_objective,
                app_context=app_context,
                max_iterations=iters,
                test_mode=mode,
            )
            rf_logger.info("Agentic test completed successfully")
            return result
        except Exception as e:
            error_msg = f"Agentic test failed: {type(e).__name__}: {e}"
            rf_logger.error(error_msg)
            raise AssertionError(error_msg)

    @keyword
    def run_agentic_exploration(
        self,
        app_context: str,
        focus_areas: str = None,
        max_iterations: int = None,
    ) -> str:
        """Runs an autonomous AI exploratory test session.

        The AI agent freely explores the application, discovering
        features, testing edge cases, and reporting findings without
        a predefined test plan.

        Args:
            app_context: Description of the application under test.
            focus_areas: Comma-separated areas to focus exploration on
                (e.g., "navigation, search, product filtering, cart operations").
            max_iterations: Override max agent iterations for this run.

        Returns:
            Exploration report as a string.

        Examples:
        | ${report}= | Run Agentic Exploration |
        | ... | app_context=E-commerce platform with catalog and checkout |
        | ... | focus_areas=navigation, search, product filtering |
        | ... | max_iterations=100 |
        """
        self._ensure_orchestrator()

        iters = int(max_iterations) if max_iterations else self.max_iterations

        rf_logger.info(f"Starting exploratory test: focus={focus_areas}")
        rf_logger.info(f"App context: {app_context}")

        try:
            result = self._orchestrator.run_exploration(
                app_context=app_context,
                focus_areas=focus_areas,
                max_iterations=iters,
            )
            rf_logger.info("Exploratory test completed successfully")
            return result
        except Exception as e:
            error_msg = f"Exploratory test failed: {type(e).__name__}: {e}"
            rf_logger.error(error_msg)
            raise AssertionError(error_msg)

    @keyword
    def run_agentic_api_test(
        self,
        test_objective: str,
        base_url: str = None,
        api_spec_url: str = None,
        max_iterations: int = None,
    ) -> str:
        """Runs an autonomous AI agentic API test.

        Specialized keyword for REST API testing. The AI agent will
        test API endpoints based on the objective, optionally using
        an OpenAPI specification for endpoint discovery.

        Args:
            test_objective: Natural language description of what API functionality to test.
            base_url: API base URL (used as context for the agent).
            api_spec_url: Optional URL to OpenAPI/Swagger specification.
            max_iterations: Override max agent iterations for this run.

        Returns:
            API test report as a string.

        Examples:
        | ${report}= | Run Agentic API Test |
        | ... | test_objective=Test user management CRUD operations |
        | ... | base_url=https://api.example.com |
        | ... | api_spec_url=https://api.example.com/openapi.json |
        """
        self._ensure_orchestrator()

        iters = int(max_iterations) if max_iterations else self.max_iterations

        # Build app context from API details
        app_context = f"REST API"
        if base_url:
            app_context += f" at {base_url}"
        if api_spec_url:
            app_context += f" (OpenAPI spec: {api_spec_url})"

        rf_logger.info(f"Starting agentic API test: {app_context}")

        try:
            result = self._orchestrator.run(
                objective=test_objective,
                app_context=app_context,
                max_iterations=iters,
                test_mode="api",
            )
            rf_logger.info("Agentic API test completed successfully")
            return result
        except Exception as e:
            error_msg = f"Agentic API test failed: {type(e).__name__}: {e}"
            rf_logger.error(error_msg)
            raise AssertionError(error_msg)

    @keyword
    def run_agentic_mobile_test(
        self,
        test_objective: str,
        app_context: str = "",
        max_iterations: int = None,
    ) -> str:
        """Runs an autonomous AI agentic mobile app test.

        Specialized keyword for mobile application testing using Appium.

        Args:
            test_objective: Natural language description of what to test.
            app_context: Description of the mobile app under test.
            max_iterations: Override max agent iterations for this run.

        Returns:
            Mobile test report as a string.

        Examples:
        | ${report}= | Run Agentic Mobile Test |
        | ... | test_objective=Test onboarding flow and main navigation |
        | ... | app_context=Android banking application |
        """
        self._ensure_orchestrator()

        iters = int(max_iterations) if max_iterations else self.max_iterations

        rf_logger.info(f"Starting agentic mobile test")

        try:
            result = self._orchestrator.run(
                objective=test_objective,
                app_context=app_context,
                max_iterations=iters,
                test_mode="mobile",
            )
            rf_logger.info("Agentic mobile test completed successfully")
            return result
        except Exception as e:
            error_msg = f"Agentic mobile test failed: {type(e).__name__}: {e}"
            rf_logger.error(error_msg)
            raise AssertionError(error_msg)

    @keyword
    def get_agentic_platform_info(self) -> str:
        """Returns information about the configured AI platform.

        Returns:
            String with platform name, model, and configuration details.

        Examples:
        | ${info}= | Get Agentic Platform Info |
        | Log | ${info} |
        """
        model_name = self.model or self.platform.value["default_model"]
        base = self.base_url or self.platform.value["default_base_url"]
        return (
            f"Platform: {self.platform.name}\n"
            f"Model: {model_name}\n"
            f"Base URL: {base}\n"
            f"Test Mode: {self.test_mode}\n"
            f"Max Iterations: {self.max_iterations}\n"
            f"Verbose: {self.verbose}"
        )
