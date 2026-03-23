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
Agent orchestrator implementing the Strands SDK supervisor-agent pattern.

A single Supervisor Agent acts as a QA Test Lead, delegating work to
specialist agents: Test Planner, Web Executor, API Executor, and
Mobile Executor.
"""

import logging
from strands import Agent, tool
from strands.agent.conversation_manager import SlidingWindowConversationManager

from .prompts import (
    SUPERVISOR_PROMPT,
    TEST_PLANNER_PROMPT,
    WEB_EXECUTOR_PROMPT,
    API_EXECUTOR_PROMPT,
    MOBILE_EXECUTOR_PROMPT,
)
from .tools.web_tools import WEB_TOOLS
from .tools.api_tools import API_TOOLS
from .tools.mobile_tools import MOBILE_TOOLS
from .tools.common_tools import COMMON_TOOLS
from .tools.browser_analysis_tools import BROWSER_ANALYSIS_TOOLS

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Implements the supervisor-agent pattern for agentic test orchestration.

    Agent hierarchy:
        Supervisor (QA Test Lead)
        ├── Test Planner Agent
        ├── Web Executor Agent
        ├── API Executor Agent
        ├── Mobile Executor Agent

    Each specialist agent is wrapped as a Strands @tool and provided to
    the supervisor, enabling it to delegate tasks naturally.
    """

    USER_DEFINED_STEPS_MARKER = "USER-DEFINED TEST STEPS (MAIN FLOW, HIGHEST PRIORITY)"

    def __init__(self, model, available_libraries, verbose=False):
        """Initialize the orchestrator with model and available library config.

        Args:
            model: Strands Model instance (created by GenAIProvider).
            available_libraries: Dict of available RF libraries and their instances.
            verbose: If True, enables detailed agent logging.
        """
        self.model = model
        self.available_libraries = available_libraries
        self.verbose = verbose
        self._callback_handler = None if not verbose else None  # Use default printing in verbose

        # Build agents
        self._build_agents()

    def _build_agents(self):
        """Build all specialist agents and the supervisor."""

        # ---- Test Planner Agent ----
        self.planner = Agent(
            system_prompt=TEST_PLANNER_PROMPT,
            model=self.model,
            tools=COMMON_TOOLS,
            conversation_manager=SlidingWindowConversationManager(
                window_size=10,
            ),
            callback_handler=self._create_callback_handler("Planner"),
            name="Test Planner",
            description="Creates structured test plans from objectives",
        )

        # ---- Web Executor Agent ----
        web_tools = []
        if "SeleniumLibrary" in self.available_libraries:
            web_tools = WEB_TOOLS + BROWSER_ANALYSIS_TOOLS + COMMON_TOOLS
        self.web_executor = Agent(
            system_prompt=WEB_EXECUTOR_PROMPT,
            model=self.model,
            tools=web_tools if web_tools else COMMON_TOOLS,
            conversation_manager=SlidingWindowConversationManager(
                window_size=20,
            ),
            callback_handler=self._create_callback_handler("WebExecutor"),
            name="Web Executor",
            description="Executes web tests using Selenium browser automation",
        )

        # ---- API Executor Agent ----
        api_tools = []
        if "RequestsLibrary" in self.available_libraries:
            api_tools = API_TOOLS + COMMON_TOOLS
        self.api_executor = Agent(
            system_prompt=API_EXECUTOR_PROMPT,
            model=self.model,
            tools=api_tools if api_tools else COMMON_TOOLS,
            conversation_manager=SlidingWindowConversationManager(
                window_size=20,
            ),
            callback_handler=self._create_callback_handler("APIExecutor"),
            name="API Executor",
            description="Executes API tests using HTTP requests",
        )

        # ---- Mobile Executor Agent ----
        mobile_tools = []
        if "AppiumLibrary" in self.available_libraries:
            mobile_tools = MOBILE_TOOLS + COMMON_TOOLS
        self.mobile_executor = Agent(
            system_prompt=MOBILE_EXECUTOR_PROMPT,
            model=self.model,
            tools=mobile_tools if mobile_tools else COMMON_TOOLS,
            conversation_manager=SlidingWindowConversationManager(
                window_size=20,
            ),
            callback_handler=self._create_callback_handler("MobileExecutor"),
            name="Mobile Executor",
            description="Executes mobile app tests using Appium",
        )

        # ---- Create supervisor tools (wrapping specialist agents) ----

        # Capture references for closures
        planner = self.planner
        web_executor = self.web_executor
        api_executor = self.api_executor
        mobile_executor = self.mobile_executor

        @tool
        def plan_tests(objective: str) -> str:
            """Delegates test planning to the Test Planner agent.

            Use this tool to create a structured test plan from a test objective.
            The planner will analyze the objective and produce test scenarios
            with steps, expected results, and priorities.

            Args:
                objective: The test objective and application context to plan for.

            Returns:
                Structured test plan with scenarios and steps.
            """
            logger.info("Supervisor → Planner: %s", objective[:100])
            result = planner(objective)
            return str(result)

        @tool
        def execute_web_test(plan: str) -> str:
            """Delegates web test execution to the Web Executor agent.

            Use this tool to execute web/browser-based test scenarios.
            The executor will use Selenium to interact with the web application.

            Args:
                plan: The test plan or scenario to execute (from plan_tests).

            Returns:
                Execution results with step-by-step details.
            """
            logger.info("Supervisor → Web Executor: %s", plan[:100])
            result = web_executor(plan)
            return str(result)

        @tool
        def execute_api_test(plan: str) -> str:
            """Delegates API test execution to the API Executor agent.

            Use this tool to execute REST API test scenarios.
            The executor will use HTTP requests to test API endpoints.

            Args:
                plan: The test plan or scenario to execute (from plan_tests).

            Returns:
                Execution results with request/response details.
            """
            logger.info("Supervisor → API Executor: %s", plan[:100])
            result = api_executor(plan)
            return str(result)

        @tool
        def execute_mobile_test(plan: str) -> str:
            """Delegates mobile test execution to the Mobile Executor agent.

            Use this tool to execute mobile application test scenarios.
            The executor will use Appium to interact with the mobile app.

            Args:
                plan: The test plan or scenario to execute (from plan_tests).

            Returns:
                Execution results with step-by-step details.
            """
            logger.info("Supervisor → Mobile Executor: %s", plan[:100])
            result = mobile_executor(plan)
            return str(result)

        # ---- Supervisor Agent ----
        supervisor_tools = [plan_tests]

        # Add executor tools based on available libraries
        if "SeleniumLibrary" in self.available_libraries:
            supervisor_tools.append(execute_web_test)
        if "RequestsLibrary" in self.available_libraries:
            supervisor_tools.append(execute_api_test)
        if "AppiumLibrary" in self.available_libraries:
            supervisor_tools.append(execute_mobile_test)

        self.supervisor = Agent(
            system_prompt=SUPERVISOR_PROMPT,
            model=self.model,
            tools=supervisor_tools,
            conversation_manager=SlidingWindowConversationManager(
                window_size=30,
            ),
            callback_handler=self._create_callback_handler("Supervisor"),
            name="Supervisor",
            description="Senior QA Test Lead coordinating specialist agents",
        )

    @staticmethod
    def _has_user_defined_steps(objective, high_level_steps=None) -> bool:
        if high_level_steps:
            return True
        return AgentOrchestrator.USER_DEFINED_STEPS_MARKER in str(objective or "")

    def _get_executor(self, test_mode: str):
        mode = str(test_mode or "").strip().lower()
        if mode == "web":
            return self.web_executor
        if mode == "api":
            return self.api_executor
        if mode == "mobile":
            return self.mobile_executor
        return None

    @staticmethod
    def _format_high_level_steps(high_level_steps) -> str:
        if not high_level_steps:
            return ""
        return "\n".join(
            f"{index}. {step}"
            for index, step in enumerate(high_level_steps, start=1)
        )

    def _build_planner_prompt(
        self,
        objective: str,
        app_context: str,
        test_mode: str,
        max_iterations: int,
    ) -> str:
        return f"""
Test Objective: {objective}

Application Context: {app_context}

Test Mode: {test_mode}
Max Iterations: {max_iterations}

Return only the structured JSON plan requested by your system prompt.
"""

    def _build_executor_prompt(
        self,
        objective: str,
        app_context: str,
        test_mode: str,
        max_iterations: int,
        plan: str = "",
        high_level_steps=None,
        exploratory: bool = False,
        focus_areas: str = "",
    ) -> str:
        formatted_steps = self._format_high_level_steps(high_level_steps)
        instructions = [
            f"Test Objective: {objective}",
            "",
            f"Application Context: {app_context}",
            "",
            f"Test Mode: {test_mode}",
            f"Max Iterations: {max_iterations}",
        ]

        if exploratory:
            instructions.extend(
                [
                    "",
                    f"Focus Areas: {focus_areas or 'general exploration'}",
                    "",
                    "Instructions:",
                    "1. Explore the application directly without a planner or supervisor handoff.",
                    "2. Focus on the listed areas, exercise main flows, and verify outcomes with tools.",
                    "3. Return a brief completion status (1-2 sentences).",
                ]
            )
            return "\n".join(instructions)

        if formatted_steps:
            instructions.extend(
                [
                    "",
                    "User-defined Main Flow:",
                    formatted_steps,
                    "",
                    "Instructions:",
                    "1. Execute the numbered steps in order without requesting a separate plan.",
                    "2. Treat the numbered steps as the primary flow and use direct tool calls to complete them.",
                    "3. Return a brief completion status (1-2 sentences).",
                ]
            )
            return "\n".join(instructions)

        instructions.extend(
            [
                "",
                "Execution Plan:",
                plan,
                "",
                "Instructions:",
                "1. Execute this plan directly in priority order.",
                "2. Use the available tools to complete and verify each scenario.",
                "3. Return a brief completion status (1-2 sentences).",
            ]
        )
        return "\n".join(instructions)

    def _run_via_supervisor(
        self,
        objective,
        app_context,
        max_iterations=50,
        test_mode="web",
    ):
        available = ", ".join(self.available_libraries.keys())

        prompt = f"""
Test Objective: {objective}

Application Context: {app_context}

Test Mode: {test_mode}
Available Libraries: {available}
Max Iterations: {max_iterations}

Instructions:
1. Start by delegating test planning to the Test Planner.
2. Execute the plan using the appropriate executor ({test_mode} mode).
   Execute scenarios in priority order and treat any user-defined steps as the main flow.
3. Return a brief completion status (1-2 sentences). Do NOT generate a standalone report.
   The official report is provided by Robot Framework's built-in log/report.
"""
        logger.info(
            "Starting agentic test via supervisor: mode=%s, max_iter=%d",
            test_mode,
            max_iterations,
        )
        result = self.supervisor(prompt)
        return str(result)

    def _run_direct(
        self,
        objective,
        app_context,
        max_iterations=50,
        test_mode="web",
        high_level_steps=None,
        exploratory: bool = False,
        focus_areas: str = "",
    ):
        executor = self._get_executor(test_mode)
        if executor is None:
            return self._run_via_supervisor(
                objective=objective,
                app_context=app_context,
                max_iterations=max_iterations,
                test_mode=test_mode,
            )

        plan = ""
        if not exploratory and not self._has_user_defined_steps(objective, high_level_steps):
            planner_prompt = self._build_planner_prompt(
                objective=objective,
                app_context=app_context,
                test_mode=test_mode,
                max_iterations=max_iterations,
            )
            logger.info("Direct execution → Planner: %s", objective[:100])
            plan = str(self.planner(planner_prompt))

        executor_prompt = self._build_executor_prompt(
            objective=objective,
            app_context=app_context,
            test_mode=test_mode,
            max_iterations=max_iterations,
            plan=plan,
            high_level_steps=high_level_steps,
            exploratory=exploratory,
            focus_areas=focus_areas,
        )
        logger.info("Direct execution → %s executor", test_mode)
        result = executor(executor_prompt)
        return str(result)

    def run(
        self,
        objective,
        app_context,
        max_iterations=50,
        test_mode="web",
        high_level_steps=None,
    ):
        """Execute an agentic test session.

        Args:
            objective: The test objective from the user.
            app_context: Application context description.
            max_iterations: Maximum agent iterations.
            test_mode: Testing mode (web, api, mobile).

        Returns:
            The final report/result as a string.
        """
        return self._run_direct(
            objective=objective,
            app_context=app_context,
            max_iterations=max_iterations,
            test_mode=test_mode,
            high_level_steps=high_level_steps,
        )

    def run_exploration(
        self,
        app_context,
        focus_areas=None,
        max_iterations=100,
        test_mode="web",
    ):
        """Execute an exploratory agentic test session.

        Args:
            app_context: Application context description.
            focus_areas: Comma-separated areas to focus on.
            max_iterations: Maximum agent iterations.

        Returns:
            The exploration report as a string.
        """
        focus = focus_areas or "general exploration"
        logger.info("Starting exploratory test: mode=%s, focus=%s", test_mode, focus)
        return self._run_direct(
            objective="EXPLORATORY TESTING",
            app_context=app_context,
            max_iterations=max_iterations,
            test_mode=test_mode,
            exploratory=True,
            focus_areas=focus,
        )

    def _create_callback_handler(self, agent_name):
        """Create a callback handler for an agent.

        Args:
            agent_name: Name of the agent for log prefix.

        Returns:
            Callback handler or None for quiet mode.
        """
        if not self.verbose:
            return None

        def handler(**kwargs):
            # Simple verbose logging
            if "data" in kwargs:
                data = kwargs.get("data", "")
                if isinstance(data, str) and data.strip():
                    logger.debug("[%s] %s", agent_name, data[:200])

        return handler
