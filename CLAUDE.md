# Meeting Notes Handler

A sophisticated Python CLI tool that automatically discovers, fetches, and organizes meeting notes from Google Calendar and Google Docs.

## Project Overview

**Meeting Notes Handler** is a professional productivity tool designed to streamline meeting note collection and organization for busy professionals who attend numerous Google Meet meetings.

#### Key Features
- = **Smart Discovery**: Automatically finds Google Meet meetings from your calendar
- =� **Gemini Integration**: Specialized support for fetching Gemini-generated meeting notes from attachments
- =� **Multi-Format Support**: Handles Google Docs, Sheets, Slides with native export capabilities
- =� **Organized Storage**: Groups meetings by ISO week in structured directories
- = **Smart Deduplication**: Avoids re-processing already fetched meetings
- <� **Selective Fetching**: Filter for only Gemini notes/transcripts or specific document types
- =� **Simple Authentication**: Uses Google CLI for streamlined setup

#### Architecture
```
meeting_notes_handler/
   main.py                 # CLI interface with Click
   config.py              # Configuration management with YAML support
   google_meet_fetcher.py  # Google Calendar/Meet integration
   docs_converter.py       # Document conversion with native export
   file_organizer.py       # File organization and deduplication
```

## Development Guidelines

### Code Quality Standards
- Follow Python packaging best practices with pyproject.toml
- Use type hints throughout the codebase
- Implement comprehensive error handling and logging
- Support Python 3.8+ for broad compatibility
- Use Click for professional CLI interfaces
- Follow semantic versioning

### Authentication Strategy
- Primary: Google CLI (gcloud) for seamless user experience
- Fallback: Manual OAuth2 credentials for advanced users
- Support for service accounts in automated environments

### File Processing Approach
- Native Google API exports for best quality (Docs � Markdown, Sheets � CSV)
- Graceful degradation for unsupported file types
- File type detection before processing to prevent errors
- Smart attachment handling for Gemini notes discovery

### CLI Design Principles
- Intuitive commands with descriptive flags
- Comprehensive help text and examples
- Progress feedback for long-running operations
- Dry-run capabilities for safe preview
- Flexible filtering and configuration options

## Configuration Management

Uses YAML configuration with environment variable overrides:
- `google.credentials_file`: OAuth2 credentials location
- `google.token_file`: Token storage location
- `output.directory`: Meeting notes storage location
- `calendar.keywords`: Meeting detection patterns
- `docs.use_native_export`: Prefer native Google export
- `logging.level`: Logging verbosity

## CLI Commands

### Core Commands
- `setup` - Interactive setup and authentication
- `fetch` - Main command for fetching meeting notes
- `list-weeks` - Show available weeks with notes
- `list-meetings` - Show meetings in specific week
- `config-show` - Display current configuration

### Fetch Options
- `--days N` - Fetch from last N days (default: 7)
- `--accepted` - Only include meetings you've accepted
- `--gemini-only` - Filter for only Gemini notes and transcripts
- `--dry-run` - Preview without saving files
- `--force` - Re-fetch even if already processed

## Future Enhancements

The project is designed for extensibility with planned features:
- AI-powered meeting summarization
- Action item extraction and tracking
- Attendee analysis and insights
- Integration with other meeting platforms
- Web interface for broader accessibility
- Advanced search and filtering capabilities

## Testing Strategy

### Current Test Coverage
- **Error Handling**: Comprehensive tests for Google API errors (404, 403, 429, 5xx) with user-friendly messages
- **Rate Limiting**: Tests for exponential backoff retry logic with jitter
- **Document Classification**: Tests for identifying Gemini vs human-created documents
- **Meeting Series Tracking**: Tests for recurring meeting detection and fingerprinting
- **Content Extraction**: Tests for smart content filtering and section parsing
- **Google API Integration**: Mocked tests for Calendar and Drive APIs

### Running Tests
```bash
# Install test dependencies
pip install pytest

# Run all tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_docs_converter.py -v
python -m pytest tests/test_document_classifier.py -v

# Run tests with coverage (if coverage.py is installed)
python -m pytest tests/ --cov=meeting_notes_handler --cov-report=html
```

### Test Files Structure
```
tests/
├── __init__.py
├── test_document_classifier.py    # Document type classification tests
├── test_series_tracker.py         # Meeting series detection tests  
├── test_smart_extractor_simple.py # Content extraction core tests
├── test_docs_converter.py         # Error handling and rate limiting tests
└── test_google_meet_fetcher.py    # Google Calendar integration tests
```

### Writing Tests for New Features

**MANDATORY**: When adding new features, always write corresponding tests. Follow these guidelines:

#### 1. Test File Naming
- Use `test_<module_name>.py` format
- Place in `tests/` directory
- Mirror the structure of `meeting_notes_handler/`

#### 2. Test Class Structure
```python
"""Tests for ModuleName."""

import pytest
from unittest.mock import Mock, patch
from meeting_notes_handler.module_name import ClassName


class TestClassName:
    """Test cases for ClassName."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Initialize test objects here
        
    def teardown_method(self):
        """Clean up test fixtures."""
        # Clean up resources if needed
        
    def test_specific_functionality(self):
        """Test specific functionality with descriptive name."""
        # Arrange
        # Act  
        # Assert
```

#### 3. Required Test Categories

**For New Classes:**
- ✅ Constructor/initialization tests
- ✅ Core method functionality tests
- ✅ Error handling and edge cases
- ✅ Integration with existing components

**For Google API Features:**
- ✅ Mock all Google API calls - never hit real APIs in tests
- ✅ Test error responses (404, 403, 429, 5xx)
- ✅ Test rate limiting and retry logic
- ✅ Test data parsing and transformation

**For Content Processing:**
- ✅ Test various input formats and edge cases
- ✅ Test empty/null/malformed inputs
- ✅ Test performance with large datasets
- ✅ Test output format consistency

#### 4. Mock Usage Patterns
```python
# Mock Google API services
with patch('module.build') as mock_build:
    mock_service = Mock()
    mock_build.return_value = mock_service
    # Test implementation

# Mock HTTP errors
from googleapiclient.errors import HttpError
mock_response = Mock()
mock_response.status = 404
error = HttpError(mock_response, b'{"error": "Not found"}')
```

#### 5. Test Data Guidelines
- Use realistic but anonymized test data
- Create reusable test fixtures in `setup_method()`
- Use temporary directories for file system tests
- Include edge cases: empty data, large data, malformed data

#### 6. Coverage Requirements
- Aim for >80% code coverage on new features
- All public methods must have tests
- All error paths must be tested
- Critical business logic requires comprehensive test scenarios

### Testing Best Practices
- **Fast Tests**: Unit tests should run quickly (<1 second each)
- **Isolated Tests**: Each test should be independent and not rely on external state
- **Descriptive Names**: Test names should clearly describe what is being tested
- **One Assertion Per Test**: Focus each test on a single behavior
- **Mock External Dependencies**: Never depend on real Google APIs, file system, or network
- **Test Both Success and Failure Paths**: Include error handling tests

## Packaging and Distribution

- Modern Python packaging with pyproject.toml
- Entry points for both `meeting-notes` and `mns` commands
- Development dependencies for contributors
- Build system using setuptools with wheel support
- Comprehensive metadata for PyPI distribution

## Important Notes for Claude

- This tool focuses on READ-ONLY access to Google services for security
- All file processing includes error handling for edge cases
- Authentication is designed to be user-friendly while maintaining security
- The codebase follows modern Python standards and best practices
- File organization matches professional software development patterns