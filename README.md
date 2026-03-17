[![Python Package CI](https://github.com/robco/robotframework-aiagentic/actions/workflows/python-package.yml/badge.svg)](https://github.com/robco/robotframework-aiagentic/actions/workflows/python-package.yml)

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/robco)
# Fully Autonomous AI Agentic Testing for Robot Framework

[![Robot Framework](https://img.shields.io/badge/Robot%20Framework-7.0%2B-brightgreen)](https://robotframework.org)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

`robotframework-aiagentic` is a Robot Framework library that enables fully autonomous, AI-driven test automation. By combining the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) supervisor-agent orchestration with multi-provider GenAI model access and native RF library integration, this module allows testers to specify **what to test** rather than **how to test it**.

Supply a test area, scenario, or high-level test idea for a target application — web, mobile, or API — and the AI agent autonomously designs test plans, executes test steps, captures evidence, and logs results into Robot Framework's built-in `log.html` / `report.html`.

## Feature Highlights

- Supervisor agent orchestrates four specialist agents (Planner, Web, API, Mobile) with dedicated system prompts.
- Instrumented tool bridge records step status, duration, assertion details, and screenshot references, surfacing them in RF logs via the `Agentic Step` keyword.
- Browser analysis tools extract interactive elements, page structure, form fields, links, and console errors to guide exploration.
- Utility tools provide assertions, JSON parsing, timing, RF variable access, and optional AIVision screenshot analysis.
- RF built-in reporting with embedded screenshots and high-level step grouping when user-defined steps are provided.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  Layer 1: RF Keyword Layer                                     │
│  .robot files → AIAgentic keywords (Run Agentic Test, etc.)    │
├────────────────────────────────────────────────────────────────┤
│  Layer 2: Agent Orchestration Layer                            │
│  Strands Supervisor → Planner / Web / API / Mobile             │
├────────────────────────────────────────────────────────────────┤
│  Layer 3: Tool Bridge Layer                                    │
│  Instrumented tools (Selenium/Requests/Appium + DOM analysis)  │
├────────────────────────────────────────────────────────────────┤
│  Layer 4: AI Provider Layer                                    │
│  Multi-provider GenAI (OpenAI, Ollama, Gemini, Anthropic, etc) │
├────────────────────────────────────────────────────────────────┤
│  Layer 5: Reporting & Observability Layer                      │
│  Test results, step logs, screenshots (RF log.html/report.html) │
└────────────────────────────────────────────────────────────────┘
```

### Agent Hierarchy

```
                ┌───────────────────┐
                │  SUPERVISOR       │
                │  (QA Test Lead)   │
                └────────┬──────────┘
                         │
     ┌─────────┬────────┬─────────┬─────────┐
┌────┴───┐┌───┴────┐┌──┴────┐┌──┴─────┐
│ Planner ││  Web   ││  API  ││ Mobile │
│  Agent  ││Executor││Execut.││Executor│
└────────┘└────────┘└───────┘└────────┘
```

## Installation

```bash
# Base installation
pip install robotframework-aiagentic

# With web testing support
pip install robotframework-aiagentic[web]

# With all testing modes and OpenAI
pip install robotframework-aiagentic[all,openai]

# With Bedrock support
pip install robotframework-aiagentic[all,bedrock]

# With Anthropic support
pip install robotframework-aiagentic[all,anthropic]

# With Ollama (local models)
pip install robotframework-aiagentic[all,ollama]

# Development
pip install robotframework-aiagentic[all,openai,dev]
```

## Quick Start

### Web Testing

```robot
*** Settings ***
Library    SeleniumLibrary
Library    AIAgentic    platform=OpenAI    api_key=%{OPENAI_API_KEY}    model=gpt-4o

*** Test Cases ***
Agentic Login Flow Test
    [Documentation]    AI agent autonomously tests the login functionality
    Open Browser    https://myapp.example.com    chrome
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. Open the login page
    ...    2. Attempt login with valid credentials and verify success
    ...    3. Attempt login with invalid credentials and verify error message
    ${status}=    Run Agentic Test
    ...    test_objective=Test the login functionality including valid credentials,
    ...        invalid credentials, empty fields, and password recovery flow
    ...    app_context=E-commerce web application with email/password login
    ...    test_steps=${TEST_STEPS}
    ...    max_iterations=50
    Log    ${status}
    [Teardown]    Close All Browsers

Agentic Exploratory Testing
    [Documentation]    AI agent freely explores and tests the application
    Open Browser    https://myapp.example.com    chrome
    ${status}=    Run Agentic Exploration
    ...    app_context=E-commerce platform with product catalog, shopping cart and checkout
    ...    focus_areas=navigation, search, product filtering, cart operations
    ...    max_iterations=100
    Log    ${status}
    [Teardown]    Close All Browsers
```

The browser opened by `Open Browser` is reused by the agent. If a session is
already active, AIAgentic will reuse it and refuse to open a new one.

### API Testing

```robot
*** Settings ***
Library    RequestsLibrary
Library    AIAgentic    platform=Ollama    model=llama3.3

*** Test Cases ***
Agentic REST API Test
    Create Session    api    https://api.example.com
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. Create a user via POST /users
    ...    2. Fetch the user via GET /users/{id}
    ...    3. Update the user via PUT /users/{id}
    ...    4. Delete the user via DELETE /users/{id}
    ${status}=    Run Agentic API Test
    ...    test_objective=Test the user management API endpoints including
    ...        CRUD operations, authentication, error handling, and edge cases
    ...    base_url=https://api.example.com
    ...    api_spec_url=https://api.example.com/openapi.json
    ...    test_steps=${TEST_STEPS}
    ...    max_iterations=30
    Log    ${status}
```

### Mobile Testing

```robot
*** Settings ***
Library    AppiumLibrary
Library    AIAgentic    platform=Gemini    api_key=%{GEMINI_API_KEY}

*** Test Cases ***
Agentic Mobile App Test
    Open Application    http://localhost:4723/wd/hub
    ...    platformName=Android    app=com.example.app
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. Complete the onboarding flow
    ...    2. Navigate to the main dashboard
    ...    3. Open settings and verify key options
    ${status}=    Run Agentic Mobile Test
    ...    test_objective=Test the onboarding flow, main navigation and settings screen
    ...    app_context=Android banking application
    ...    test_steps=${TEST_STEPS}
    ...    max_iterations=40
    Log    ${status}
    [Teardown]    Close Application
```

## Supported AI Platforms

| Platform  | Default Model                     | Provider            | Notes                         |
|-----------|-----------------------------------|---------------------|-------------------------------|
| OpenAI    | gpt-4o                            | OpenAI API          | Requires `OPENAI_API_KEY`     |
| Ollama    | llama3.3                          | Local Ollama        | Free, local inference         |
| Gemini    | gemini-2.0-flash                  | Google AI           | Requires `GEMINI_API_KEY`     |
| Anthropic | claude-sonnet-4-5                 | Anthropic API       | Requires `ANTHROPIC_API_KEY`  |
| Bedrock   | us.anthropic.claude-sonnet-4-5-20251101-v1:0 | AWS Bedrock | Uses AWS credentials       |
| Manual    | User-specified                    | OpenAI-compatible   | Custom endpoint               |

## Configuration

### Environment Variables

| Variable           | Description                                  |
|--------------------|----------------------------------------------|
| `OPENAI_API_KEY`   | OpenAI API key                               |
| `GEMINI_API_KEY`   | Google Gemini API key                        |
| `ANTHROPIC_API_KEY`| Anthropic API key                            |
| `AWS_*`            | AWS credentials for Bedrock                  |

### Robot Framework Variables

```robot
*** Settings ***
Library    AIAgentic
...    platform=${AI_PLATFORM}
...    model=${AI_MODEL}
...    api_key=${AI_API_KEY}
...    max_iterations=${AI_MAX_ITERATIONS}

# Execute with:
# robot --variable AI_PLATFORM:OpenAI --variable AI_MODEL:gpt-4o tests/
```

### Constructor Parameters

| Parameter             | Default    | Description                                   |
|-----------------------|------------|-----------------------------------------------|
| `platform`            | OpenAI     | AI platform (OpenAI, Ollama, Gemini, etc.)    |
| `model`               | (varies)   | Model ID override                             |
| `api_key`             | (env var)  | API key override                              |
| `base_url`            | (varies)   | API base URL override                         |
| `max_iterations`      | 50         | Maximum agent iterations                      |
| `test_mode`           | web        | Default test mode (web, api, mobile)          |
| `headless`            | False      | Request headless browser mode (driver-dependent) |
| `screenshot_on_action`| True       | Capture screenshots after actions when supported |
| `verbose`             | False      | Enable verbose agent logging                  |
| `selenium_library`    | SeleniumLibrary | SeleniumLibrary name/alias for existing sessions |
| `requests_library`    | RequestsLibrary | RequestsLibrary name/alias for existing sessions |
| `appium_library`      | AppiumLibrary | AppiumLibrary name/alias for existing sessions |
| `timeout_seconds`     | 600        | Session timeout in seconds                    |
| `max_cost_usd`        | None       | Maximum session cost in USD                   |

If you import SeleniumLibrary/RequestsLibrary/AppiumLibrary with an alias,
pass the corresponding `*_library` parameter so agentic tools attach to the
already-opened session.

### Session Reuse (No New Browsers/Apps)

If an active Selenium or Appium session is detected, AIAgentic **reuses it**
and **refuses to open a new session on a different device**. This prevents
cases like opening a desktop browser when an Android Appium browser is already
running. Make sure the existing session is open before calling `Run Agentic*`,
and set `selenium_library` / `appium_library` if you imported those libraries
with aliases.

```robot
*** Settings ***
Library    SeleniumLibrary    WITH NAME    Web
Library    AIAgentic    platform=OpenAI    selenium_library=Web

*** Test Cases ***
Reuse Existing Web Session
    Open Browser    https://example.com    chrome
    ${status}=    Run Agentic Test
    ...    test_objective=Smoke test the landing page
    Log    ${status}
```

## Keywords

| Keyword                     | Description                                       |
|----------------------------|----------------------------------------------------|
| `Run Agentic Test`         | Execute an autonomous test from a test objective (supports `test_steps`) |
| `Run Agentic Exploration`  | Run exploratory testing with focus areas           |
| `Run Agentic API Test`     | Execute autonomous REST API testing (supports `test_steps`) |
| `Run Agentic Mobile Test`  | Execute autonomous mobile app testing (supports `test_steps`) |
| `Get Agentic Platform Info`| Return configured platform information             |
| `Agentic Step`             | Step-level logging keyword used by the agent tools |
| `Agentic High Level Step`  | High-level step marker used for RF log grouping    |

## Safety & Guardrails

- **Iteration limit**: Hard stop after `max_iterations` to prevent infinite loops
- **Timeout**: Session-level timeout enforcement (default 10 minutes)
- **Cost tracking**: Approximate token cost accumulation with optional limit
- **Error recovery**: Retry budget per action (max 3 retries)
- **Action whitelist/blacklist**: Configurable tool restrictions

## Integration with robotframework-aivision

When [robotframework-aivision](https://github.com/robco/robotframework-aivision) is loaded alongside AIAgentic, additional visual analysis capabilities become available to the agents, including screenshot analysis, visual regression detection, and accessibility validation.

## Reporting

robotframework-aiagentic uses only Robot Framework v7.4+ built-in reporting
(`log.html` / `report.html`). No custom standalone reports are generated.
`Run Agentic*` keywords return a short completion status; review details in the RF log.

When you provide user-defined numbered test steps (via the `test_steps` argument
or `${TEST_STEPS}` variable), those steps are treated as the main flow and
agentic actions are grouped under them in
the RF log with embedded screenshots for readability.

Additional reporting features:

- Step-level logging via `Agentic Step` with status, duration, assertions, and embedded screenshots
- High-level grouping when user-defined steps are supplied
- Screenshots are copied into `${OUTPUT_DIR}` for reliable linking in `log.html`

## Development Roadmap

| Phase | Target    | Focus                                                |
|-------|-----------|------------------------------------------------------|
| 1     | Q2 2026   | Core architecture + Web + API testing                |
| 2     | Q3 2026   | Enhanced reporting + Gemini/Anthropic support        |
| 3     | Q4 2026   | Mobile testing + Bedrock support                     |
| 4     | Q1 2027   | Multi-agent swarm, self-healing locators             |
| 5     | Q2 2027   | Cloud & tool integration (BrowserStack, Xray)        |
| 6     | Q3 2027   | MCP/A2A protocol support, plugin architecture        |

## Author

**Róbert Malovec**
- Email: robert@malovec.sk
- GitHub: [@robco](https://github.com/robco)
- Organization: T-Mobile Czech Republic

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
