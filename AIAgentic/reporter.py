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
Reporting module for robotframework-aiagentic.

Generates structured test results in multiple formats and integrates
with Robot Framework's native logging infrastructure.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from robot.api import logger as rf_logger
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .executor import TestSession, SessionStatus

logger = logging.getLogger(__name__)


def _get_output_dir():
    """Get Robot Framework output directory."""
    try:
        return BuiltIn().get_variable_value("${OUTPUT_DIR}")
    except RobotNotRunningError:
        return os.getcwd()


class TestReporter:
    """Generates and manages test reports for agentic test sessions.

    Supports multiple output formats:
    - Text: Human-readable summary for RF logs
    - JSON: Machine-readable structured data
    - HTML: Rich visual report with embedded screenshots
    - JUnit XML: CI/CD compatible format
    """

    def __init__(self, output_dir: str = None):
        """Initialize the reporter.

        Args:
            output_dir: Directory for report files. Defaults to RF output dir.
        """
        self.output_dir = output_dir or _get_output_dir()

    def generate_text_report(self, session: TestSession) -> str:
        """Generate a human-readable text report.

        Args:
            session: Completed test session.

        Returns:
            Formatted text report string.
        """
        data = session.to_dict()
        lines = [
            "=" * 70,
            "AGENTIC TEST REPORT",
            "=" * 70,
            "",
            f"Session ID:     {data['session_id']}",
            f"Test Mode:      {data['test_mode']}",
            f"Status:         {data['status'].upper()}",
            f"Duration:       {data['duration_seconds']}s",
            f"Iterations:     {data['iterations_used']}/{data['max_iterations']}",
            "",
            f"Objective: {data['objective']}",
            f"App Context: {data['app_context']}",
            "",
            "-" * 70,
            "RESULTS SUMMARY",
            "-" * 70,
            f"  Total Steps:   {data['total_steps']}",
            f"  Passed:        {data['passed_steps']}",
            f"  Failed:        {data['failed_steps']}",
            f"  Pass Rate:     {data['pass_rate']}%",
            "",
        ]

        # Steps detail
        if data["steps"]:
            lines.append("-" * 70)
            lines.append("STEP DETAILS")
            lines.append("-" * 70)
            for step in data["steps"]:
                status_icon = "✓" if step["status"] == "passed" else "✗"
                lines.append(
                    f"  {status_icon} Step {step['step_number']}: "
                    f"{step['action']} - {step['description']}"
                )
                if step.get("assertion_message"):
                    lines.append(f"    Assertion: {step['assertion_message']}")
                if step.get("error_message"):
                    lines.append(f"    Error: {step['error_message']}")
                if step.get("screenshot_path"):
                    lines.append(f"    Screenshot: {step['screenshot_path']}")
            lines.append("")

        # Errors
        if data["errors"]:
            lines.append("-" * 70)
            lines.append("ERRORS")
            lines.append("-" * 70)
            for err in data["errors"]:
                lines.append(f"  - {err}")
            lines.append("")

        # Screenshots
        if data["screenshots"]:
            lines.append("-" * 70)
            lines.append(f"SCREENSHOTS ({len(data['screenshots'])})")
            lines.append("-" * 70)
            for ss in data["screenshots"]:
                lines.append(f"  - {ss}")
            lines.append("")

        lines.append("=" * 70)
        lines.append(f"Report generated: {datetime.now().isoformat()}")
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_json_report(self, session: TestSession) -> str:
        """Generate a JSON report.

        Args:
            session: Completed test session.

        Returns:
            JSON string of the report.
        """
        data = session.to_dict()
        data["report_generated"] = datetime.now().isoformat()
        data["report_version"] = "1.0"
        return json.dumps(data, indent=2)

    def generate_html_report(self, session: TestSession) -> str:
        """Generate an HTML report with embedded styling.

        Args:
            session: Completed test session.

        Returns:
            HTML string of the report.
        """
        data = session.to_dict()
        status_color = "#27ae60" if data["status"] == "completed" else "#e74c3c"

        # Build steps HTML
        steps_html = ""
        for step in data.get("steps", []):
            step_class = "pass" if step["status"] == "passed" else "fail"
            steps_html += f"""
            <tr class="{step_class}">
                <td>{step['step_number']}</td>
                <td>{step['action']}</td>
                <td>{step['description']}</td>
                <td><span class="badge {step_class}">{step['status'].upper()}</span></td>
                <td>{step.get('duration_ms', 0):.0f}ms</td>
            </tr>"""

        # Build screenshots HTML
        screenshots_html = ""
        for ss in data.get("screenshots", []):
            filename = os.path.basename(ss)
            screenshots_html += f'<div class="screenshot"><img src="{filename}" alt="{filename}"><p>{filename}</p></div>'

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agentic Test Report - {data['session_id']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid {status_color}; padding-bottom: 10px; margin-bottom: 20px; }}
        h2 {{ color: #34495e; margin-top: 30px; margin-bottom: 15px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px; margin-bottom: 30px; }}
        .card {{ background: #f8f9fa; border-radius: 8px; padding: 20px; border-left: 4px solid {status_color}; }}
        .card .label {{ font-size: 0.85em; color: #7f8c8d; text-transform: uppercase; }}
        .card .value {{ font-size: 1.5em; font-weight: bold; color: #2c3e50; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #ecf0f1; }}
        th {{ background: #2c3e50; color: white; }}
        tr.pass {{ background: #f0fff0; }}
        tr.fail {{ background: #fff0f0; }}
        .badge {{ padding: 3px 10px; border-radius: 12px; font-size: 0.8em; font-weight: bold; color: white; }}
        .badge.pass {{ background: #27ae60; }}
        .badge.fail {{ background: #e74c3c; }}
        .screenshot {{ display: inline-block; margin: 10px; text-align: center; }}
        .screenshot img {{ max-width: 400px; border: 1px solid #ddd; border-radius: 4px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ecf0f1;
                   color: #7f8c8d; font-size: 0.85em; }}
    </style>
</head>
<body>
    <h1>🤖 Agentic Test Report</h1>

    <div class="summary">
        <div class="card">
            <div class="label">Status</div>
            <div class="value" style="color: {status_color}">{data['status'].upper()}</div>
        </div>
        <div class="card">
            <div class="label">Pass Rate</div>
            <div class="value">{data['pass_rate']}%</div>
        </div>
        <div class="card">
            <div class="label">Steps</div>
            <div class="value">{data['passed_steps']}/{data['total_steps']}</div>
        </div>
        <div class="card">
            <div class="label">Duration</div>
            <div class="value">{data['duration_seconds']}s</div>
        </div>
        <div class="card">
            <div class="label">Iterations</div>
            <div class="value">{data['iterations_used']}/{data['max_iterations']}</div>
        </div>
    </div>

    <h2>Test Objective</h2>
    <p><strong>{data['objective']}</strong></p>
    <p>Application: {data['app_context']} | Mode: {data['test_mode']}</p>

    <h2>Step Details</h2>
    <table>
        <tr><th>#</th><th>Action</th><th>Description</th><th>Status</th><th>Duration</th></tr>
        {steps_html}
    </table>

    {{"<h2>Screenshots</h2>" + screenshots_html if screenshots_html else ""}}

    <div class="footer">
        <p>Session ID: {data['session_id']} | Generated: {{datetime.now().isoformat()}}</p>
        <p>Powered by robotframework-aiagentic v0.1.0</p>
    </div>
</body>
</html>"""
        return html

    def generate_junit_xml(self, session: TestSession) -> str:
        """Generate JUnit XML report for CI/CD integration.

        Args:
            session: Completed test session.

        Returns:
            JUnit XML string.
        """
        data = session.to_dict()
        failures = data["failed_steps"]
        total = data["total_steps"]
        duration = data["duration_seconds"]

        test_cases = ""
        for step in data.get("steps", []):
            classname = f"agentic.{data['test_mode']}.{data['session_id']}"
            name = f"Step_{step['step_number']}_{step['action']}"
            time_s = step.get("duration_ms", 0) / 1000

            if step["status"] == "passed":
                test_cases += f'    <testcase classname="{classname}" name="{name}" time="{time_s:.3f}"/>\n'
            else:
                msg = step.get("error_message") or step.get("assertion_message") or "Test step failed"
                test_cases += (
                    f'    <testcase classname="{classname}" name="{name}" time="{time_s:.3f}">\n'
                    f'      <failure message="{_xml_escape(msg[:200])}">{_xml_escape(msg)}</failure>\n'
                    f"    </testcase>\n"
                )

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="agentic-{data['session_id']}" tests="{total}" failures="{failures}" time="{duration:.3f}">
{test_cases}</testsuite>
"""
        return xml

    def save_reports(self, session: TestSession, formats: list = None) -> Dict[str, str]:
        """Save reports in specified formats to the output directory.

        Args:
            session: Completed test session.
            formats: List of formats to generate. Options: text, json, html, junit.
                     Defaults to all formats.

        Returns:
            Dictionary mapping format name to saved file path.
        """
        formats = formats or ["text", "json", "html", "junit"]
        saved = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"agentic_report_{session.session_id}_{timestamp}"

        for fmt in formats:
            try:
                if fmt == "text":
                    content = self.generate_text_report(session)
                    path = os.path.join(self.output_dir, f"{prefix}.txt")
                    with open(path, "w") as f:
                        f.write(content)
                    saved["text"] = path

                elif fmt == "json":
                    content = self.generate_json_report(session)
                    path = os.path.join(self.output_dir, f"{prefix}.json")
                    with open(path, "w") as f:
                        f.write(content)
                    saved["json"] = path

                elif fmt == "html":
                    content = self.generate_html_report(session)
                    path = os.path.join(self.output_dir, f"{prefix}.html")
                    with open(path, "w") as f:
                        f.write(content)
                    saved["html"] = path

                elif fmt == "junit":
                    content = self.generate_junit_xml(session)
                    path = os.path.join(self.output_dir, f"{prefix}_junit.xml")
                    with open(path, "w") as f:
                        f.write(content)
                    saved["junit"] = path

                logger.info("Saved %s report: %s", fmt, path)
            except Exception as e:
                logger.error("Failed to save %s report: %s", fmt, e)

        return saved

    def log_to_rf(self, session: TestSession):
        """Log the session results to Robot Framework's built-in logger.

        Args:
            session: Completed test session.
        """
        try:
            report = self.generate_text_report(session)
            rf_logger.info(report)

            # Also log as HTML for rich RF log integration
            html_summary = (
                f'<div style="font-family:monospace;background:#f8f9fa;padding:10px;border-radius:4px;">'
                f"<b>Agentic Test Report</b><br/>"
                f"Status: <b>{session.status.value.upper()}</b><br/>"
                f"Steps: {session.passed_steps}/{session.total_steps} passed<br/>"
                f"Duration: {session.duration_seconds:.1f}s<br/>"
                f"</div>"
            )
            rf_logger.info(html_summary, html=True)
        except Exception as e:
            logger.warning("Could not log to RF: %s", e)


class AIAgenticListener:
    """Robot Framework listener (v3 API) for real-time agentic test reporting.

    When enabled, publishes agent actions as they occur, allowing external
    tools to monitor agentic test execution in progress.
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self):
        self.current_session = None
        self._active = False

    def start_test(self, data, result):
        """Called when a test case starts."""
        self._active = True
        logger.debug("Listener: Test started: %s", data.name)

    def log_message(self, message):
        """Called when a log message is generated."""
        if self._active and "[AGENTIC]" in str(message.message):
            self._publish_action(message)

    def end_test(self, data, result):
        """Called when a test case ends."""
        self._active = False
        logger.debug("Listener: Test ended: %s - %s", data.name, result.status)

    def _publish_action(self, message):
        """Process and publish an agentic action log entry."""
        logger.debug("Agentic action: %s", message.message[:200])


def _xml_escape(text):
    """Escape special XML characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
