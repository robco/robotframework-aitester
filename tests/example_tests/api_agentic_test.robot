*** Settings ***
Documentation     Example: AI Agentic REST API Testing with RequestsLibrary
...
...               This test demonstrates how to use the AIAgentic library
...               to autonomously test REST API endpoints. The AI agent
...               designs API test scenarios, sends requests, validates
...               responses, and logs results into the built-in Robot Framework report.
...
...               Prerequisites:
...               - OPENAI_API_KEY environment variable set (or use Ollama for local)
...               - Target API available

Library           RequestsLibrary
Library           AIAgentic    platform=OpenAI    model=gpt-4o    test_mode=api

Suite Setup       Create Session    jsonplaceholder    ${API_BASE_URL}


*** Variables ***
${API_BASE_URL}    https://jsonplaceholder.typicode.com


*** Test Cases ***
Agentic API CRUD Test
    [Documentation]    AI agent autonomously tests CRUD operations on the Posts API.
    [Tags]    agentic    api    crud
    ${TEST_STEPS}=    Set Variable
    ...    Test Steps:
    ...    1. GET all posts and verify response is a list
    ...    2. GET a single post by ID and verify structure
    ...    3. POST a new post and verify 201 response
    ...    4. PUT update the post and verify response
    ...    5. DELETE the post and verify response
    ${status}=    Run Agentic API Test
    ...    test_objective=Test the /posts endpoint CRUD operations: GET all posts (verify response is a list), GET a single post by ID (verify structure has userId, id, title, body), POST a new post (verify 201 response), PUT to update a post, and DELETE a post.
    ...    base_url=${API_BASE_URL}
    ...    test_steps=${TEST_STEPS}
    ...    max_iterations=40
    Log    ${status}

Agentic API Validation Test
    [Documentation]    AI agent tests API input validation and error handling.
    [Tags]    agentic    api    validation
    ${status}=    Run Agentic API Test
    ...    test_objective=Test error handling and edge cases: GET a non-existent post (e.g., /posts/99999), send POST with missing required fields, send requests with invalid Content-Type headers. Verify appropriate HTTP status codes are returned (404, 400/422).
    ...    base_url=${API_BASE_URL}
    ...    max_iterations=30
    Log    ${status}

Agentic API Relationship Test
    [Documentation]    AI agent tests nested resources and relationships.
    [Tags]    agentic    api    relationships
    ${status}=    Run Agentic API Test
    ...    test_objective=Test nested resource endpoints: GET /posts/1/comments (verify comments belong to post 1), GET /users (verify user structure), GET /users/1/posts (verify all posts belong to user 1). Validate response structures and data consistency.
    ...    base_url=${API_BASE_URL}
    ...    max_iterations=30
    Log    ${status}

Agentic API Performance Smoke Test
    [Documentation]    AI agent checks basic API response times and status codes.
    [Tags]    agentic    api    performance
    ${status}=    Run Agentic API Test
    ...    test_objective=Perform a quick health check across major endpoints: GET /posts, GET /comments, GET /albums, GET /photos, GET /todos, GET /users. For each endpoint verify: HTTP 200 status code, response body is non-empty JSON array, and note the response times.
    ...    base_url=${API_BASE_URL}
    ...    max_iterations=25
    Log    ${status}
