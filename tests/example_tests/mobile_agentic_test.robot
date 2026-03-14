*** Settings ***
Documentation     Example: AI Agentic Mobile App Testing with AppiumLibrary
...
...               This test demonstrates how to use the AIAgentic library
...               to autonomously test a mobile application. The AI agent
...               designs mobile test scenarios, performs touch interactions,
...               and generates a structured report.
...
...               Prerequisites:
...               - Appium server running (default: http://localhost:4723)
...               - Android emulator or iOS simulator available
...               - OPENAI_API_KEY environment variable set (or use Ollama for local)
...               - Target mobile application APK/IPA available

Library           AppiumLibrary
Library           AIAgentic    platform=OpenAI    model=gpt-4o    test_mode=mobile

Suite Setup       Open Application    ${APPIUM_URL}
...               platformName=${PLATFORM_NAME}
...               deviceName=${DEVICE_NAME}
...               app=${APP_PATH}
...               automationName=UiAutomator2
Suite Teardown    Close All Applications


*** Variables ***
${APPIUM_URL}         http://localhost:4723
${PLATFORM_NAME}      Android
${DEVICE_NAME}        emulator-5554
${APP_PATH}           ${CURDIR}/../../app/sample.apk


*** Test Cases ***
Agentic Mobile Onboarding Test
    [Documentation]    AI agent autonomously tests the app onboarding flow.
    [Tags]    agentic    mobile    onboarding
    ${report}=    Run Agentic Mobile Test
    ...    test_objective=Test the onboarding/welcome screens. Swipe through each screen, verify content is displayed, tap Skip or Next buttons, and verify arrival at the main screen or login page.
    ...    app_context=Android application with multi-step onboarding wizard
    ...    max_iterations=30
    Log    ${report}

Agentic Mobile Navigation Test
    [Documentation]    AI agent explores the app navigation structure.
    [Tags]    agentic    mobile    navigation
    ${report}=    Run Agentic Mobile Test
    ...    test_objective=Explore the main navigation of the app. Test bottom navigation tabs (if present), hamburger menu, back button behavior, and deep navigation paths. Verify each screen loads correctly without crashes.
    ...    app_context=Android application with standard navigation patterns
    ...    max_iterations=40
    Log    ${report}

Agentic Mobile Form Input Test
    [Documentation]    AI agent tests mobile form interactions.
    [Tags]    agentic    mobile    forms
    ${report}=    Run Agentic Mobile Test
    ...    test_objective=Find and test form inputs in the app. Test text fields (verify keyboard appears), dropdowns/spinners, checkboxes, toggles, and date pickers. Verify form submission and validation messages.
    ...    app_context=Android application with registration or settings forms
    ...    max_iterations=35
    Log    ${report}

Agentic Mobile Gesture Test
    [Documentation]    AI agent tests gesture-based interactions.
    [Tags]    agentic    mobile    gestures
    ${report}=    Run Agentic Mobile Test
    ...    test_objective=Test gesture interactions: scroll through lists (verify new content loads), pull-to-refresh (verify content updates), swipe actions on list items (verify swipe actions like delete or archive), and long-press actions.
    ...    app_context=Android application with scrollable lists and gesture support
    ...    max_iterations=30
    Log    ${report}
