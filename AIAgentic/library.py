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

import hashlib
import html
import logging
import mimetypes
import os
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from robot.api import logger as rf_logger
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .executor import (
    SafetyGuard,
    SessionStatus,
    StepStatus,
    create_session,
    set_active_session,
)
from .genai import GenAIProvider
from .orchestrator import AgentOrchestrator
from .platforms import Platforms

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

    _SCREENSHOT_SUBDIR = "agentic-screenshots"
    _INLINE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}

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
        try:
            self.platform = Platforms[platform]
        except KeyError:
            valid = ", ".join(p.name for p in Platforms)
            raise ValueError(f"Unknown platform '{platform}'. Valid options: {valid}")

        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_iterations = int(max_iterations)
        self.test_mode = test_mode
        self.headless = headless
        self.screenshot_on_action = screenshot_on_action
        self.verbose = verbose
        self.report_formats = []
        self.timeout_seconds = float(timeout_seconds)
        self.max_cost_usd = float(max_cost_usd) if max_cost_usd else None
        self.selenium_library = selenium_library
        self.requests_library = requests_library
        self.appium_library = appium_library

        self._orchestrator = None
        self._genai_provider = None
        self._safety_guard = None
        self._available_libraries = {}
        self._available_library_keys = set()
        self._screenshot_artifact_cache = {}

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

        if self._orchestrator is None or available_keys != self._available_library_keys:
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
        except Exception as exc:
            logger.debug("Unable to read browser ids: %s", exc)
            return "Start State: No active browser session detected. Start from scratch."

        if not browser_ids:
            return "Start State: No active browser session detected. Start from scratch."

        url = None
        title = None
        try:
            url = sl.get_location()
        except Exception as exc:
            logger.debug("Unable to read current URL: %s", exc)
        try:
            title = sl.get_title()
        except Exception as exc:
            logger.debug("Unable to read page title: %s", exc)

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
        except Exception as exc:
            logger.debug("Unable to read current Appium application: %s", exc)
            return "Start State: No active mobile session detected. Start from scratch."

        lines = ["Start State: Active mobile session detected."]

        try:
            open_apps = al._cache.get_open_browsers()
            lines.append(f"Open applications: {len(open_apps)}")
        except Exception as exc:
            logger.debug("Unable to read open Appium applications: %s", exc)

        session_id = getattr(driver, "session_id", None)
        if session_id:
            lines.append(f"Session ID: {session_id}")

        context = None
        try:
            context = getattr(driver, "current_context", None)
            if callable(context):
                context = context()
        except Exception as exc:
            logger.debug("Unable to read current context: %s", exc)
        if context:
            lines.append(f"Current context: {context}")

        activity = None
        try:
            activity = getattr(driver, "current_activity", None)
            if callable(activity):
                activity = activity()
        except Exception as exc:
            logger.debug("Unable to read current activity: %s", exc)
        if activity:
            lines.append(f"Current activity: {activity}")

        package = None
        try:
            package = getattr(driver, "current_package", None)
            if callable(package):
                package = package()
        except Exception as exc:
            logger.debug("Unable to read current package: %s", exc)
        if package:
            lines.append(f"Current package: {package}")

        caps = getattr(driver, "capabilities", None) or getattr(driver, "desired_capabilities", None)
        if isinstance(caps, dict):
            platform = self._first_capability(caps, "platformName", "appium:platformName", "platform")
            platform_version = self._first_capability(caps, "platformVersion", "appium:platformVersion")
            device = self._first_capability(caps, "deviceName", "appium:deviceName")
            automation = self._first_capability(caps, "automationName", "appium:automationName")
            app = self._first_capability(caps, "app", "appium:app", "appPath")
            app_package = self._first_capability(caps, "appPackage", "appium:appPackage")
            app_activity = self._first_capability(caps, "appActivity", "appium:appActivity")
            bundle_id = self._first_capability(caps, "bundleId", "appium:bundleId")
            udid = self._first_capability(caps, "udid", "appium:udid")
            browser_name = self._first_capability(caps, "browserName", "appium:browserName")

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
        mode = (test_mode or "").strip().lower()
        if mode == "web":
            return self._build_web_start_state()
        if mode == "mobile":
            return self._build_mobile_start_state()
        return ""

    @staticmethod
    def _has_active_start_state(start_state: str) -> bool:
        if not start_state:
            return False
        lowered = start_state.lower()
        if "active browser session detected" in lowered:
            return "no active browser session detected" not in lowered
        if "active mobile session detected" in lowered:
            return "no active mobile session detected" not in lowered
        return False

    def _resolve_start_state_and_reuse(self, test_mode: str) -> tuple[str, bool]:
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
        if not start_state:
            return app_context
        if app_context:
            return f"{app_context}\n\n{start_state}"
        return start_state

    def _resolve_selenium_library_name(self) -> str:
        try:
            override = BuiltIn().get_variable_value("${AIAGENTIC_SELENIUM_LIBRARY}")
            if override:
                return str(override)
        except (RuntimeError, RobotNotRunningError):
            pass
        return self.selenium_library or "SeleniumLibrary"

    def _resolve_appium_library_name(self) -> str:
        try:
            override = BuiltIn().get_variable_value("${AIAGENTIC_APPIUM_LIBRARY}")
            if override:
                return str(override)
        except (RuntimeError, RobotNotRunningError):
            pass
        return self.appium_library or "AppiumLibrary"

    def _assert_active_web_session(self) -> None:
        lib_name = self._resolve_selenium_library_name()
        sl = self._get_library_instance(lib_name)
        if not sl:
            raise AssertionError(
                f"SeleniumLibrary instance '{lib_name}' not found. "
                "Ensure SeleniumLibrary is imported and that AIAgentic is "
                "configured with the correct selenium_library alias."
            )
        try:
            browser_ids = sl.get_browser_ids()
        except Exception as exc:
            raise AssertionError(
                f"Unable to access Selenium browser session from '{lib_name}': {exc}. "
                "Ensure the browser was opened by the same SeleniumLibrary instance."
            ) from exc
        if not browser_ids:
            raise AssertionError(
                "Reuse of an existing browser session is required, but the "
                f"SeleniumLibrary instance '{lib_name}' has no active browsers. "
                "Open the browser with the same SeleniumLibrary instance or set "
                "selenium_library to the correct alias."
            )
        try:
            sl.get_location()
        except Exception as exc:
            raise AssertionError(f"Active Selenium session in '{lib_name}' is not reachable: {exc}.") from exc

    def _assert_active_mobile_session(self) -> None:
        lib_name = self._resolve_appium_library_name()
        al = self._get_library_instance(lib_name)
        if not al:
            raise AssertionError(
                f"AppiumLibrary instance '{lib_name}' not found. "
                "Ensure AppiumLibrary is imported and that AIAgentic is "
                "configured with the correct appium_library alias."
            )
        try:
            al._current_application()
        except Exception as exc:
            raise AssertionError(
                f"Unable to access Appium session from '{lib_name}': {exc}. "
                "Ensure the app was opened by the same AppiumLibrary instance."
            ) from exc

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
            return "No UI interaction actions were recorded for the following steps:\n" + "\n".join(missing)
        return None

    def _validate_user_step_completion(self, session) -> Optional[str]:
        if not session.high_level_steps:
            return None
        groups = {i + 1: [] for i in range(len(session.high_level_steps))}
        for step in session.steps:
            num = step.high_level_step_number
            if num in groups:
                groups[num].append(step)

        missing = []
        not_passed = []
        for idx, step_text in enumerate(session.high_level_steps, start=1):
            steps = groups.get(idx, [])
            if not steps:
                missing.append(f"{idx}. {step_text}")
                continue
            has_pass = any(s.status == StepStatus.PASSED for s in steps)
            if not has_pass:
                not_passed.append(f"{idx}. {step_text}")

        if missing or not_passed:
            parts = ["User-defined steps were not completed successfully."]
            if missing:
                parts.append("No recorded actions for:")
                parts.extend(missing)
            if not_passed:
                parts.append("No passed actions for:")
                parts.extend(not_passed)
            return "\n".join(parts)
        return None

    @staticmethod
    def _detect_failure_in_result(result: Optional[str]) -> Optional[str]:
        if not result:
            return None
        text = str(result)
        lower = text.lower()
        if "**failed**" in lower:
            return text.strip()
        if "failed status" in lower or "status: failed" in lower or "status failed" in lower:
            return text.strip()
        if "completed with failed" in lower:
            return text.strip()
        if re.search(r"\b(test|execution)\b.*\bfailed\b", lower):
            return text.strip()
        return None

    @staticmethod
    def _parse_numbered_steps(text: str) -> List[str]:
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
                items = [str(item) for item in value]
                if any(re.match(r"^\s*\d+[\.\)]\s+", item) for item in items):
                    return "\n".join(items)
                return "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(items))
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
                formatted = "\n".join(f"{idx + 1}. {step}" for idx, step in enumerate(steps))
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
            f'<ol style="margin:6px 0 0 18px;">{"".join(items)}</ol>'
            "</div>"
        )
        self._log_html_message(html_block)

    def _get_output_dir(self) -> str:
        try:
            output_dir = BuiltIn().get_variable_value("${OUTPUT_DIR}")
        except (RuntimeError, RobotNotRunningError):
            output_dir = None
        output_dir = output_dir or os.getcwd()
        os.makedirs(output_dir, exist_ok=True)
        return os.path.abspath(output_dir)

    def _get_report_file(self) -> Optional[str]:
        try:
            report_file = BuiltIn().get_variable_value("${REPORT FILE}")
        except (RuntimeError, RobotNotRunningError):
            report_file = None
        return str(report_file) if report_file else None

    def _get_log_file(self) -> Optional[str]:
        try:
            log_file = BuiltIn().get_variable_value("${LOG FILE}")
        except (RuntimeError, RobotNotRunningError):
            log_file = None
        return str(log_file) if log_file else None

    @staticmethod
    def _normalize_fs_path(path_value: str) -> str:
        return os.path.abspath(os.path.expanduser(os.path.expandvars(str(path_value).strip())))

    @staticmethod
    def _sanitize_filename_component(value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value or "")
        sanitized = sanitized.strip("-._")
        return sanitized or "screenshot"

    def _make_screenshot_target_name(self, source_path: str) -> str:
        source = Path(source_path)
        stem = self._sanitize_filename_component(source.stem)
        suffix = source.suffix.lower() or ".png"
        digest = hashlib.sha1(source_path.encode("utf-8", errors="ignore")).hexdigest()[:10]
        return f"{stem}-{digest}{suffix}"

    def _is_image_file(self, path_value: str) -> bool:
        suffix = Path(path_value).suffix.lower()
        if suffix in self._INLINE_IMAGE_EXTENSIONS:
            return True
        mime, _ = mimetypes.guess_type(path_value)
        return bool(mime and mime.startswith("image/"))

    def _build_artifact_relpath(self, filename: str) -> str:
        return f"{self._SCREENSHOT_SUBDIR}/{filename}".replace(os.sep, "/")

    def _quote_url_path(self, relpath: str) -> str:
        return urllib.parse.quote(relpath.replace(os.sep, "/"), safe="/-_.~")

    def _prepare_screenshot_artifact(self, screenshot_path: str) -> Optional[Dict[str, str]]:
        if not screenshot_path:
            return None

        source_path = self._normalize_fs_path(screenshot_path)
        if not os.path.exists(source_path):
            logger.warning("Screenshot path does not exist: %s", source_path)
            return None

        output_dir = self._get_output_dir()
        artifact_dir = os.path.join(output_dir, self._SCREENSHOT_SUBDIR)
        os.makedirs(artifact_dir, exist_ok=True)

        target_name = self._make_screenshot_target_name(source_path)
        target_path = os.path.join(artifact_dir, target_name)
        try:
            source_stat = os.stat(source_path)
        except OSError as exc:
            logger.warning("Unable to stat screenshot '%s': %s", source_path, exc)
            return None

        cache_key = (
            os.path.realpath(source_path),
            os.path.realpath(target_path),
            int(source_stat.st_mtime_ns),
            int(source_stat.st_size),
        )
        cached_artifact = self._screenshot_artifact_cache.get(cache_key)
        if cached_artifact and os.path.exists(cached_artifact["target_path"]):
            return cached_artifact

        try:
            source_real = os.path.realpath(source_path)
            target_real = os.path.realpath(target_path)
            if source_real != target_real:
                if not os.path.exists(target_path):
                    shutil.copy2(source_path, target_path)
                else:
                    target_stat = os.stat(target_path)
                    if (
                        int(target_stat.st_mtime_ns) < int(source_stat.st_mtime_ns)
                        or int(target_stat.st_size) != int(source_stat.st_size)
                    ):
                        shutil.copy2(source_path, target_path)
        except Exception as exc:
            logger.warning("Unable to copy screenshot '%s' to '%s': %s", source_path, target_path, exc)
            return None

        relpath = self._build_artifact_relpath(target_name)
        artifact = {
            "source_path": source_path,
            "target_path": target_path,
            "filename": target_name,
            "relpath": relpath,
            "url": self._quote_url_path(relpath),
            "is_image": str(self._is_image_file(target_path)).lower(),
        }
        self._screenshot_artifact_cache[cache_key] = artifact
        return artifact

    def _build_screenshot_html(self, artifact: Dict[str, str]) -> str:
        if not artifact:
            return ""

        url = artifact["url"]
        label = self._escape_html(artifact["filename"])
        if artifact.get("is_image") == "true":
            return (
                '<div style="margin-top:8px">'
                f'<div><a href="{url}">{label}</a></div>'
                f'<a href="{url}">'
                f'<img src="{url}" style="margin-top:6px;max-width:100%;width:900px;'
                'border:1px solid #dfe3e8;border-radius:4px;">'
                "</a>"
                "</div>"
            )
        return f'<div style="margin-top:8px"><a href="{url}">{label}</a></div>'

    def _build_screenshot_notice_html(self) -> str:
        log_file = self._get_log_file() or "log.html"
        report_file = self._get_report_file() or "report.html"
        return (
            '<div style="margin-top:8px;color:#5f6b7a;font-size:12px;">'
            f'Embedded step screenshots are rendered in <b>{self._escape_html(log_file)}</b>. '
            f'<b>{self._escape_html(report_file)}</b> is only a summary view and does not show full keyword HTML content.'
            "</div>"
        )

    def _log_html_message(self, html_block: str) -> None:
        """Log HTML content even if log level is temporarily NONE."""
        try:
            bi = BuiltIn()
            old_level = bi.set_log_level("INFO")
            bi.log(html_block, level="INFO", html=True)
            bi.set_log_level(old_level)
        except RobotNotRunningError:
            rf_logger.info(html_block, html=True)
        except Exception as exc:
            logger.debug("Unable to log HTML message: %s", exc)

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
            self._log_html_message(html_summary)
        except Exception as exc:
            logger.debug("Unable to log session summary: %s", exc)

    def _log_high_level_summary(self, session):
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
            parts.append(f'<div style="margin:8px 0 4px 0;"><b>Step {idx}:</b> {safe_title}</div>')
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
                if getattr(step, "screenshot_path", ""):
                    artifact = self._prepare_screenshot_artifact(step.screenshot_path)
                    if artifact:
                        item += f'<div style="margin:6px 0 0 28px;">{self._build_screenshot_html(artifact)}</div>'
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
        self._log_html_message("".join(parts))

    def _finalize_session(self, session, error: Exception = None):
        validation_error = self._validate_ui_action_coverage(session)
        completion_error = self._validate_user_step_completion(session)
        if error:
            session.errors.append(str(error))
        if validation_error:
            session.errors.append(validation_error)
            rf_logger.error(validation_error)
        if completion_error:
            session.errors.append(completion_error)
            rf_logger.error(completion_error)

        if error or validation_error or completion_error:
            session.finalize(SessionStatus.FAILED)
        else:
            session.finalize()
        self._log_high_level_summary(session)
        self._log_basic_summary(session)

    @keyword("Agentic High Level Step")
    def agentic_high_level_step(self, step_number: str, step_description: str = "") -> str:
        safe_desc = self._escape_html(step_description).replace("\n", "<br/>")
        html_block = (
            '<div style="font-family:Segoe UI,Arial,sans-serif;'
            'background:#eef4ff;padding:8px 10px;border-radius:6px;'
            'border:1px solid #d6e4ff;margin:6px 0;">'
            f"<b>High-Level Step {step_number}</b><br/>"
            f"{safe_desc}"
            "</div>"
        )
        self._log_html_message(html_block)
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

        Notes:
            - Embedded screenshot preview is available in Robot Framework log.html.
            - report.html is only a summary page and does not render full keyword HTML blocks.
            - Robot Framework will still display the original keyword arguments, including
              the raw screenshot_path passed by the caller. That is a framework UI behavior.
        """
        # Backward compatibility for legacy runtime callers that passed only 7 positional
        # arguments in this order:
        #   action, description, status, duration_ms, screenshot_path,
        #   high_level_step_number, high_level_step_description
        # Those old calls land here as:
        #   assertion_message=<real screenshot path>
        #   error_message=<real high level step number>
        #   screenshot_path=<real high level step description>
        if (
            assertion_message
            and os.path.exists(str(assertion_message))
            and error_message
            and str(error_message).strip().isdigit()
            and screenshot_path
            and not os.path.exists(str(screenshot_path))
            and not high_level_step_number
            and not high_level_step_description
        ):
            legacy_screenshot_path = assertion_message
            legacy_step_number = str(error_message).strip()
            legacy_step_description = str(screenshot_path)
            screenshot_path = legacy_screenshot_path
            high_level_step_number = legacy_step_number
            high_level_step_description = legacy_step_description
            assertion_message = ""
            error_message = ""

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

        artifact = None
        if screenshot_path:
            artifact = self._prepare_screenshot_artifact(screenshot_path)
            if artifact:
                lines.append(f'<b>Screenshot:</b> <a href="{artifact["url"]}">{self._escape_html(artifact["relpath"])}</a>')
                lines.append(self._build_screenshot_html(artifact))
                lines.append(self._build_screenshot_notice_html())
            else:
                lines.append(
                    f"<b>Screenshot:</b> Screenshot file was not available for embedding: "
                    f"{self._escape_html(os.path.basename(str(screenshot_path)))}"
                )

        self._log_html_message("<br/>".join(lines))

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

        rf_logger.info(f"Starting agentic test: mode={mode}, max_iterations={iters}")
        rf_logger.info(f"Objective: {objective}")
        rf_logger.info(f"App context: {app_context}")
        if high_level_steps:
            self._log_user_defined_steps(high_level_steps)
        error = None
        error_msg = None
        result = None
        try:
            if mode == "web" and reuse_existing_session:
                self._assert_active_web_session()
            if mode == "mobile" and reuse_existing_session:
                self._assert_active_mobile_session()
            result = self._orchestrator.run(
                objective=objective,
                app_context=app_context,
                max_iterations=iters,
                test_mode=mode,
                high_level_steps=high_level_steps,
            )
            failure_detail = self._detect_failure_in_result(result)
            if failure_detail:
                error = AssertionError(failure_detail)
                error_msg = f"Agentic report indicated failure: {failure_detail}"
                rf_logger.error(error_msg)
            else:
                rf_logger.info("Agentic test completed successfully")
        except Exception as exc:
            error = exc
            error_msg = f"Agentic test failed: {type(exc).__name__}: {exc}"
            rf_logger.error(error_msg)
        finally:
            try:
                self._finalize_session(session, error=error)
            except Exception as finalize_error:
                logger.warning("Failed to finalize session: %s", finalize_error)
            set_active_session(None)

        if error:
            raise AssertionError(error_msg)
        if session.status == SessionStatus.FAILED:
            failure_detail = session.errors[-1] if session.errors else "Agentic test failed"
            raise AssertionError(failure_detail)
        return result

    @keyword
    def run_agentic_exploration(
        self,
        app_context: str,
        focus_areas: str = None,
        max_iterations: int = None,
        scroll_into_view: bool = True,
    ) -> str:
        self._ensure_orchestrator()

        iters = int(max_iterations) if max_iterations else self.max_iterations
        start_state, reuse_existing_session = self._resolve_start_state_and_reuse(self.test_mode)
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

        error = None
        error_msg = None
        result = None
        try:
            if self.test_mode == "web" and reuse_existing_session:
                self._assert_active_web_session()
            if self.test_mode == "mobile" and reuse_existing_session:
                self._assert_active_mobile_session()
            result = self._orchestrator.run_exploration(
                app_context=app_context,
                focus_areas=focus_areas,
                max_iterations=iters,
                test_mode=self.test_mode,
            )
            failure_detail = self._detect_failure_in_result(result)
            if failure_detail:
                error = AssertionError(failure_detail)
                error_msg = f"Exploratory report indicated failure: {failure_detail}"
                rf_logger.error(error_msg)
            else:
                rf_logger.info("Exploratory test completed successfully")
        except Exception as exc:
            error = exc
            error_msg = f"Exploratory test failed: {type(exc).__name__}: {exc}"
            rf_logger.error(error_msg)
        finally:
            try:
                self._finalize_session(session, error=error)
            except Exception as finalize_error:
                logger.warning("Failed to finalize session: %s", finalize_error)
            set_active_session(None)

        if error:
            raise AssertionError(error_msg)
        if session.status == SessionStatus.FAILED:
            failure_detail = session.errors[-1] if session.errors else "Exploratory test failed"
            raise AssertionError(failure_detail)
        return result

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
        self._ensure_orchestrator()

        objective, high_level_steps, _ = self._extract_user_defined_steps(
            test_objective=test_objective,
            test_steps=test_steps,
        )
        iters = int(max_iterations) if max_iterations else self.max_iterations

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

        error = None
        error_msg = None
        result = None
        try:
            result = self._orchestrator.run(
                objective=objective,
                app_context=app_context,
                max_iterations=iters,
                test_mode="api",
                high_level_steps=high_level_steps,
            )
            failure_detail = self._detect_failure_in_result(result)
            if failure_detail:
                error = AssertionError(failure_detail)
                error_msg = f"Agentic API report indicated failure: {failure_detail}"
                rf_logger.error(error_msg)
            else:
                rf_logger.info("Agentic API test completed successfully")
        except Exception as exc:
            error = exc
            error_msg = f"Agentic API test failed: {type(exc).__name__}: {exc}"
            rf_logger.error(error_msg)
        finally:
            try:
                self._finalize_session(session, error=error)
            except Exception as finalize_error:
                logger.warning("Failed to finalize session: %s", finalize_error)
            set_active_session(None)

        if error:
            raise AssertionError(error_msg)
        if session.status == SessionStatus.FAILED:
            failure_detail = session.errors[-1] if session.errors else "Agentic API test failed"
            raise AssertionError(failure_detail)
        return result

    @keyword
    def run_agentic_mobile_test(
        self,
        test_objective: str,
        app_context: str = "",
        max_iterations: int = None,
        test_steps: str = None,
        scroll_into_view: bool = True,
    ) -> str:
        self._ensure_orchestrator()

        objective, high_level_steps, _ = self._extract_user_defined_steps(
            test_objective=test_objective,
            test_steps=test_steps,
        )
        iters = int(max_iterations) if max_iterations else self.max_iterations

        rf_logger.info("Starting agentic mobile test")

        start_state, reuse_existing_session = self._resolve_start_state_and_reuse("mobile")
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

        error = None
        error_msg = None
        result = None
        try:
            if reuse_existing_session:
                self._assert_active_mobile_session()
            result = self._orchestrator.run(
                objective=objective,
                app_context=app_context,
                max_iterations=iters,
                test_mode="mobile",
                high_level_steps=high_level_steps,
            )
            failure_detail = self._detect_failure_in_result(result)
            if failure_detail:
                error = AssertionError(failure_detail)
                error_msg = f"Agentic mobile report indicated failure: {failure_detail}"
                rf_logger.error(error_msg)
            else:
                rf_logger.info("Agentic mobile test completed successfully")
        except Exception as exc:
            error = exc
            error_msg = f"Agentic mobile test failed: {type(exc).__name__}: {exc}"
            rf_logger.error(error_msg)
        finally:
            try:
                self._finalize_session(session, error=error)
            except Exception as finalize_error:
                logger.warning("Failed to finalize session: %s", finalize_error)
            set_active_session(None)

        if error:
            raise AssertionError(error_msg)
        if session.status == SessionStatus.FAILED:
            failure_detail = session.errors[-1] if session.errors else "Agentic mobile test failed"
            raise AssertionError(failure_detail)
        return result

    @keyword
    def get_agentic_platform_info(self) -> str:
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
