# Meeting Notes Handler

A powerful Python command-line tool that automatically fetches and organizes Google Meet meeting notes from your Google Calendar and associated Google Docs. Designed for professionals who want to keep their meeting notes organized without manual effort.

## ✨ Features

- 🔍 **Automatic Discovery**: Intelligently finds Google Meet meetings from your calendar
- 📎 **Gemini Integration**: Specialized support for auto-generated Gemini meeting notes from attachments
- 📄 **Multi-Format Support**: Converts Google Docs, Sheets, and Slides to clean Markdown
- 🗂️ **Smart Organization**: Groups meetings by ISO week in organized directory structure
- 🔄 **Intelligent Deduplication**: Automatically skips already processed meetings
- 🎯 **Selective Fetching**: Filter for only Gemini notes/transcripts or accepted meetings
- 🚀 **Streamlined Setup**: One-command authentication using Google CLI
- ⚙️ **Highly Configurable**: Flexible configuration with YAML and environment variables
- 🖥️ **Professional CLI**: Comprehensive command-line interface with helpful feedback

## 🚀 Quick Start

### 1. Installation

#### Option A: Install from source (Recommended for development)
```bash
git clone https://github.com/matburt/meeting-notes-handler.git
cd meeting-notes-handler
pip install -e .
```

#### Option B: Install as package
```bash
pip install git+https://github.com/matburt/meeting-notes-handler.git
# or from local directory
pip install .
```

#### Option C: Development setup
```bash
pip install -e ".[dev]"  # Includes testing and linting tools
```

### 2. Authentication Setup

The tool needs permission to read your Google Calendar and Docs. This one-time setup uses the official Google Cloud CLI for secure authentication.

#### Step 1: Install Google Cloud CLI
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL  # Restart your shell
```

#### Step 2: Authenticate and grant permissions
```bash
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/documents.readonly
```

#### Step 3: Enable required APIs
```bash
gcloud services enable calendar-json.googleapis.com drive.googleapis.com docs.googleapis.com
```

### 3. Initial Setup and Test
```bash
meeting-notes setup
# This will guide you through configuration and test authentication
```

### 4. Start Fetching Meeting Notes
```bash
# Fetch meetings from the last 7 days (default)
meeting-notes fetch

# See all available options
meeting-notes fetch --help
```

## 📋 Usage

### Core Commands

| Command | Description |
|---------|-------------|
| `setup` | Interactive setup and authentication testing |
| `fetch` | Fetch and process meeting notes (main command) |
| `list-weeks` | Show available weeks with meeting notes |
| `list-meetings WEEK` | Show meetings in a specific week (e.g., 2024-W03) |
| `config-show` | Display current configuration settings |

### Fetch Command Options

| Option | Short | Description |
|--------|-------|-------------|
| `--days N` | `-d` | Number of days back to search (default: 7) |
| `--accepted` | | Only fetch meetings you've accepted or are tentative for |
| `--gemini-only` | `-g` | **NEW**: Only fetch Gemini notes and transcripts, skip other documents |
| `--dry-run` | | Preview what would be fetched without saving files |
| `--force` | `-f` | Force re-fetch meetings even if already processed |
| `--week YYYY-WW` | `-w` | Fetch specific week (e.g., 2024-W03) |

### Example Usage

```bash
# Basic usage - fetch last 7 days
meeting-notes fetch

# Fetch from last 14 days, only accepted meetings
meeting-notes fetch --days 14 --accepted

# Only fetch Gemini-generated notes and transcripts
meeting-notes fetch --gemini-only

# Preview what would be fetched without saving
meeting-notes fetch --dry-run --days 30

# Force re-fetch everything from last week
meeting-notes fetch --force --days 7

# Combine options for specific workflow
meeting-notes fetch --gemini-only --accepted --days 14

# List all available weeks
meeting-notes list-weeks

# Show meetings in a specific week
meeting-notes list-meetings 2024-W15

# Check current configuration
meeting-notes config-show

# Using short alias
mns fetch -g -d 14  # Gemini-only for last 14 days
```

## 🎯 Gemini Integration (New Feature)

The `--gemini-only` flag is perfect for users who primarily want to collect AI-generated meeting summaries:

### What it includes:
- **Gemini meeting notes** (auto-generated summaries)
- **Meeting transcripts** 
- **Chat logs** from meetings
- **Auto-generated content** from Google Meet

### What it filters out:
- User-uploaded documents
- Manually created notes
- Presentation slides
- Other attached files

### Smart Detection:
The tool identifies Gemini content by:
- Attachment titles containing keywords like "Gemini", "Notes by Gemini", "Transcript"
- URL patterns specific to Gemini-generated content
- File metadata indicating auto-generation

```bash
# Perfect for collecting AI summaries
meeting-notes fetch --gemini-only --days 30

# Combine with other filters
meeting-notes fetch --gemini-only --accepted --force
```

## 📁 File Organization

Meeting notes are automatically organized in a clean, searchable structure:

```
meeting_notes/
├── 2024-W15/                           # ISO week format
│   ├── meeting_20240408_140000_team_standup.md
│   ├── meeting_20240410_100000_project_review.md
│   └── meeting_20240412_150000_client_demo.md
├── 2024-W16/
│   ├── meeting_20240415_090000_sprint_planning.md
│   └── meeting_20240418_160000_retrospective.md
└── 2024-W17/
    └── meeting_20240422_140000_all_hands.md
```

### File Content Structure
Each meeting file includes:
```markdown
---
date: 2024-04-08T14:00:00-04:00
title: Team Standup
week: 2024-W15
meeting_id: abc123
organizer: team-lead@company.com
attendees_count: 8
docs_count: 2
docs_links: ['https://docs.google.com/...']
---

# Team Standup

**Date:** 2024-04-08 14:00
**Organizer:** team-lead@company.com
**Attendees:** member1@company.com, member2@company.com, ...
**Meeting Link:** https://meet.google.com/xyz-abc-def

## Document 1
**Title:** Sprint Update Notes

[Converted Markdown content from Google Doc]

## Document 2
**Title:** Action Items

[Additional document content]
```

## ⚙️ Configuration

### Configuration File
Create `config.yaml` in your project directory (see `config.yaml.example`):

```yaml
google:
  credentials_file: "credentials.json"
  token_file: "token.json"

output:
  directory: "./meeting_notes"

calendar:
  keywords: ["meet.google.com", "Google Meet"]
  days_back: 7

docs:
  use_native_export: true      # Use Google's native Markdown export
  fallback_to_manual: true     # Fallback if native export fails

logging:
  level: "INFO"
```

### Environment Variables
Override configuration with environment variables:
- `GOOGLE_CREDENTIALS_FILE` - Path to OAuth2 credentials
- `GOOGLE_TOKEN_FILE` - Path to store authentication token
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `OUTPUT_DIRECTORY` - Where to save meeting notes

## 🔧 Advanced Authentication

### Alternative Authentication Methods

#### Service Accounts (for automation)
1. Create a service account in Google Cloud Console
2. Grant domain-wide delegation for Calendar and Drive access
3. Download the service account key JSON file
4. Share calendars and docs with the service account email
5. Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

#### Manual OAuth Setup
1. Create OAuth2 credentials in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Calendar, Drive, and Docs APIs
3. Download credentials JSON as `credentials.json`
4. Run `meeting-notes setup` and select manual setup

## 🔍 How It Works

1. **Authentication**: Secure OAuth2 flow with Google APIs
2. **Calendar Scanning**: Searches your primary calendar for Google Meet meetings
3. **Document Discovery**: Extracts links from meeting descriptions AND attachments
4. **Smart Filtering**: Identifies Gemini notes, transcripts, and other document types
5. **File Type Detection**: Determines document type before processing
6. **Intelligent Conversion**: 
   - Google Docs → Native Markdown export
   - Google Sheets → CSV converted to Markdown tables
   - Google Slides → Native Markdown export
   - Other files → Informative placeholders
7. **Deduplication**: Tracks processed meetings to avoid re-downloading
8. **Organization**: Saves files in ISO week-based directory structure

## 🛠️ Troubleshooting

### Authentication Issues

#### Google CLI Problems
```bash
# Re-authenticate if needed
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/documents.readonly

# Check current authentication
gcloud auth list
gcloud auth application-default print-access-token
```

#### Manual Credentials Issues
- Ensure credentials file is valid JSON
- Verify all required APIs are enabled in Google Cloud Console
- Delete `token.json` to force re-authentication
- Check that credentials are for "Desktop application" type

### No Meetings Found
- Verify calendar keywords match your meeting descriptions
- Check that meetings have Google Docs links or attachments
- Increase `days_back` setting to search further
- Use `--dry-run` to see what meetings are being found

### File Processing Errors
- The tool gracefully handles different file types
- Permission errors show clear messages instead of crashing
- Use `--log-level DEBUG` for detailed file processing information
- Unsupported files are included as informative placeholders

### Gemini Notes Not Found
- Ensure Gemini is enabled for your Google Meet meetings
- Check that Gemini notes are being generated (usually appear as attachments)
- Use `--force` to re-process meetings if Gemini notes were added later
- Try without `--gemini-only` to see all documents, then enable filtering

### Performance Issues
```bash
# Check API quotas
gcloud services list --enabled
gcloud logging read "resource.type=api" --limit=50

# Use selective fetching
meeting-notes fetch --accepted --days 3  # Reduce scope
meeting-notes fetch --gemini-only        # Focus on Gemini content
```

## 🚧 Development

### Package Structure
```
meeting-notes-handler/
├── meeting_notes_handler/       # Main package
│   ├── __init__.py             # Package initialization
│   ├── main.py                 # CLI entry point with Click
│   ├── config.py               # Configuration management
│   ├── google_meet_fetcher.py  # Google Calendar/Meet integration
│   ├── docs_converter.py       # Document conversion logic
│   └── file_organizer.py       # File organization and deduplication
├── pyproject.toml              # Modern packaging configuration
├── requirements.txt            # Dependencies
├── config.yaml.example         # Configuration template
└── README.md                   # This file
```

### Building and Testing
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black meeting_notes_handler/
isort meeting_notes_handler/
flake8 meeting_notes_handler/

# Build package
python -m build
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass and code is properly formatted
5. Submit a pull request with a clear description

## 🔮 Roadmap

### Phase 2: Analysis and Intelligence
- **AI-powered summarization** of meeting content
- **Action item extraction** and tracking
- **Attendee analysis** and meeting patterns
- **Topic clustering** across meetings
- **Meeting effectiveness metrics**

### Phase 3: Integration and Automation
- **Slack/Teams integration** for automatic sharing
- **Calendar integration** for action item scheduling
- **Email digest** of weekly meeting summaries
- **API endpoints** for custom integrations
- **Webhook support** for real-time processing

### Phase 4: User Experience
- **Web interface** for non-technical users
- **Advanced search** and filtering capabilities
- **Export options** (PDF, Word, etc.)
- **Meeting analytics dashboard**
- **Mobile companion app**

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

- **Documentation**: See this README and in-code documentation
- **Issues**: Report bugs and request features via GitHub Issues
- **Configuration Help**: Use `meeting-notes config-show` and `meeting-notes setup`
- **Debug Mode**: Use `--log-level DEBUG` for detailed troubleshooting

---

**Note**: This tool requires read-only access to your Google Calendar and Drive. All data remains on your local machine - nothing is sent to external services except for authentication with Google's official APIs.