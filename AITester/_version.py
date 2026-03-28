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

"""Project version metadata."""

from pathlib import Path

_FALLBACK_VERSION = "0.0.1-dev"


def _read_latest_changes_version():
    """Read the newest release version from CHANGES when available."""
    changes_path = Path(__file__).resolve().parents[1] / "CHANGES"
    try:
        first_line = changes_path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (FileNotFoundError, IndexError, OSError):
        return _FALLBACK_VERSION

    version = first_line.split(",", 1)[0].strip()
    return version or _FALLBACK_VERSION


__version__ = _read_latest_changes_version()
