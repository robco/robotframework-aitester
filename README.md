# robotframework-aiagentic

**Fully Autonomous AI Agentic Testing for Robot Framework**

[![Robot Framework](https://img.shields.io/badge/Robot%20Framework-6.0%2B-brightgreen)](https://robotframework.org)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

`robotframework-aiagentic` is a Robot Framework library that enables fully autonomous, AI-driven test automation. By combining the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) supervisor-agent orchestration with multi-provider GenAI model access and native RF library integration, this module allows testers to specify **what to test** rather than **how to test it**.

Supply a test area, scenario, or high-level test idea for a target application — web, mobile, or API — and the AI agent autonomously designs test plans, executes test steps, captures evidence, and generates structured test reports.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  Layer 1: RF Keyword Layer                                     │
│  .robot files → AIAgentic keywords (Run Agentic Test, etc.)    │
├────────────────────────────────────────────────────────────────┤
│  Layer 2: Agent Orchestration Layer                            │
│  Strands Supervisor → Planner / Web / API / Mobile / Reporter  │
├────────────────────────────────────────────────────────────────┤
│  Layer 3: Tool Bridge Layer                                    │
│  @tool decorated functions wrapping SeleniumLibrary, etc.      │
├────────────────────────────────────────────────────────────────┤
│  Layer 4: AI Provider Layer                                    │
│  Multi-provider GenAI (OpenAI, Ollama, Gemini, Anthropic, etc) │
├────────────────────────────────────────────────────────────────┤
│  Layer 5: Reporting & Observability Layer                      │
│  Test results, screenshots, HTML/JSON/JUnit reports            │
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
┌────┴───┐┌───┴────┐┌──┴────┐┌──┴─────┐┌──┴────┐
│ Planner ││  Web   ││  API  ││ Mobile ││Report-│
│  Agent  ││Executor││Execut.││Executor││  er   │
└────────┘└────────┘└───────┘└────────┘└───────┘
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
    ${report}=    Run Agentic Test
    ...    test_objective=Test the login functionality including valid credentials,
    ...        invalid credentials, empty fields, and password recovery flow
    ...    app_context=E-commerce web application with email/password login
    ...    max_iterations=50
    Log    ${report}
    [Teardown]    Close All Browsers

Agentic Exploratory Testing
    [Documentation]    AI agent freely explores and tests the application
    Open Browser    https://myapp.example.com    chrome
    ${report}=    Run Agentic Exploration
    ...    app_context=E-commerce platform with product catalog, shopping cart and checkout
    ...    focus_areas=navigation, search, product filtering, cart operations
    ...    max_iterations=100
    Log    ${report}
    [Teardown]    Close All Browsers
```

### API Testing

```robot
*** Settings ***
Library    RequestsLibrary
Library    AIAgentic    platform=Ollama    model=llama3.3

*** Test Cases ***
Agentic REST API Test
    Create Session    api    https://api.example.com
    ${report}=    Run Agentic API Test
    ...    test_objective=Test the user management API endpoints including
    ...        CRUD operations, authentication, error handling, and edge cases
    ...    base_url=https://api.example.com
    ...    api_spec_url=https://api.example.com/openapi.json
    ...    max_iterations=30
    Log    ${report}
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
    ${report}=    Run Agentic Mobile Test
    ...    test_objective=Test the onboarding flow, main navigation and settings screen
    ...    app_context=Android banking application
    ...    max_iterations=40
    Log    ${report}
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
| `verbose`             | False      | Enable verbose agent logging                  |
| `report_formats`      | text,json,html | Comma-separated report formats            |
| `timeout_seconds`     | 600        | Session timeout in seconds                    |
| `max_cost_usd`        | None       | Maximum session cost in USD                   |

## Keywords

| Keyword                     | Description                                       |
|----------------------------|----------------------------------------------------|
| `Run Agentic Test`         | Execute an autonomous test from a test objective   |
| `Run Agentic Exploration`  | Run exploratory testing with focus areas           |
| `Run Agentic API Test`     | Execute autonomous REST API testing                |
| `Run Agentic Mobile Test`  | Execute autonomous mobile app testing              |
| `Get Agentic Platform Info`| Return configured platform information             |

## Safety & Guardrails

- **Iteration limit**: Hard stop after `max_iterations` to prevent infinite loops
- **Timeout**: Session-level timeout enforcement (default 10 minutes)
- **Cost tracking**: Approximate token cost accumulation with optional limit
- **Error recovery**: Retry budget per action (max 3 retries)
- **Action whitelist/blacklist**: Configurable tool restrictions

## Integration with robotframework-aivision

When [robotframework-aivision](https://github.com/robco/robotframework-aivision) is loaded alongside AIAgentic, additional visual analysis capabilities become available to the agents, including screenshot analysis, visual regression detection, and accessibility validation.

## Reporting

Reports are generated in multiple formats:

- **Text**: Human-readable summary in Robot Framework logs
- **JSON**: Machine-readable structured data
- **HTML**: Rich visual report with embedded screenshots
- **JUnit XML**: CI/CD compatible format

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
