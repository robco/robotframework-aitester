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
System prompt templates for robotframework-aiagentic agents.

Each module defines the system prompt for one specialist agent:
- supervisor: Orchestrates specialist agents
- planner: Designs test scenarios
- web_executor: Executes Selenium-based web tests
- api_executor: Executes REST API tests
- mobile_executor: Executes Appium-based mobile tests
- reporter: Synthesizes test results
"""
