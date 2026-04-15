"""Unit tests for orchestrator fast-path behavior."""

from AITester.orchestrator import AgentOrchestrator


class FakeAgent:
    instances = []

    def __init__(
        self,
        system_prompt=None,
        model=None,
        tools=None,
        conversation_manager=None,
        callback_handler=None,
        hooks=None,
        name=None,
        description=None,
    ):
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools or []
        self.hooks = hooks or []
        self.name = name
        self.description = description
        self.calls = []
        FakeAgent.instances.append(self)

    def __call__(self, prompt):
        self.calls.append(prompt)
        if self.name == "Test Planner":
            return '{"scenarios":[{"scenario_id":"1","name":"Plan"}]}'
        return f"{self.name} executed"


def build_orchestrator(monkeypatch, available_libraries):
    FakeAgent.instances = []
    monkeypatch.setattr("AITester.orchestrator.Agent", FakeAgent)
    monkeypatch.setattr(
        "AITester.orchestrator.SlidingWindowConversationManager",
        lambda window_size: {"window_size": window_size},
    )
    return AgentOrchestrator(model=object(), available_libraries=available_libraries)


def get_agent(name: str):
    for agent in FakeAgent.instances:
        if agent.name == name:
            return agent
    raise AssertionError(f"Agent '{name}' was not created")


def test_run_uses_direct_executor_path(monkeypatch):
    orchestrator = build_orchestrator(monkeypatch, {"SeleniumLibrary": object()})

    result = orchestrator.run(
        objective="Test login flow",
        app_context="Web app",
        test_mode="web",
        max_iterations=5,
    )

    planner = get_agent("Test Planner")
    executor = get_agent("Web Executor")
    supervisor = get_agent("Supervisor")

    assert result == "Web Executor executed"
    assert len(planner.calls) == 1
    assert len(executor.calls) == 1
    assert len(supervisor.calls) == 0
    assert "Execution Plan:" in executor.calls[0]
    assert '"scenario_id":"1"' in executor.calls[0]


def test_run_skips_planner_for_user_defined_steps(monkeypatch):
    orchestrator = build_orchestrator(monkeypatch, {"SeleniumLibrary": object()})

    result = orchestrator.run(
        objective="USER-DEFINED TEST STEPS (MAIN FLOW, HIGHEST PRIORITY):\n1. Open login",
        app_context="Web app",
        test_mode="web",
        max_iterations=5,
        high_level_steps=["Open login", "Verify dashboard"],
    )

    planner = get_agent("Test Planner")
    executor = get_agent("Web Executor")
    supervisor = get_agent("Supervisor")

    assert result == "Web Executor executed"
    assert len(planner.calls) == 0
    assert len(executor.calls) == 1
    assert len(supervisor.calls) == 0
    assert "User-defined Main Flow:" in executor.calls[0]
    assert "1. Open login" in executor.calls[0]
    assert "selenium_handle_common_blockers" in executor.calls[0]
    assert "get_frame_inventory" in executor.calls[0]
    assert "Treat user-provided steps as ordered intent checkpoints" in executor.calls[0]
    assert "Prefer semantic snapshot-driven tools over raw locator guessing" in executor.calls[0]
    assert "get_execution_observations" in executor.calls[0]
    assert "Do not pause for human input" in executor.calls[0]
    assert "get_rf_variable" in executor.calls[0]
    assert "reach pages by clicking visible links" in executor.calls[0]
    assert "unless the user explicitly instructs a concrete URL to open" in executor.calls[0]
    assert "Do not close or restart the browser as a recovery step" in executor.calls[0]
    assert "switch into the most likely iframe with `selenium_select_frame`" in executor.calls[0]
    assert "selenium_click_snapshot_element" in executor.calls[0]


def test_run_extracts_numbered_steps_from_objective(monkeypatch):
    orchestrator = build_orchestrator(monkeypatch, {"SeleniumLibrary": object()})

    result = orchestrator.run(
        objective="""
        USER-DEFINED TEST STEPS (MAIN FLOW, HIGHEST PRIORITY)
        1. Open login page
        2. Sign in with valid credentials
        """,
        app_context="Web app",
        test_mode="web",
        max_iterations=5,
    )

    planner = get_agent("Test Planner")
    executor = get_agent("Web Executor")

    assert result == "Web Executor executed"
    assert len(planner.calls) == 0
    assert "1. Open login page" in executor.calls[0]
    assert "2. Sign in with valid credentials" in executor.calls[0]


def test_run_skips_planner_for_mobile_user_defined_steps(monkeypatch):
    orchestrator = build_orchestrator(monkeypatch, {"AppiumLibrary": object()})

    result = orchestrator.run(
        objective="USER-DEFINED TEST STEPS (MAIN FLOW, HIGHEST PRIORITY):\n1. Complete onboarding",
        app_context="Android app",
        test_mode="mobile",
        max_iterations=5,
        high_level_steps=["Complete onboarding", "Verify dashboard"],
    )

    planner = get_agent("Test Planner")
    executor = get_agent("Mobile Executor")

    assert result == "Mobile Executor executed"
    assert len(planner.calls) == 0
    assert "User-defined Main Flow:" in executor.calls[0]
    assert "appium_get_view_snapshot" in executor.calls[0]
    assert "appium_get_interactive_elements" in executor.calls[0]
    assert "appium_get_loading_state" in executor.calls[0]
    assert "appium_handle_common_interruptions" in executor.calls[0]
    assert "appium_get_context_inventory" in executor.calls[0]
    assert "appium_switch_context" in executor.calls[0]
    assert "appium_click_snapshot_element" in executor.calls[0]
    assert "get_execution_observations" in executor.calls[0]
    assert "Do not pause for human input" in executor.calls[0]
    assert "get_rf_variable" in executor.calls[0]
    assert "navigate with visible taps, swipes, scrolls" in executor.calls[0]
    assert "Do not close, reset, or relaunch the application" in executor.calls[0]


def test_run_exploration_uses_direct_executor(monkeypatch):
    orchestrator = build_orchestrator(monkeypatch, {"SeleniumLibrary": object()})

    result = orchestrator.run_exploration(
        app_context="Web app",
        focus_areas="checkout",
        max_iterations=7,
        test_mode="web",
    )

    planner = get_agent("Test Planner")
    executor = get_agent("Web Executor")
    supervisor = get_agent("Supervisor")

    assert result == "Web Executor executed"
    assert len(planner.calls) == 0
    assert len(executor.calls) == 1
    assert len(supervisor.calls) == 0
    assert "Focus Areas: checkout" in executor.calls[0]
    assert "get_page_snapshot" in executor.calls[0]
    assert "get_frame_inventory" in executor.calls[0]
    assert "get_execution_observations" in executor.calls[0]


def test_build_agents_attaches_session_tracking_hooks(monkeypatch):
    build_orchestrator(monkeypatch, {"SeleniumLibrary": object()})

    planner = get_agent("Test Planner")
    executor = get_agent("Web Executor")
    supervisor = get_agent("Supervisor")

    assert len(planner.hooks) == 1
    assert len(executor.hooks) == 1
    assert len(supervisor.hooks) == 1
