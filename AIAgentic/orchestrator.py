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

    def run(self, objective, app_context, max_iterations=50, test_mode="web"):
        """Execute an agentic test session.

        Args:
            objective: The test objective from the user.
            app_context: Application context description.
            max_iterations: Maximum agent iterations.
            test_mode: Testing mode (web, api, mobile).

        Returns:
            The final report/result as a string.
        """
        # Build the prompt for the supervisor
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
3. Return a brief completion status (1-2 sentences). Do NOT generate a standalone report.
   The official report is provided by Robot Framework's built-in log/report.
"""
        logger.info(
            "Starting agentic test: mode=%s, max_iter=%d",
            test_mode,
            max_iterations,
        )
        result = self.supervisor(prompt)
        return str(result)

    def run_exploration(self, app_context, focus_areas=None, max_iterations=100):
        """Execute an exploratory agentic test session.

        Args:
            app_context: Application context description.
            focus_areas: Comma-separated areas to focus on.
            max_iterations: Maximum agent iterations.

        Returns:
            The exploration report as a string.
        """
        available = ", ".join(self.available_libraries.keys())
        focus = focus_areas or "general exploration"

        prompt = f"""
Test Objective: EXPLORATORY TESTING

Application Context: {app_context}

Focus Areas: {focus}
Available Libraries: {available}
Max Iterations: {max_iterations}

Instructions:
1. Plan an exploratory test approach covering the focus areas.
2. Systematically explore the application:
   - Navigate through main flows
   - Try unexpected inputs and actions
   - Test error handling and edge cases
   - Look for UI/UX issues
3. Document findings with evidence in your actions.
4. Return a brief completion status (1-2 sentences). Do NOT generate a standalone report.
"""
        logger.info("Starting exploratory test: focus=%s", focus)
        result = self.supervisor(prompt)
        return str(result)

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
