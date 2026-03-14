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

from setuptools import setup, find_packages


def version():
    with open("CHANGES.txt") as changes:
        return changes.readline().split(",")[0]


def license_text():
    with open("LICENSE") as f:
        return f.readline()


def readme():
    changes_title = "\n\nVersion history\n----------------\n\n"
    formatted_changes = []

    with open("CHANGES.txt", "r") as ch:
        for line in ch:
            stripped_line = line.strip()
            if stripped_line:
                formatted_changes.append(f"- {stripped_line}")

    with open("README.md", "r") as r:
        return r.read() + changes_title + "\n".join(formatted_changes) + "\n"


setup(
    name="robotframework-aiagentic",
    version=version(),
    author="Róbert Malovec",
    author_email="robert@malovec.sk",
    description="AI Agentic Testing library for Robot Framework",
    long_description=readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/robco/robotframework-aiagentic",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "robotframework>=6.0",
        "strands-agents>=0.1.0",
        "strands-agents-tools>=0.1.0",
        "openai>=1.0.0",
        "pillow>=9.0.0",
    ],
    extras_require={
        "web": ["robotframework-seleniumlibrary>=6.0"],
        "api": ["robotframework-requests>=0.9"],
        "mobile": ["robotframework-appiumlibrary>=2.0"],
        "all": [
            "robotframework-seleniumlibrary>=6.0",
            "robotframework-requests>=0.9",
            "robotframework-appiumlibrary>=2.0",
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
    classifiers=[
        "Framework :: Robot Framework",
        "Framework :: Robot Framework :: Library",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
    ],
)
