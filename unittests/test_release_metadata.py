# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Release metadata regression tests."""

from pathlib import Path

from AITester import __version__
from AITester.library import AITester


def test_runtime_versions_match_release_notes():
    changes_path = Path(__file__).resolve().parents[1] / "CHANGES"
    release_version = changes_path.read_text(encoding="utf-8").splitlines()[0].split(",")[0].strip()

    assert __version__ == release_version
    assert AITester.ROBOT_LIBRARY_VERSION == __version__
    assert release_version == __version__
