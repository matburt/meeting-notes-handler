"""Meeting Notes Handler - A tool for fetching and organizing Google Meet notes."""

__version__ = "0.1.0"
__author__ = "matburt"
__email__ = "mat@matburt.net"
__description__ = "A Python CLI tool for fetching and organizing Google Meet meeting notes"

# Import main classes for easier access
from .config import Config
from .google_meet_fetcher import GoogleMeetFetcher
from .file_organizer import FileOrganizer
from .docs_converter import DocsConverter

__all__ = [
    "Config",
    "GoogleMeetFetcher", 
    "FileOrganizer",
    "DocsConverter",
    "__version__",
    "__author__",
    "__email__",
    "__description__",
]