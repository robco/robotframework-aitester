# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for reporter module."""

import json
import os
import pytest
import tempfile
from AIAgentic.executor import (
    TestSession,
    TestStep,
    SessionStatus,
    StepStatus,
    create_session,
)
from AIAgentic.reporter import TestReporter


def _make_session():
    """Create a test session with sample steps."""
    session = create_session("Test login flow", "Web application", "web", 50)
    session.add_step(TestStep(1, "selenium_open_browser", "Open browser", StepStatus.PASSED, 500))
    session.add_step(TestStep(2, "selenium_click_element", "Click login", StepStatus.PASSED, 150))
    session.add_step(TestStep(3, "selenium_input_text", "Enter username", StepStatus.PASSED, 100))
    session.add_step(TestStep(4, "selenium_input_password", "Enter password", StepStatus.PASSED, 100))
    session.add_step(TestStep(5, "selenium_click_button", "Submit login", StepStatus.PASSED, 200))
    session.add_step(TestStep(6, "selenium_element_should_contain", "Verify welcome",
                              StepStatus.FAILED, 150,
                              error_message="Expected 'Welcome' but got 'Error'"))
    session.finalize()
    return session


class TestTextReport:
    """Tests for text report generation."""

    def test_text_report_contains_summary(self):
        session = _make_session()
        reporter = TestReporter()
        report = reporter.generate_text_report(session)
        assert "AGENTIC TEST REPORT" in report
        assert "Test login flow" in report
        assert "FAILED" in report.upper()

    def test_text_report_shows_steps(self):
        session = _make_session()
        reporter = TestReporter()
        report = reporter.generate_text_report(session)
        assert "Step 1" in report or "selenium_open_browser" in report

    def test_text_report_shows_errors(self):
        session = _make_session()
        reporter = TestReporter()
        report = reporter.generate_text_report(session)
        assert "Welcome" in report or "Error" in report


class TestJsonReport:
    """Tests for JSON report generation."""

    def test_json_report_valid(self):
        session = _make_session()
        reporter = TestReporter()
        report = reporter.generate_json_report(session)
        data = json.loads(report)
        assert data["objective"] == "Test login flow"
        assert data["total_steps"] == 6
        assert data["failed_steps"] == 1

    def test_json_report_has_version(self):
        session = _make_session()
        reporter = TestReporter()
        report = reporter.generate_json_report(session)
        data = json.loads(report)
        assert "report_version" in data


class TestHtmlReport:
    """Tests for HTML report generation."""

    def test_html_report_structure(self):
        session = _make_session()
        reporter = TestReporter()
        html = reporter.generate_html_report(session)
        assert "<!DOCTYPE html>" in html
        assert "Agentic Test Report" in html
        assert session.session_id in html

    def test_html_report_has_steps(self):
        session = _make_session()
        reporter = TestReporter()
        html = reporter.generate_html_report(session)
        assert "selenium_open_browser" in html


class TestJunitReport:
    """Tests for JUnit XML report generation."""

    def test_junit_xml_valid(self):
        session = _make_session()
        reporter = TestReporter()
        xml = reporter.generate_junit_xml(session)
        assert '<?xml version="1.0"' in xml
        assert "<testsuite" in xml
        assert 'tests="6"' in xml
        assert 'failures="1"' in xml

    def test_junit_xml_has_failure(self):
        session = _make_session()
        reporter = TestReporter()
        xml = reporter.generate_junit_xml(session)
        assert "<failure" in xml


class TestSaveReports:
    """Tests for saving reports to disk."""

    def test_save_all_formats(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = TestReporter(output_dir=tmpdir)
            saved = reporter.save_reports(session)
            assert "text" in saved
            assert "json" in saved
            assert "html" in saved
            assert "junit" in saved
            for path in saved.values():
                assert os.path.exists(path)
