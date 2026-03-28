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

from pathlib import Path

from setuptools import find_packages, setup

BASE_DIR = Path(__file__).resolve().parent
VERSION_NS = {"__file__": str(BASE_DIR / "AITester" / "_version.py")}
exec((BASE_DIR / "AITester" / "_version.py").read_text(encoding="utf-8"), VERSION_NS)


def read_text(*parts):
    return BASE_DIR.joinpath(*parts).read_text(encoding="utf-8")


def build_long_description():
    changes_title = "\n\nVersion history\n----------------\n\n"
    formatted_changes = []

    for line in read_text("CHANGES").splitlines():
        stripped_line = line.strip()
        if stripped_line:
            formatted_changes.append(f"- {stripped_line}")

    return read_text("README.md") + changes_title + "\n".join(formatted_changes) + "\n"


setup(
    name="robotframework-aitester",
    version=VERSION_NS["__version__"],
    author="Róbert Malovec",
    author_email="robert@malovec.sk",
    description="Autonomous AI testing library for Robot Framework",
    long_description=build_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/robco/robotframework-aitester",
    project_urls={
        "Documentation": "https://robco.github.io/robotframework-aitester/",
        "Source": "https://github.com/robco/robotframework-aitester",
        "Tracker": "https://github.com/robco/robotframework-aitester/issues",
    },
    packages=find_packages(exclude=("unittests", "unittests.*")),
    python_requires=">=3.10",
    license="Apache-2.0",
    include_package_data=True,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: Robot Framework",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Testing",
    ],
    keywords=[
        "robotframework",
        "testing",
        "ai",
        "automation",
        "selenium",
        "appium",
        "api-testing",
    ],
    install_requires=[
        "robotframework>=6.0",
        "strands-agents[ollama,gemini]>=1.29.0",
        "strands-agents-tools>=0.2.0",
        "openai>=2.0.0",
        "pillow>=11.0.0",
    ],
    extras_require={
        "web": ["robotframework-seleniumlibrary>=7.0"],
        "api": ["robotframework-requests>=0.9"],
        "mobile": ["robotframework-appiumlibrary>=3.2.0"],
        "all": [
            "robotframework-seleniumlibrary>=7.0",
            "robotframework-requests>=0.9",
            "robotframework-appiumlibrary>=3.2.0",
        ],
        "openai": ["strands-agents[openai]"],
        "bedrock": ["strands-agents[bedrock]"],
        "anthropic": ["strands-agents[anthropic]"],
        "ollama": ["strands-agents[ollama]"],
        "dev": [
            "pytest>=7.0",
            "pytest-mock>=3.0",
            "flake8",
        ],
    },
)
