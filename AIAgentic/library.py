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
Main Robot Framework library class for robotframework-aiagentic.

This is the public interface of the library, exposing Robot Framework keywords
such as Run Agentic Test, Run Agentic Exploration, and Run Agentic API Test
that testers invoke from .robot files.
"""

import html
import logging
import os
import re
import shutil
from typing import Any, Dict, Optional, List, Tuple

from robot.api.deco import keyword
from robot.api import logger as rf_logger
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .platforms import Platforms
from .genai import GenAIProvider
from .orchestrator import AgentOrchestrator
from .executor import (
    SafetyGuard,
    SessionStatus,
    create_session,
    set_active_session,
)

logger = logging.getLogger(__name__)


class AIAgentic:
    """AI Agentic Testing Library for Robot Framework.

    Enables fully autonomous, AI-driven test automation by combining
    the Strands Agents SDK with native RF library integration. Users
    supply a test objective and the AI agent autonomously designs,
    executes, and reports on test scenarios.

    Supported test modes:
    - web: Selenium-based browser testing (requires SeleniumLibrary)
    - api: REST API testing (requires RequestsLibrary)
    - mobile: Appium-based mobile testing (requires AppiumLibrary)

    Supported AI platforms: OpenAI, Ollama, Gemini, Anthropic, Bedrock

    Examples:
    | Library | AIAgentic | platform=OpenAI | api_key=%{OPENAI_API_KEY} | model=gpt-4o |
    | Library | AIAgentic | platform=Ollama | model=llama3.3 |
    """

    ROBOT_LIBRARY_SCOPE = "GLOBAL"
    ROBOT_LIBRARY_VERSION = "0.1.0"

    def __init__(
        self,
        platform: str = "OpenAI",
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        max_iterations: int = 50,
        test_mode: str = "web",
        headless: bool = False,
        screenshot_on_action: bool = True,
        verbose: bool = False,
        report_formats: str = "text,json,html",
        timeout_seconds: float = 600,
        max_cost_usd: float = None,
        selenium_library: str = "SeleniumLibrary",
        requests_library: str = "RequestsLibrary",
        appium_library: str = "AppiumLibrary",
    ):
        """Initialize the AIAgentic library.

        Args:
            platform: AI platform name (OpenAI, Ollama, Gemini, Anthropic, Bedrock, Manual).
            model: Model ID override. Uses platform default if not specified.
            api_key: API key override. Resolves from environment if not specified.
            base_url: Base URL override. Uses platform default if not specified.
            max_iterations: Maximum agent iterations per test run. Default 50.
            test_mode: Default testing mode (web, api, mobile). Default web.
            headless: Run browser in headless mode. Default False.
            screenshot_on_action: Capture screenshots after actions. Default True.
            verbose: Enable verbose agent logging. Default False.
            report_formats: Deprecated (ignored). RF built-in reporting is used.
            timeout_seconds: Session timeout in seconds. Default 600 (10 min).
            max_cost_usd: Maximum session cost in USD. None for unlimited.
            selenium_library: SeleniumLibrary name or alias (for existing sessions).
            requests_library: RequestsLibrary name or alias (for existing sessions).
            appium_library: AppiumLibrary name or alias (for existing sessions).
        """
        # Resolve platform enum
        try:
            self.platform = Platforms[platform]
        except KeyError:
            valid = ", ".join(p.name for p in Platforms)
            raise ValueError(
                f"Unknown platform '{platform}'. Valid options: {valid}"
            )

        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_iterations = int(max_iterations)
        self.test_mode = test_mode
        self.headless = headless
        self.screenshot_on_action = screenshot_on_action
        self.verbose = verbose
        # report_formats is deprecated and intentionally ignored to enforce RF built-in reporting only
        self.report_formats = []
        self.timeout_seconds = float(timeout_seconds)
        self.max_cost_usd = float(max_cost_usd) if max_cost_usd else None
        self.selenium_library = selenium_library
        self.requests_library = requests_library
        self.appium_library = appium_library

        # Lazy-initialized components
        self._orchestrator = None
        self._genai_provider = None
        self._safety_guard = None
        self._available_libraries = {}
        self._available_library_keys = set()

        self._register_library_aliases()

        logger.info(
            "AIAgentic initialized: platform=%s, model=%s, test_mode=%s",
            platform,
            model or self.platform.value["default_model"],
            test_mode,
        )

    def _get_available_libraries(self):
        """Discover which RF libraries are loaded.

        Returns:
            Dict mapping library name to library instance.
        """
        libs = {}
        for name in [
            self.selenium_library,
            self.appium_library,
            self.requests_library,
            "SeleniumLibrary",
            "AppiumLibrary",
            "RequestsLibrary",
        ]:
            try:
                libs[name] = BuiltIn().get_library_instance(name)
            except (RuntimeError, RobotNotRunningError):
                pass
        if self.selenium_library in libs and "SeleniumLibrary" not in libs:
            libs["SeleniumLibrary"] = libs[self.selenium_library]
        if self.requests_library in libs and "RequestsLibrary" not in libs:
            libs["RequestsLibrary"] = libs[self.requests_library]
        if self.appium_library in libs and "AppiumLibrary" not in libs:
            libs["AppiumLibrary"] = libs[self.appium_library]
        return libs

    def _register_library_aliases(self):
        """Expose configured library aliases to tool modules via RF variables."""
        try:
            bi = BuiltIn()
            if self.selenium_library:
                bi.set_global_variable("${AIAGENTIC_SELENIUM_LIBRARY}", self.selenium_library)
            if self.requests_library:
                bi.set_global_variable("${AIAGENTIC_REQUESTS_LIBRARY}", self.requests_library)
            if self.appium_library:
                bi.set_global_variable("${AIAGENTIC_APPIUM_LIBRARY}", self.appium_library)
        except (RuntimeError, RobotNotRunningError):
            pass

    def _ensure_orchestrator(self):
        """Lazy initialization of the agent orchestrator."""
        self._register_library_aliases()
        available_libs = self._get_available_libraries()
        available_keys = set(available_libs.keys())

        if (
            self._orchestrator is None
            or available_keys != self._available_library_keys
        ):
            # Create or reuse GenAI provider
            if self._genai_provider is None:
                self._genai_provider = GenAIProvider(
                    platform=self.platform,
                    model=self.model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            model = self._genai_provider.create_model()

            if not available_libs:
                logger.warning(
                    "No testing libraries (SeleniumLibrary, RequestsLibrary, AppiumLibrary) "
                    "detected. Agent will have limited tool capabilities."
                )

            self._orchestrator = AgentOrchestrator(
                model=model,
                available_libraries=available_libs,
                verbose=self.verbose,
            )
            self._available_libraries = available_libs
            self._available_library_keys = available_keys

            self._safety_guard = SafetyGuard(
                max_iterations=self.max_iterations,
                timeout_seconds=self.timeout_seconds,
                max_cost_usd=self.max_cost_usd,
            )

            logger.info(
                "Orchestrator initialized with libraries: %s",
                list(available_libs.keys()),
            )

    def _get_library_instance(self, name: str):
        """Safely retrieve a Robot Framework library instance."""
        try:
            return BuiltIn().get_library_instance(name)
        except (RuntimeError, RobotNotRunningError):
            return None

    @staticmethod
    def _first_capability(caps: Dict[str, Any], *keys: str) -> Optional[Any]:
        """Return first non-empty capability matching any of the given keys."""
        if not caps:
            return None
        normalized = {str(k).lower(): v for k, v in caps.items()}
        for key in keys:
            if key in caps and caps[key]:
                return caps[key]
            low_key = str(key).lower()
            if low_key in normalized and normalized[low_key]:
                return normalized[low_key]
        return None

    def _build_web_start_state(self) -> str:
        """Describe current web start state, if any."""
        sl = self._get_library_instance(self.selenium_library) or self._get_library_instance("SeleniumLibrary")
        if not sl:
            return "Start State: No active browser session detected. Start from scratch."

        try:
            browser_ids = sl.get_browser_ids()
        except Exception as e:
            logger.debug("Unable to read browser ids: %s", e)
            return "Start State: No active browser session detected. Start from scratch."

        if not browser_ids:
            return "Start State: No active browser session detected. Start from scratch."

        url = None
        title = None
        try:
            url = sl.get_location()
        except Exception as e:
            logger.debug("Unable to read current URL: %s", e)
        try:
            title = sl.get_title()
        except Exception as e:
            logger.debug("Unable to read page title: %s", e)

        lines = [
            "Start State: Active browser session detected.",
            f"Open browsers: {len(browser_ids)}",
        ]
        if url:
            lines.append(f"Current URL: {url}")
        if title:
            lines.append(f"Title: {title}")
        return "\n".join(lines)

    def _build_mobile_start_state(self) -> str:
        """Describe current mobile start state, if any."""
        al = self._get_library_instance(self.appium_library) or self._get_library_instance("AppiumLibrary")
        if not al:
            return "Start State: No active mobile session detected. Start from scratch."

        try:
            driver = al._current_application()
        except Exception as e:
            logger.debug("Unable to read current Appium application: %s", e)
            return "Start State: No active mobile session detected. Start from scratch."

        lines = ["Start State: Active mobile session detected."]

        try:
            open_apps = al._cache.get_open_browsers()
            lines.append(f"Open applications: {len(open_apps)}")
        except Exception as e:
            logger.debug("Unable to read open Appium applications: %s", e)

        session_id = getattr(driver, "session_id", None)
        if session_id:
            lines.append(f"Session ID: {session_id}")

        context = None
        try:
            context = getattr(driver, "current_context", None)
            if callable(context):
                context = context()
        except Exception as e:
            logger.debug("Unable to read current context: %s", e)
        if context:
            lines.append(f"Current context: {context}")

        activity = None
        try:
            activity = getattr(driver, "current_activity", None)
            if callable(activity):
                activity = activity()
        except Exception as e:
            logger.debug("Unable to read current activity: %s", e)
        if activity:
            lines.append(f"Current activity: {activity}")

        package = None
        try:
            package = getattr(driver, "current_package", None)
            if callable(package):
                package = package()
        except Exception as e:
            logger.debug("Unable to read current package: %s", e)
        if package:
            lines.append(f"Current package: {package}")

        caps = getattr(driver, "capabilities", None) or getattr(
            driver, "desired_capabilities", None
        )
        if isinstance(caps, dict):
            platform = self._first_capability(
                caps, "platformName", "appium:platformName", "platform"
            )
            platform_version = self._first_capability(
                caps, "platformVersion", "appium:platformVersion"
            )
            device = self._first_capability(
                caps, "deviceName", "appium:deviceName"
            )
            automation = self._first_capability(
                caps, "automationName", "appium:automationName"
            )
            app = self._first_capability(
                caps, "app", "appium:app", "appPath"
            )
            app_package = self._first_capability(
                caps, "appPackage", "appium:appPackage"
            )
            app_activity = self._first_capability(
                caps, "appActivity", "appium:appActivity"
            )
            bundle_id = self._first_capability(
                caps, "bundleId", "appium:bundleId"
            )
            udid = self._first_capability(caps, "udid", "appium:udid")
            browser_name = self._first_capability(
                caps, "browserName", "appium:browserName"
            )

            if platform:
                lines.append(f"Platform: {platform}")
            if platform_version:
                lines.append(f"Platform version: {platform_version}")
            if device:
                lines.append(f"Device: {device}")
            if automation:
                lines.append(f"Automation: {automation}")
            if app:
                lines.append(f"App: {app}")
            if app_package:
                lines.append(f"App package: {app_package}")
            if app_activity:
                lines.append(f"App activity: {app_activity}")
            if bundle_id:
                lines.append(f"Bundle ID: {bundle_id}")
            if udid:
                lines.append(f"UDID: {udid}")
            if browser_name:
                lines.append(f"Browser: {browser_name}")

        return "\n".join(lines)

    def _build_start_state_summary(self, test_mode: str) -> str:
        """Build a start-state summary for the given test mode."""
        mode = (test_mode or "").strip().lower()
        if mode == "web":
            return self._build_web_start_state()
        if mode == "mobile":
            return self._build_mobile_start_state()
        return ""

    @staticmethod
    def _has_active_start_state(start_state: str) -> bool:
        """Return True if start-state summary reports an active session."""
        if not start_state:
            return False
        lowered = start_state.lower()
        if "active browser session detected" in lowered:
            return "no active browser session detected" not in lowered
        if "active mobile session detected" in lowered:
            return "no active mobile session detected" not in lowered
        return False

    def _resolve_start_state_and_reuse(self, test_mode: str) -> tuple[str, bool]:
        """Resolve start-state summary and reuse flag for a run."""
        start_state = self._build_start_state_summary(test_mode)
        reuse_existing_session = self._has_active_start_state(start_state)

        other_mode = None
        mode = (test_mode or "").strip().lower()
        if mode == "web":
            other_mode = "mobile"
        elif mode == "mobile":
            other_mode = "web"

        if other_mode:
            other_state = self._build_start_state_summary(other_mode)
            other_active = self._has_active_start_state(other_state)
            if other_active and not reuse_existing_session:
                reuse_existing_session = True
                start_state = (
                    "Start State: Active session detected on another device/app. "
                    "Reuse the existing session and do NOT open a new one.\n"
                    f"{other_state}"
                )

        return start_state, reuse_existing_session

    @staticmethod
    def _merge_app_context(app_context: str, start_state: str) -> str:
        """Merge app context with the detected start state."""
        if not start_state:
            return app_context
        if app_context:
            return f"{app_context}\n\n{start_state}"
        return start_state

    @staticmethod
    def _escape_html(text: str) -> str:
        return html.escape(str(text), quote=False)

    @staticmethod
    def _coerce_bool(value, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return default

    @staticmethod
    def _is_verification_step(text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        keywords = (
            "verify",
            "check",
            "confirm",
            "ensure",
            "assert",
            "validate",
            "look for",
            "find",
            "locate",
            "see",
            "presence",
        )
        return any(keyword in lowered for keyword in keywords)

    def _validate_ui_action_coverage(self, session) -> Optional[str]:
        if session.test_mode not in {"web", "mobile"}:
            return None
        total_actions = session.ui_interactions_total + session.ui_state_checks_total
        if total_actions == 0:
            return "No UI tool actions were recorded during this session."
        if not session.high_level_steps:
            return None
        missing = []
        for idx, step_text in enumerate(session.high_level_steps, start=1):
            interactions = session.ui_interactions_by_step.get(idx, 0)
            state_checks = session.ui_state_checks_by_step.get(idx, 0)
            if interactions == 0 and state_checks == 0:
                missing.append(f"{idx}. {step_text}")
                continue
            if interactions == 0 and not self._is_verification_step(step_text):
                missing.append(f"{idx}. {step_text}")
        if missing:
            return (
                "No UI interaction actions were recorded for the following steps:\n"
                + "\n".join(missing)
            )
        return None

    @staticmethod
    def _parse_numbered_steps(text: str) -> List[str]:
        """Parse numbered steps (1., 2), 3.) from free-form text."""
        if not text:
            return []
        steps = []
        current = None
        for line in str(text).splitlines():
            match = re.match(r"^\s*(\d+)[\.\)]\s+(.*)$", line)
            if match:
                if current is not None:
                    steps.append(current.rstrip())
                current = match.group(2).strip()
                continue
            if current is not None and line.strip():
                if re.match(r"^\s*[-*]\s+", line) or line.startswith(" "):
                    current += "\n" + line.strip()
                else:
                    current += " " + line.strip()
        if current is not None:
            steps.append(current.rstrip())
        return steps

    def _extract_user_defined_steps(
        self,
        test_objective: str,
        test_steps: Optional[str],
    ) -> Tuple[str, List[str], Optional[str]]:
        def normalize_text(value):
            if value is None:
                return ""
            if isinstance(value, (list, tuple)):
                return "\n".join(str(item) for item in value)
            return str(value)

        def normalize_steps(value):
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                return "\n".join(
                    f"{idx + 1}. {item}" for idx, item in enumerate(value)
                )
            return str(value)

        steps_text = None
        if test_steps and str(test_steps).strip():
            steps_text = normalize_steps(test_steps)
        else:
            try:
                candidate = BuiltIn().get_variable_value("${TEST_STEPS}")
            except (RuntimeError, RobotNotRunningError):
                candidate = None
            normalized = normalize_steps(candidate)
            if normalized and normalized.strip():
                steps_text = normalized

        objective_text = normalize_text(test_objective)
        parsed_source = steps_text if steps_text else objective_text
        steps = self._parse_numbered_steps(parsed_source)

        objective = objective_text
        if steps_text and steps_text not in objective_text:
            objective = f"{objective_text.rstrip()}\n\n{steps_text.strip()}"
        if steps:
            marker = "USER-DEFINED TEST STEPS (MAIN FLOW, HIGHEST PRIORITY)"
            if marker.lower() not in objective.lower():
                formatted = "\n".join(
                    f"{idx + 1}. {step}" for idx, step in enumerate(steps)
                )
                objective = f"{objective.rstrip()}\n\n{marker}:\n{formatted}"
        return objective, steps, steps_text

    def _log_user_defined_steps(self, steps: List[str]) -> None:
        if not steps:
            return
        items = []
        for step in steps:
            safe = self._escape_html(step).replace("\n", "<br/>")
            items.append(f"<li>{safe}</li>")
        html_block = (
            '<div style="font-family:Segoe UI,Arial,sans-serif;'
            'background:#f8f9fa;padding:10px 12px;border-radius:6px;'
            'border:1px solid #e2e6ea;margin:6px 0;">'
            '<b>User-defined Test Steps</b>'
            f"<ol style=\"margin:6px 0 0 18px;\">{''.join(items)}</ol>"
            "</div>"
        )
        rf_logger.info(html_block, html=True)

    def _ensure_screenshot_in_output(self, screenshot_path: str) -> Optional[str]:
        if not screenshot_path:
            return None
        filename = os.path.basename(screenshot_path)
        try:
            output_dir = BuiltIn().get_variable_value("${OUTPUT_DIR}")
        except RobotNotRunningError:
            output_dir = os.getcwd()
        if not output_dir:
            output_dir = os.getcwd()
        try:
            target = os.path.join(output_dir, filename)
            if os.path.exists(screenshot_path) and os.path.abspath(screenshot_path) != os.path.abspath(target):
                shutil.copy2(screenshot_path, target)
        except Exception as exc:
            logger.debug("Unable to copy screenshot to output dir: %s", exc)
        return filename

    def _build_screenshot_html(self, filename: str) -> str:
        if not filename:
            return ""
        return (
            '<div style="margin-top:6px;">'
            f'<a href="{filename}">'
            f'<img src="{filename}" style="max-width:520px; border:1px solid #ddd; border-radius:4px;">'
            "</a>"
            "</div>"
        )

    def _start_session(
        self,
        objective: str,
        app_context: str,
        test_mode: str,
        max_iterations: int,
        high_level_steps: Optional[List[str]] = None,
        reuse_existing_session: bool = False,
        start_state_summary: Optional[str] = None,
        scroll_into_view: bool = True,
    ):
        """Create and register an active session for step recording."""
        session = create_session(
            objective=objective,
            app_context=app_context,
            test_mode=test_mode,
            max_iterations=max_iterations,
            high_level_steps=high_level_steps,
            reuse_existing_session=reuse_existing_session,
            start_state_summary=start_state_summary,
            scroll_into_view=scroll_into_view,
        )
        set_active_session(session)
        return session

    def _log_basic_summary(self, session):
        """Log a brief session summary into Robot Framework log."""
        try:
            status = session.status.value.upper()
            html_summary = (
                '<div style="font-family:Segoe UI,Arial,sans-serif;'
                'background:#f8f9fa;padding:10px 12px;border-radius:6px;'
                'border:1px solid #e2e6ea;margin:6px 0;">'
                f"<b>Agentic Session Summary</b><br/>"
                f"Status: <b>{status}</b><br/>"
                f"Steps: {session.passed_steps}/{session.total_steps} passed<br/>"
                f"Duration: {session.duration_seconds:.1f}s<br/>"
                "</div>"
            )
            rf_logger.info(html_summary, html=True)
        except Exception as exc:
            logger.debug("Unable to log session summary: %s", exc)

    def _log_high_level_summary(self, session):
        """Log high-level steps with their executed agentic steps."""
        if not session.high_level_steps:
            return

        groups = {i + 1: [] for i in range(len(session.high_level_steps))}
        unassigned = []
        for step in session.steps:
            num = step.high_level_step_number
            if num in groups:
                groups[num].append(step)
            else:
                unassigned.append(step)

        parts = [
            '<div style="font-family:Segoe UI,Arial,sans-serif;'
            'background:#ffffff;padding:10px 12px;border-radius:6px;'
            'border:1px solid #e2e6ea;margin:8px 0;">',
            "<b>High-Level Step Execution</b>",
        ]

        status_colors = {
            "passed": "#2e7d32",
            "failed": "#c62828",
            "error": "#c62828",
            "skipped": "#6c757d",
        }

        for idx, title in enumerate(session.high_level_steps, start=1):
            safe_title = self._escape_html(title).replace("\n", "<br/>")
            parts.append(
                f'<div style="margin:8px 0 4px 0;"><b>Step {idx}:</b> {safe_title}</div>'
            )
            steps = groups.get(idx, [])
            if not steps:
                parts.append(
                  '<div style="color:#6c757d;font-style:italic;margin-left:12px;">No agentic steps recorded.</div>'
                )
                continue
            parts.append('<ul style="margin:6px 0 10px 20px;">')
            for step in steps:
                status = step.status.value
                color = status_colors.get(status, "#6c757d")
                action = self._escape_html(step.action)
                desc = self._escape_html(step.description)
                item = (
                    "<li>"
                    f'<span style="display:inline-block;min-width:64px;color:{color};font-weight:600;">'
                    f"{status.upper()}</span> "
                    f"{action} - {desc}"
                )
                if step.screenshot_path:
                    filename = self._ensure_screenshot_in_output(step.screenshot_path)
                    if filename:
                        item += f'<div style="margin:6px 0 0 28px;">{self._build_screenshot_html(filename)}</div>'
                item += "</li>"
                parts.append(item)
            parts.append("</ul>")

        if unassigned:
            parts.append('<div style="margin:8px 0 4px 0;"><b>Unassigned Steps</b></div>')
            parts.append('<ul style="margin:6px 0 10px 20px;">')
            for step in unassigned:
                status = step.status.value
                color = status_colors.get(status, "#6c757d")
                action = self._escape_html(step.action)
                desc = self._escape_html(step.description)
                parts.append(
                    "<li>"
                    f'<span style="display:inline-block;min-width:64px;color:{color};font-weight:600;">'
                    f"{status.upper()}</span> "
                    f"{action} - {desc}"
                    "</li>"
                )
            parts.append("</ul>")

        parts.append("</div>")
        rf_logger.info("".join(parts), html=True)

    def _finalize_session(self, session, error: Exception = None):
        """Finalize session status and publish RF log summaries."""
        validation_error = self._validate_ui_action_coverage(session)
        if error:
            session.errors.append(str(error))
        if validation_error:
            session.errors.append(validation_error)
            rf_logger.error(validation_error)

        if error or validation_error:
            session.finalize(SessionStatus.FAILED)
        else:
            session.finalize()
        self._log_high_level_summary(session)
        self._log_basic_summary(session)

    @keyword("Agentic High Level Step")
    def agentic_high_level_step(self, step_number: str, step_description: str = "") -> str:
        """Log a high-level step marker into RF logs."""
        safe_desc = self._escape_html(step_description).replace("\n", "<br/>")
        html_block = (
            '<div style="font-family:Segoe UI,Arial,sans-serif;'
            'background:#eef4ff;padding:8px 10px;border-radius:6px;'
            'border:1px solid #d6e4ff;margin:6px 0;">'
            f"<b>High-Level Step {step_number}</b><br/>"
            f"{safe_desc}"
            "</div>"
        )
        rf_logger.info(html_block, html=True)
        return f"High-Level Step {step_number}: {step_description}"

    @keyword("Agentic Step")
    def agentic_step(
        self,
        action: str,
        description: str,
        status: str = "PASS",
        duration_ms: str = "",
        assertion_message: str = "",
        error_message: str = "",
        screenshot_path: str = "",
        high_level_step_number: str = "",
        high_level_step_description: str = "",
    ) -> str:
        """Log a single agentic step as a keyword in RF logs.

        This keyword is invoked by the agentic runtime to surface step
        details in the standard Robot Framework log.html report.
        """
        status_upper = str(status).strip().upper()
        duration_label = f"{duration_ms}ms" if duration_ms else ""

        safe_action = self._escape_html(action)
        safe_description = self._escape_html(description)
        safe_assertion = self._escape_html(assertion_message) if assertion_message else ""
        safe_error = self._escape_html(error_message) if error_message else ""

        lines = [
            f"<b>Action:</b> {safe_action}",
            f"<b>Description:</b> {safe_description}",
            f"<b>Status:</b> {status_upper}",
        ]
        if high_level_step_number or high_level_step_description:
            safe_hl = self._escape_html(high_level_step_description).replace("\n", "<br/>")
            prefix = f"{high_level_step_number}. " if high_level_step_number else ""
            lines.append(f"<b>High-Level Step:</b> {prefix}{safe_hl}")
        if duration_label:
            lines.append(f"<b>Duration:</b> {duration_label}")
        if assertion_message:
            lines.append(f"<b>Assertion:</b> {safe_assertion}")
        if error_message:
            lines.append(f"<b>Error:</b> {safe_error}")
        if screenshot_path:
            filename = self._ensure_screenshot_in_output(screenshot_path)
            if filename:
                lines.append(f'<b>Screenshot:</b> <a href="{filename}">{filename}</a>')
                lines.append(self._build_screenshot_html(filename))

        rf_logger.info("<br/>".join(lines), html=True)

        if status_upper in ("FAIL", "FAILED", "ERROR"):
            failure_detail = error_message or assertion_message or f"{action}: {description}"
            raise AssertionError(failure_detail)

        return f"{action} - {description} ({status_upper})"

    @keyword
    def run_agentic_test(
        self,
        test_objective: str,
        app_context: str = "",
        max_iterations: int = None,
        test_mode: str = None,
        test_steps: str = None,
        scroll_into_view: bool = True,
    ) -> str:
        """Runs an autonomous AI agentic test based on the given objective.

        The AI agent will autonomously design test scenarios, execute test
        steps, capture evidence, and generate a structured test report.

        Args:
            test_objective: Natural language description of what to test
                (e.g., "Test the login functionality including valid and invalid credentials").
            app_context: Description of the application under test
                (e.g., "E-commerce web application with email/password login").
            max_iterations: Override max agent iterations for this run.
            test_mode: Override test mode for this run (web, api, mobile).
            test_steps: Optional user-defined high-level steps (numbered list).
            scroll_into_view: Scroll elements into view before UI interactions.

        Returns:
            Structured test report as a string.

        Examples:
        | ${report}= | Run Agentic Test |
        | ... | test_objective=Test login with valid and invalid credentials |
        | ... | app_context=Web application with email/password login |
        | ... | max_iterations=50 |
        """
        self._ensure_orchestrator()

        objective, high_level_steps, _ = self._extract_user_defined_steps(
            test_objective=test_objective,
            test_steps=test_steps,
        )
        mode = test_mode or self.test_mode
        iters = int(max_iterations) if max_iterations else self.max_iterations
        start_state, reuse_existing_session = self._resolve_start_state_and_reuse(mode)
        scroll_flag = self._coerce_bool(scroll_into_view, default=True)
        app_context = self._merge_app_context(app_context, start_state)
        session = self._start_session(
            objective=objective,
            app_context=app_context,
            test_mode=mode,
            max_iterations=iters,
            high_level_steps=high_level_steps,
            reuse_existing_session=reuse_existing_session,
            start_state_summary=start_state,
            scroll_into_view=scroll_flag,
        )

        rf_logger.info(
            f"Starting agentic test: mode={mode}, max_iterations={iters}",
        )
        rf_logger.info(f"Objective: {objective}")
        rf_logger.info(f"App context: {app_context}")
        if high_level_steps:
            self._log_user_defined_steps(high_level_steps)

        try:
            result = self._orchestrator.run(
                objective=objective,
                app_context=app_context,
                max_iterations=iters,
                test_mode=mode,
            )
            rf_logger.info("Agentic test completed successfully")
            try:
                self._finalize_session(session)
            except Exception as e:
                logger.warning("Failed to finalize session: %s", e)
            return result
        except Exception as e:
            error_msg = f"Agentic test failed: {type(e).__name__}: {e}"
            rf_logger.error(error_msg)
            try:
                self._finalize_session(session, error=e)
            except Exception as finalize_error:
                logger.warning("Failed to finalize session: %s", finalize_error)
            raise AssertionError(error_msg)
        finally:
            set_active_session(None)

    @keyword
    def run_agentic_exploration(
        self,
        app_context: str,
        focus_areas: str = None,
        max_iterations: int = None,
        scroll_into_view: bool = True,
    ) -> str:
        """Runs an autonomous AI exploratory test session.

        The AI agent freely explores the application, discovering
        features, testing edge cases, and reporting findings without
        a predefined test plan.

        Args:
            app_context: Description of the application under test.
            focus_areas: Comma-separated areas to focus exploration on
                (e.g., "navigation, search, product filtering, cart operations").
            max_iterations: Override max agent iterations for this run.
            scroll_into_view: Scroll elements into view before UI interactions.

        Returns:
            Exploration report as a string.

        Examples:
        | ${report}= | Run Agentic Exploration |
        | ... | app_context=E-commerce platform with catalog and checkout |
        | ... | focus_areas=navigation, search, product filtering |
        | ... | max_iterations=100 |
        """
        self._ensure_orchestrator()

        iters = int(max_iterations) if max_iterations else self.max_iterations
        start_state, reuse_existing_session = self._resolve_start_state_and_reuse(
            self.test_mode
        )
        scroll_flag = self._coerce_bool(scroll_into_view, default=True)
        app_context = self._merge_app_context(app_context, start_state)
        session = self._start_session(
            objective="EXPLORATORY TESTING",
            app_context=app_context,
            test_mode=self.test_mode,
            max_iterations=iters,
            reuse_existing_session=reuse_existing_session,
            start_state_summary=start_state,
            scroll_into_view=scroll_flag,
        )

        rf_logger.info(f"Starting exploratory test: focus={focus_areas}")
        rf_logger.info(f"App context: {app_context}")

        try:
            result = self._orchestrator.run_exploration(
                app_context=app_context,
                focus_areas=focus_areas,
                max_iterations=iters,
            )
            rf_logger.info("Exploratory test completed successfully")
            try:
                self._finalize_session(session)
            except Exception as e:
                logger.warning("Failed to finalize session: %s", e)
            return result
        except Exception as e:
            error_msg = f"Exploratory test failed: {type(e).__name__}: {e}"
            rf_logger.error(error_msg)
            try:
                self._finalize_session(session, error=e)
            except Exception as finalize_error:
                logger.warning("Failed to finalize session: %s", finalize_error)
            raise AssertionError(error_msg)
        finally:
            set_active_session(None)

    @keyword
    def run_agentic_api_test(
        self,
        test_objective: str,
        base_url: str = None,
        api_spec_url: str = None,
        max_iterations: int = None,
        test_steps: str = None,
        scroll_into_view: bool = True,
    ) -> str:
        """Runs an autonomous AI agentic API test.

        Specialized keyword for REST API testing. The AI agent will
        test API endpoints based on the objective, optionally using
        an OpenAPI specification for endpoint discovery.

        Args:
            test_objective: Natural language description of what API functionality to test.
            base_url: API base URL (used as context for the agent).
            api_spec_url: Optional URL to OpenAPI/Swagger specification.
            max_iterations: Override max agent iterations for this run.
            test_steps: Optional user-defined high-level steps (numbered list).
            scroll_into_view: Scroll elements into view before UI interactions.

        Returns:
            API test report as a string.

        Examples:
        | ${report}= | Run Agentic API Test |
        | ... | test_objective=Test user management CRUD operations |
        | ... | base_url=https://api.example.com |
        | ... | api_spec_url=https://api.example.com/openapi.json |
        """
        self._ensure_orchestrator()

        objective, high_level_steps, _ = self._extract_user_defined_steps(
            test_objective=test_objective,
            test_steps=test_steps,
        )
        iters = int(max_iterations) if max_iterations else self.max_iterations

        # Build app context from API details
        app_context = "REST API"
        if base_url:
            app_context += f" at {base_url}"
        if api_spec_url:
            app_context += f" (OpenAPI spec: {api_spec_url})"

        scroll_flag = self._coerce_bool(scroll_into_view, default=True)
        session = self._start_session(
            objective=objective,
            app_context=app_context,
            test_mode="api",
            max_iterations=iters,
            high_level_steps=high_level_steps,
            scroll_into_view=scroll_flag,
        )

        rf_logger.info(f"Starting agentic API test: {app_context}")
        if high_level_steps:
            self._log_user_defined_steps(high_level_steps)

        try:
            result = self._orchestrator.run(
                objective=objective,
                app_context=app_context,
                max_iterations=iters,
                test_mode="api",
            )
            rf_logger.info("Agentic API test completed successfully")
            try:
                self._finalize_session(session)
            except Exception as e:
                logger.warning("Failed to finalize session: %s", e)
            return result
        except Exception as e:
            error_msg = f"Agentic API test failed: {type(e).__name__}: {e}"
            rf_logger.error(error_msg)
            try:
                self._finalize_session(session, error=e)
            except Exception as finalize_error:
                logger.warning("Failed to finalize session: %s", finalize_error)
            raise AssertionError(error_msg)
        finally:
            set_active_session(None)

    @keyword
    def run_agentic_mobile_test(
        self,
        test_objective: str,
        app_context: str = "",
        max_iterations: int = None,
        test_steps: str = None,
        scroll_into_view: bool = True,
    ) -> str:
        """Runs an autonomous AI agentic mobile app test.

        Specialized keyword for mobile application testing using Appium.

        Args:
            test_objective: Natural language description of what to test.
            app_context: Description of the mobile app under test.
            max_iterations: Override max agent iterations for this run.
            test_steps: Optional user-defined high-level steps (numbered list).
            scroll_into_view: Scroll elements into view before UI interactions.

        Returns:
            Mobile test report as a string.

        Examples:
        | ${report}= | Run Agentic Mobile Test |
        | ... | test_objective=Test onboarding flow and main navigation |
        | ... | app_context=Android banking application |
        """
        self._ensure_orchestrator()

        objective, high_level_steps, _ = self._extract_user_defined_steps(
            test_objective=test_objective,
            test_steps=test_steps,
        )
        iters = int(max_iterations) if max_iterations else self.max_iterations

        rf_logger.info("Starting agentic mobile test")

        start_state, reuse_existing_session = self._resolve_start_state_and_reuse(
            "mobile"
        )
        scroll_flag = self._coerce_bool(scroll_into_view, default=True)
        app_context = self._merge_app_context(app_context, start_state)
        session = self._start_session(
            objective=objective,
            app_context=app_context,
            test_mode="mobile",
            max_iterations=iters,
            high_level_steps=high_level_steps,
            reuse_existing_session=reuse_existing_session,
            start_state_summary=start_state,
            scroll_into_view=scroll_flag,
        )
        if high_level_steps:
            self._log_user_defined_steps(high_level_steps)

        try:
            result = self._orchestrator.run(
                objective=objective,
                app_context=app_context,
                max_iterations=iters,
                test_mode="mobile",
            )
            rf_logger.info("Agentic mobile test completed successfully")
            try:
                self._finalize_session(session)
            except Exception as e:
                logger.warning("Failed to finalize session: %s", e)
            return result
        except Exception as e:
            error_msg = f"Agentic mobile test failed: {type(e).__name__}: {e}"
            rf_logger.error(error_msg)
            try:
                self._finalize_session(session, error=e)
            except Exception as finalize_error:
                logger.warning("Failed to finalize session: %s", finalize_error)
            raise AssertionError(error_msg)
        finally:
            set_active_session(None)

    @keyword
    def get_agentic_platform_info(self) -> str:
        """Returns information about the configured AI platform.

        Returns:
            String with platform name, model, and configuration details.

        Examples:
        | ${info}= | Get Agentic Platform Info |
        | Log | ${info} |
        """
        model_name = self.model or self.platform.value["default_model"]
        base = self.base_url or self.platform.value["default_base_url"]
        return (
            f"Platform: {self.platform.name}\n"
            f"Model: {model_name}\n"
            f"Base URL: {base}\n"
            f"Test Mode: {self.test_mode}\n"
            f"Max Iterations: {self.max_iterations}\n"
            f"Verbose: {self.verbose}"
        )
