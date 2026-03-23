"""Unit tests for orchestrator fast-path behavior."""

from AIAgentic.orchestrator import AgentOrchestrator


class FakeAgent:
    instances = []

    def __init__(
        self,
        system_prompt=None,
        model=None,
        tools=None,
        conversation_manager=None,
        callback_handler=None,
        name=None,
        description=None,
    ):
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools or []
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
    monkeypatch.setattr("AIAgentic.orchestrator.Agent", FakeAgent)
    monkeypatch.setattr(
        "AIAgentic.orchestrator.SlidingWindowConversationManager",
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
