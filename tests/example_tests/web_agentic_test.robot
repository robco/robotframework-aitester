*** Settings ***
Documentation     Example: AI Agentic Web Testing with SeleniumLibrary
...
...               This test demonstrates how to use the AIAgentic library
...               to autonomously test a web application. The AI agent
...               designs test scenarios, executes browser actions, and
...               logs results into the built-in Robot Framework report.
...
...               Prerequisites:
...               - ChromeDriver or GeckoDriver installed
...               - OPENAI_API_KEY environment variable set (or use Ollama for local)
...               - Target web application running

Library           SeleniumLibrary
Library           AIAgentic    platform=OpenAI    model=gpt-4o    test_mode=web

Suite Setup       Open Browser    ${APP_URL}    ${BROWSER}
Suite Teardown    Close All Browsers


*** Variables ***
${APP_URL}        https://the-internet.herokuapp.com
${BROWSER}        chrome


*** Test Cases ***
Agentic Login Flow Test
    [Documentation]    AI agent autonomously tests the login functionality.
    [Tags]    agentic    web    login
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. Open the login page
    ...    2. Login with valid credentials and verify success
    ...    3. Login with invalid credentials and verify error message
    ${status}=    Run Agentic Test
    ...    test_objective=Test the login page at /login. Try valid credentials (tomsmith / SuperSecretPassword!) and verify successful login. Then try invalid credentials and verify error messages are shown correctly.
    ...    app_context=Heroku test application with a login page that accepts username and password
    ...    test_steps=${TEST_STEPS}
    ...    max_iterations=30
    Log    ${status}

Agentic Form Validation Test
    [Documentation]    AI agent tests form inputs and validation behavior.
    [Tags]    agentic    web    forms
    ${status}=    Run Agentic Test
    ...    test_objective=Navigate to /forgot_password and test the forgot password form. Submit with valid and invalid email addresses. Verify appropriate messages are displayed.
    ...    app_context=Heroku test application with a forgot password form
    ...    max_iterations=25
    Log    ${status}

Agentic Exploratory Test
    [Documentation]    AI agent freely explores the application and reports findings.
    [Tags]    agentic    web    exploratory
    ${status}=    Run Agentic Exploration
    ...    app_context=Heroku test application with various web UI examples including checkboxes, dropdowns, dynamic loading, and drag-and-drop
    ...    focus_areas=navigation, interactive elements, dynamic content
    ...    max_iterations=50
    Log    ${status}

Agentic Dynamic Content Test
    [Documentation]    AI agent tests pages with dynamic and asynchronous content.
    [Tags]    agentic    web    dynamic
    ${status}=    Run Agentic Test
    ...    test_objective=Navigate to /dynamic_loading/1 and /dynamic_loading/2 pages. Test dynamic loading behavior: click Start button, wait for content to appear, verify the loaded text reads 'Hello World!'.
    ...    app_context=Heroku test application with dynamic loading examples
    ...    max_iterations=30
    Log    ${status}

Check Platform Configuration
    [Documentation]    Verify the AI platform is configured correctly.
    [Tags]    agentic    smoke
    ${info}=    Get Agentic Platform Info
    Log    ${info}
    Should Contain    ${info}    OpenAI
