#!/usr/bin/env python3
"""Setup script for the Meeting Notes Handler."""

from setuptools import setup, find_packages
from pathlib import Path
import re

# Read the contents of README file
this_directory = Path(__file__).parent
long_description = ""
readme_file = this_directory / "README.md"
if readme_file.exists():
    long_description = readme_file.read_text(encoding='utf-8')

# Read version from __init__.py
def get_version():
    init_file = this_directory / "meeting_notes_handler" / "__init__.py"
    if init_file.exists():
        content = init_file.read_text(encoding='utf-8')
        match = re.search(r'__version__ = [\'"]([^\'"]*)[\'"]', content)
        if match:
            return match.group(1)
    return "0.1.0"

# Read requirements
def get_requirements():
    requirements_file = this_directory / "requirements.txt"
    if requirements_file.exists():
        with open(requirements_file, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="meeting-notes-handler",
    version=get_version(),
    description="A Python CLI tool for fetching and organizing Google Meet meeting notes",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="matburt",
    author_email="mat@matburt.net",
    url="https://github.com/matburt/meeting-notes-handler",
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
    install_requires=get_requirements(),
    entry_points={
        'console_scripts': [
            'meeting-notes=meeting_notes_handler.main:cli',
            'mns=meeting_notes_handler.main:cli',  # Short alias
        ],
    },
    python_requires=">=3.8",
    keywords=['google-meet', 'calendar', 'meeting-notes', 'productivity', 'automation'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Office/Business :: Scheduling",
        "Topic :: Text Processing :: Markup :: Markdown",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    project_urls={
        "Bug Reports": "https://github.com/matburt/meeting-notes-handler/issues",
        "Source": "https://github.com/matburt/meeting-notes-handler",
        "Documentation": "https://github.com/matburt/meeting-notes-handler#readme",
    },
)