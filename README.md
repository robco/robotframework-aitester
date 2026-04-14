[![Python Package CI](https://github.com/robco/robotframework-aitester/actions/workflows/python-package.yml/badge.svg)](https://github.com/robco/robotframework-aitester/actions/workflows/python-package.yml)

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/robco)
# Robot Framework AI Tester

[![Robot Framework](https://img.shields.io/badge/Robot%20Framework-6.0%2B-brightgreen)](https://robotframework.org)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

`robotframework-aitester` is a Robot Framework library for autonomous, AI-driven
testing across web, API, and mobile flows. By combining the
[Strands Agents SDK](https://github.com/strands-agents/sdk-python) with native
Robot Framework library reuse, it lets testers specify **what to test** rather
than scripting every interaction detail by hand.

Supply a scenario, risk area, or numbered business flow for a target
application and the agent will plan or reuse a flow, execute it, adapt around
common transient blockers, capture evidence, and log results into Robot
Framework's built-in `log.html` / `report.html`.

The current executor contract is fully autonomous. There is no
manual-intervention pause path: when a flow stalls, the agent inspects live
state, clears blockers, reuses Robot Framework variables when available, tries
safe alternate paths, and fails the blocked step with precise evidence if the
gate cannot be completed autonomously.

For UI modes, _AITester_ is strongly session-reuse oriented. The recommended
pattern is still to open the browser or mobile app with _SeleniumLibrary_ or
_AppiumLibrary_ first and let _AITester_ attach to that session. When no active
session exists and enough entry-point information is available, the web/mobile
toolsets can still create an initial session through the underlying RF library.

## Feature Highlights

- Direct single-mode execution uses a fast path: `Planner -> Web/API/Mobile Executor`, while user-defined numbered `test_steps` skip planning and run straight in the target executor.
- `Run AI Exploration` also uses the direct executor path and skips a planner handoff.
- Numbered steps embedded directly in the objective are also detected and treated as the main flow, even if `test_steps` is not passed separately.
- If `test_steps` is omitted, AITester can auto-detect numbered steps from common RF variables such as `${TEST_STEPS}`, `${AI_STEPS}`, `${AI_TEST_STEPS}`, `${AITESTER_TEST_STEPS}`, and `${USER_TEST_STEPS}`.
- Supervisor orchestration remains available internally as a fallback path for unsupported or custom execution flows.
- Instrumented tool bridge records step status, duration, assertion details, and screenshot references, surfacing them in RF logs via the `AI Step` keyword.
- Browser analysis tools share a cached `get_page_snapshot` view and derive interactive elements, page structure, form fields, links, text content, and console errors from that shared page state.
- Browser snapshots now expose stable per-snapshot element IDs, enabling semantic actions such as snapshot-based click, input, select, and assertions instead of raw locator guessing.
- Mobile analysis tools now reuse a cached Appium source snapshot across screen-summary and source-inspection calls until the UI changes.
- Mobile screen snapshots now expose stable per-snapshot element IDs, enabling the same semantic action pattern for native and hybrid flows.
- Mobile runs now include higher-level Appium helpers for loading waits, picker selection, keyboard control, context switching, and back navigation.
- Web and mobile executors can add minimal recovery actions when the requested flow is blocked by cookie banners, consent modals, permission dialogs, tutorials, or similar transient UI interruptions. For web runs, cookie/consent banners are accepted by default unless the user explicitly says otherwise.
- Hard gates such as CAPTCHA, MFA, OTP entry, approval dialogs, or legal confirmations no longer escalate to a human-intervention tool. Executors stay autonomous, consult suite variables, and fail with evidence if the gate cannot be completed safely.
- Utility tools provide assertions, JSON parsing, timing, RF variable access, execution observations, and optional AIVision screenshot analysis.
- RF built-in reporting with embedded screenshots, cached screenshot artifacts, and high-level step grouping when user-defined steps are provided.

## Keywords Documentation

Keywords documentation can be found [here](https://robco.github.io/robotframework-aitester/).

## Prerequisites

- For web runs, open the target browser with _SeleniumLibrary_ before calling `Run AI Test` or `Run AI Exploration`.
- For mobile runs, start the Appium server, device or emulator, and open the application with _AppiumLibrary_ before calling `Run AI Mobile Test` or `Run AI Exploration`.
- For API runs, load _RequestsLibrary_ in the suite and provide `base_url` or an already-initialized session context when relevant.
- Install only the extras you need for the target mode and provider.
- Set provider credentials through environment variables such as `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY` when required.
- If _SeleniumLibrary_, _RequestsLibrary_, or _AppiumLibrary_ is imported with an alias, pass the corresponding `selenium_library`, `requests_library`, or `appium_library` constructor argument so _AITester_ can attach to the existing session.
- `Run AI Exploration` uses the library's configured `test_mode`; set `test_mode=mobile` at library import if you want mobile exploratory execution.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 1: RF Keyword Layer                                       │
│  .robot files → AITester keywords (Run AI Test, etc.)            │
├──────────────────────────────────────────────────────────────────┤
│  Layer 2: Agent Orchestration Layer                              │
│  Direct Planner/Executor fast path or Supervisor fallback        │
├──────────────────────────────────────────────────────────────────┤
│  Layer 3: Tool Bridge Layer                                      │
│  Instrumented tools (Selenium/Requests/Appium + cached analysis) │
├──────────────────────────────────────────────────────────────────┤
│  Layer 4: AI Provider Layer                                      │
│  Multi-provider GenAI (OpenAI, Ollama, Gemini, Anthropic, etc)   │
├──────────────────────────────────────────────────────────────────┤
│  Layer 5: Reporting & Observability Layer                        │
│  Test results, step logs, screenshots (RF log.html/report.html)  │
└──────────────────────────────────────────────────────────────────┘
```

### Runtime Paths

```
Default single-mode path:

RF Keyword ──> Planner ──> Web/API/Mobile Executor

User-defined numbered `test_steps`:

RF Keyword ─────────────────> Web/API/Mobile Executor

Fallback path:

RF Keyword ──> Supervisor ──> Planner / Web / API / Mobile
```

In practice, most web, API, mobile, and exploratory runs now use the direct executor path.

## Installation

```bash
# Base installation
# Includes OpenAI-, Gemini-, and Ollama-compatible model support
pip install robotframework-aitester

# With web testing support
pip install robotframework-aitester[web]

# With API testing support
pip install robotframework-aitester[api]

# With mobile testing support
pip install robotframework-aitester[mobile]

# With all testing modes
pip install robotframework-aitester[all]

# With Bedrock support
pip install robotframework-aitester[all,bedrock]

# With Anthropic support
pip install robotframework-aitester[all,anthropic]

# Development
pip install robotframework-aitester[all,anthropic,bedrock,dev]
```

Recommended production installs:

- `pip install robotframework-aitester[web]` for Selenium-based UI suites
- `pip install robotframework-aitester[api]` for RequestsLibrary-based API suites
- `pip install robotframework-aitester[mobile]` for Appium-based mobile suites
- Base install already includes OpenAI, Gemini, and Ollama provider support through `strands-agents[openai,ollama,gemini]`
- Add `[anthropic]` or `[bedrock]` only when your selected GenAI backend needs those optional providers

## Quick Start

### Web Testing

```robot
*** Settings ***
Library    SeleniumLibrary
Library    AITester    platform=OpenAI    api_key=%{OPENAI_API_KEY}    model=gpt-4o

*** Test Cases ***
AI Login Flow Test
    [Documentation]    AI agent autonomously tests the login functionality
    Open Browser    https://myapp.example.com    chrome
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. Open the login page
    ...    2. Attempt login with valid credentials and verify success
    ...    3. Attempt login with invalid credentials and verify error message
    ${status}=    Run AI Test
    ...    test_objective=Test the login functionality including valid credentials,
    ...        invalid credentials, empty fields, and password recovery flow
    ...    app_context=E-commerce web application with email/password login
    ...    test_steps=${TEST_STEPS}
    ...    max_iterations=50
    Log    ${status}
    [Teardown]    Close All Browsers

AI Exploratory Testing
    [Documentation]    AI agent freely explores and tests the application
    Open Browser    https://myapp.example.com    chrome
    ${status}=    Run AI Exploration
    ...    app_context=E-commerce platform with product catalog, shopping cart and checkout
    ...    focus_areas=navigation, search, product filtering, cart operations
    ...    max_iterations=100
    Log    ${status}
    [Teardown]    Close All Browsers
```

The browser opened by `Open Browser` is reused by the agent. If a session is
already active, _AITester_ will reuse it and refuse to open a new one.

When numbered `test_steps` are supplied, those steps are treated as the main flow
and executed directly in order without a separate planning handoff.

Those steps are treated as intent checkpoints rather than a pixel-perfect script.
The agent may insert minimal support actions, such as dismissing a cookie banner,
opening a menu, waiting for the page to settle, or retrying after a transient blocker,
as long as the requested business flow stays intact.

If the flow hits a hard gate, the agent does not stop and wait for a human. It
first tries suite-provided data via `get_rf_variable`, safe alternate visible
paths, and evidence capture before failing the blocked step precisely.

### API Testing

```robot
*** Settings ***
Library    RequestsLibrary
Library    AITester    platform=Ollama    model=llama3.3

*** Test Cases ***
AI REST API Test
    Create Session    api    https://api.example.com
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. Create a user via POST /users
    ...    2. Fetch the user via GET /users/{id}
    ...    3. Update the user via PUT /users/{id}
    ...    4. Delete the user via DELETE /users/{id}
    ${status}=    Run AI API Test
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
Library    AITester    platform=Gemini    api_key=%{GEMINI_API_KEY}

*** Test Cases ***
AI Mobile App Test
    Open Application    http://localhost:4723/wd/hub
    ...    platformName=Android    app=com.example.app
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. Complete the onboarding flow
    ...    2. Navigate to the main dashboard
    ...    3. Open settings and verify key options
    ${status}=    Run AI Mobile Test
    ...    test_objective=Test the onboarding flow, main navigation and settings screen
    ...    app_context=Android banking application
    ...    test_steps=${TEST_STEPS}
    ...    max_iterations=40
    Log    ${status}
    [Teardown]    Close Application
```

For mobile runs, _AITester_ expects an active AppiumLibrary session and works best
when `app_context` and numbered `test_steps` make the target screen, account
state, and intended path explicit. It can now wait on loading indicators, work
through common pickers, hide the on-screen keyboard, switch hybrid contexts,
and use back navigation without dropping down to raw Appium commands.

For mobile exploratory testing, import the library with `test_mode=mobile` and
then call `Run AI Exploration`.

## Supported AI Platforms

| Platform  | Default Model                     | Provider            | Notes                         |
|-----------|-----------------------------------|---------------------|-------------------------------|
| OpenAI    | gpt-4o                            | OpenAI API          | Requires `OPENAI_API_KEY`     |
| Ollama    | llama3.3                          | Local Ollama        | Free, local inference         |
| Docker Model | ai/qwen3-vl:8B-Q8_K_XL         | Local Docker Model Runner | Free, local inference   |
| Gemini    | gemini-2.0-flash                  | Google AI           | Requires `GEMINI_API_KEY`     |
| Anthropic | claude-sonnet-4-5                 | Anthropic API       | Requires `ANTHROPIC_API_KEY`  |
| Bedrock   | us.anthropic.claude-sonnet-4-5-20251101-v1:0 | AWS Bedrock | Uses AWS credentials       |
| Manual    | User-specified                    | OpenAI-compatible   | Bring your own compatible endpoint; typically pair with explicit `model` and `base_url` |

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
Library    AITester
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
| `api_key`             | (env var)  | API key override; ignored for Docker Model, which always uses `dummy` |
| `base_url`            | (varies)   | AI provider base URL override                 |
| `max_iterations`      | 50         | Maximum agent iterations                      |
| `test_mode`           | web        | Default test mode (web, api, mobile)          |
| `headless`            | False      | Stored as configuration metadata; browser/app startup remains owned by SeleniumLibrary/AppiumLibrary |
| `screenshot_on_action`| True       | Reserved for future screenshot policy tuning; current prompts/tool calls still decide when screenshots are taken |
| `verbose`             | False      | Enable verbose agent logging                  |
| `selenium_library`    | SeleniumLibrary | SeleniumLibrary name/alias for existing sessions |
| `requests_library`    | RequestsLibrary | RequestsLibrary name/alias for existing sessions |
| `appium_library`      | AppiumLibrary | AppiumLibrary name/alias for existing sessions |
| `timeout_seconds`     | 600        | Configures `SafetyGuard` timeout metadata     |
| `max_cost_usd`        | None       | Configures `SafetyGuard` cost-limit metadata  |

If you import _SeleniumLibrary_/_RequestsLibrary_/_AppiumLibrary_ with an alias,
pass the corresponding `*_library` parameter so AI tools attach to the
already-opened session.

For `platform=DockerModel`, _AITester_ automatically passes `api_key=dummy`
to the OpenAI-compatible Strands client. No environment variable or
constructor argument is required for that platform.

For `platform=Manual`, pass the OpenAI-compatible endpoint details yourself,
typically with both `model=` and `base_url=` and, if needed, `api_key=`.

Important: _AITester_ can only drive sessions created by _SeleniumLibrary_/_AppiumLibrary_.
If you open a browser/app manually or through another tool, the agent will not
be able to interact with it.

### Session Reuse

If an active Selenium or Appium session is detected, _AITester_ **reuses it**
and **refuses to open a new session on a different device**. This prevents
cases like opening a desktop browser when an Android Appium browser is already
running. Make sure the existing session is open before calling `Run AI*`,
and set `selenium_library` / `appium_library` if you imported those libraries
with aliases.

If no active session exists, the web/mobile executors still have
`selenium_open_browser` / `appium_open_application` available through the RF
library bridge. In practice, deterministic suites work best when your setup
opens the target browser or app explicitly and lets AITester reuse it.

```robot
*** Settings ***
Library    SeleniumLibrary    WITH NAME    Web
Library    AITester    platform=OpenAI    selenium_library=Web

*** Test Cases ***
Reuse Existing Web Session
    Open Browser    https://example.com    chrome
    ${status}=    Run AI Test
    ...    test_objective=Smoke test the landing page
    Log    ${status}
```

## Keywords

| Keyword                     | Description                                       |
|----------------------------|----------------------------------------------------|
| `Run AI Test`              | Execute an autonomous test from a test objective (supports `test_steps`, `scroll_into_view`) |
| `Run AI Exploration`       | Run exploratory testing with focus areas (supports `scroll_into_view`) |
| `Run AI API Test`          | Execute autonomous REST API testing (supports `test_steps`, `scroll_into_view`) |
| `Run AI Mobile Test`       | Execute autonomous mobile app testing (supports `test_steps`, `scroll_into_view`) |
| `Get AI Platform Info`     | Return configured platform information             |
| `AI Step`                  | Step-level logging keyword used by the agent tools |
| `AI High Level Step`       | High-level step marker used for RF log grouping    |

## Safety & Guardrails

- **Session reuse enforcement**: Existing Selenium/Appium sessions are reused and conflicting new sessions are refused.
- **Destructive session protection**: Browser close/restart and mobile app close/reset/relaunch actions are blocked unless the user explicitly asked for them.
- **Direct URL restraint**: After initial entry, UI executors are instructed to navigate like a real user through visible controls instead of jumping to internal URLs unless the user explicitly requested a concrete URL.
- **Execution metadata**: `max_iterations` is passed into planner/executor prompts and stored on the active session for reporting.
- **Session bookkeeping**: `timeout_seconds` and `max_cost_usd` initialize `SafetyGuard` metadata for the run.
- **Autonomous recovery**: Executors are instructed to inspect state, clear blockers, inspect frames or contexts, reuse RF variables, and fail with precise evidence instead of pausing for human input.
- **Post-run validation**: User-defined high-level steps and UI-action coverage are checked at session finalization for web/mobile runs.

## Integration with robotframework-aivision

When [robotframework-aivision](https://github.com/robco/robotframework-aivision) is loaded alongside _AITester_, the shared `analyze_screenshot` tool can ask AI-vision questions about a captured screenshot. If AIVision is not loaded, the tool falls back to a plain text notice instead of breaking the run.

## Reporting

robotframework-aitester uses Robot Framework built-in reporting
(`log.html` / `report.html`). No custom standalone reports are generated.
`Run AI*` keywords return a short completion status; review details in the RF log.

Robot Framework `6.0+` is supported, but `7.4+` gives the best HTML log
rendering for embedded screenshots and richer keyword output.

When you provide user-defined numbered test steps (via the `test_steps` argument
or one of the common step variables `${TEST_STEPS}`, `${AI_STEPS}`,
`${AI_TEST_STEPS}`, `${AITESTER_TEST_STEPS}`, or `${USER_TEST_STEPS}`), those steps are treated as the main flow and
AI actions are grouped under them in
the RF log with embedded screenshots for readability.

If `test_steps` is omitted and AITester auto-detects one of those variables, it
logs which variable was used. For clarity and repeatability, passing
`test_steps=${TEST_STEPS}` explicitly is still recommended.

If `test_objective` is left empty and no numbered steps are available, the
`Run AI*` keywords now fail fast instead of silently improvising a generic flow.

If the agent's completion message explicitly reports a failed status,
`Run AI*` will fail the Robot test to keep the RF result consistent.

Additional reporting features:

- Step-level logging via `AI Step` with status, duration, assertions, and embedded screenshots
- High-level grouping when user-defined steps are supplied
- Screenshot paths are normalized into `${OUTPUT_DIR}`, and embedded preview artifacts are cached under `${OUTPUT_DIR}/aitester-screenshots`
- Screenshot files may use any image extension supported by the underlying library (e.g., `.png`, `.jpg`, `.jpeg`).
- When a screenshot filename is explicitly provided for Selenium/Appium, _AITester_ normalizes it to `.png`
  to avoid WebDriver warnings about mismatched file types.

## Browser State Analysis

For web sessions, _AITester_ now prefers a shared cached page snapshot instead of
running multiple overlapping DOM scans on every analysis step.

- `get_page_snapshot` captures title, URL, text preview, forms, links, headings, interactive elements, and possible blocking overlays in one pass
- `get_loading_state` and the loading section of `get_page_snapshot` use DOM/accessibility heuristics to surface visible loading indicators such as `aria-busy` regions, progress bars, loaders/spinners, and skeleton/shimmer placeholders
- `get_interactive_elements`, `get_page_structure`, `get_page_text_content`, `get_all_links`, `get_frame_inventory`, and `get_form_fields` reuse that cached snapshot where possible
- iframe-heavy pages are now better supported: the snapshot includes iframe/frame inventory, and `get_frame_inventory` summarizes candidate frame locators, titles, URLs, and same-origin previews so the agent can switch into the right frame before interacting
- Successful mutating Selenium actions invalidate the cache so later analysis reflects the latest page state
- `selenium_handle_common_blockers` uses that snapshot to clear common blockers such as cookie banners, consent popups, newsletter modals, and tutorial overlays before retrying the intended action
- When a cookie or consent banner is detected during a web run, _AITester_ prefers accept/allow actions so the banner disappears unless the user explicitly requested a different choice
- For slow pages with loading spinners or skeleton screens, prefer condition-based waits such as
  `selenium_wait_until_page_contains`, `selenium_wait_until_page_contains_element`,
  `selenium_wait_until_element_is_not_visible`, `selenium_wait_until_page_does_not_contain`,
  and `selenium_wait_until_page_does_not_contain_element` instead of fixed delays
- When the concrete loading implementation is unknown, `selenium_wait_for_loading_to_finish`
  polls fresh page snapshots and waits for consecutive clean checks with no detected loading
  indicators; treat it as a best-effort readiness heuristic, not a guarantee of network idle

## Mobile State Analysis

For mobile sessions, AITester can inspect the current Appium source and summarize
likely interruptions before continuing the requested flow. The current Appium
source is cached per session so repeated calls do not re-fetch the same screen
state unless a mutating Appium action succeeds or a refresh is requested.

- `appium_get_view_snapshot` gives a compact screen summary with text preview and likely interruption candidates
- `appium_get_source`, `appium_get_view_snapshot`, `appium_get_loading_state`, `appium_get_interactive_elements`, `appium_get_screen_structure`, and `appium_get_context_inventory` reuse the cached screen snapshot where possible
- `appium_handle_common_interruptions` can clear common transient blockers such as permission dialogs, update prompts, onboarding/tutorial screens, and similar modal interruptions
- High-level mobile execution can now use condition-based waits, picker selection helpers, keyboard visibility control, keycode input, context switching, and back navigation helpers instead of relying on fixed delays or raw Appium calls
- Mobile executor prompts now explicitly allow minimal recovery steps when user-defined steps are imprecise or temporarily blocked, while preserving the current app session unless the user asked to restart it

## UI Element Scrolling

All main AI keywords accept `scroll_into_view` (default `True`). When enabled,
the agent scrolls elements into view before interacting with them, improving
observability in the RF log/screenshots.

```robot
${status}=    Run AI Test
...    test_objective=Validate checkout flow
...    scroll_into_view=False
```
