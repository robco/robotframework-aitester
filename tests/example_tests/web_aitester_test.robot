*** Settings ***
Documentation     Example: AI Web Testing with AITester
...
...               This test demonstrates how to use the AITester library
...               to autonomously test a web application. The AI agent
...               designs test scenarios, executes browser actions, and
...               logs results into the built-in Robot Framework report.
...               The browser is opened in Suite Setup; AITester will
...               reuse the existing session and will not open a new one.
...
...               Prerequisites:
...               - ChromeDriver or GeckoDriver installed
...               - OPENAI_API_KEY environment variable set (or use Ollama for local)
...               - Target web application running

Library           SeleniumLibrary
Library           AITester    platform=OpenAI    model=gpt-4o    test_mode=web

Suite Setup       Open Browser    ${APP_URL}    ${BROWSER}
Suite Teardown    Close All Browsers


*** Variables ***
${APP_URL}        https://the-internet.herokuapp.com
${BROWSER}        chrome


*** Test Cases ***
AI Login Flow Test
    [Documentation]    AI agent autonomously tests the login functionality.
    [Tags]    aitester    web    login
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. Open the login page
    ...    2. Login with valid credentials and verify success
    ...    3. Login with invalid credentials and verify error message
    ${status}=    Run AI Test
    ...    test_objective=Test the login page at /login. Try valid credentials (tomsmith / SuperSecretPassword!) and verify successful login. Then try invalid credentials and verify error messages are shown correctly.
    ...    app_context=Heroku test application with a login page that accepts username and password
    ...    test_steps=${TEST_STEPS}
    ...    max_iterations=30
    Log    ${status}

AI Form Validation Test
    [Documentation]    AI agent tests form inputs and validation behavior.
    [Tags]    aitester    web    forms
    ${status}=    Run AI Test
    ...    test_objective=Navigate to /forgot_password and test the forgot password form. Submit with valid and invalid email addresses. Verify appropriate messages are displayed.
    ...    app_context=Heroku test application with a forgot password form
    ...    max_iterations=25
    Log    ${status}

AI Exploratory Test
    [Documentation]    AI agent freely explores the application and reports findings.
    [Tags]    aitester    web    exploratory
    ${status}=    Run AI Exploration
    ...    app_context=Heroku test application with various web UI examples including checkboxes, dropdowns, dynamic loading, and drag-and-drop
    ...    focus_areas=navigation, interactive elements, dynamic content
    ...    max_iterations=50
    Log    ${status}

AI Dynamic Content Test
    [Documentation]    AI agent tests pages with dynamic and asynchronous content.
    [Tags]    aitester    web    dynamic
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. Navigate to /dynamic_loading/1
    ...    2. Click Start and wait for "Hello World!" to appear
    ...    3. Navigate to /dynamic_loading/2
    ...    4. Click Start and verify "Hello World!" appears
    ${status}=    Run AI Test
    ...    test_objective=Navigate to /dynamic_loading/1 and /dynamic_loading/2 pages. Test dynamic loading behavior: click Start button, wait for content to appear, verify the loaded text reads 'Hello World!'.
    ...    app_context=Heroku test application with dynamic loading examples
    ...    test_steps=${TEST_STEPS}
    ...    max_iterations=30
    Log    ${status}

Check Platform Configuration
    [Documentation]    Verify the AI platform is configured correctly.
    [Tags]    aitester    smoke
    ${info}=    Get AI Platform Info
    Log    ${info}
    Should Contain    ${info}    OpenAI
