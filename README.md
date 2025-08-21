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

## 📚 Documentation

- 📋 **[File Organization & Format Specification](docs/file-organization.md)** - Complete guide to directory structure, file formats, metadata schemas, and caching system
- 🔍 **[Meeting Notes Diffing Guide](docs/file-organization.md#-meeting-notes-diffing--change-tracking-new-feature)** - Understanding content comparison and change tracking
- ⚙️ **[Configuration Reference](docs/file-organization.md#-configuration-impact-on-organization)** - Advanced configuration options and environment variables

## 📋 Requirements

- **Python 3.12+** (required for latest features and performance)
- **Google account** with Calendar and Drive access
- **Google CLI** (recommended) or Google Cloud project for authentication
- **uv** (recommended) or pip for package management

## 🚀 Quick Start

### 1. Installation

#### Recommended: Using uv (Fast Python Package Manager)
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/matburt/meeting-notes-handler.git
cd meeting-notes-handler

# Install with uv (creates venv automatically)
uv pip install -e .

# For development with extra dependencies
uv pip install -e ".[dev]"
```

#### Alternative: Using pip
```bash
git clone https://github.com/matburt/meeting-notes-handler.git
cd meeting-notes-handler

# Create virtual environment (Python 3.12+ required)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .
```

#### Quick Install (No Development)
```bash
pip install git+https://github.com/matburt/meeting-notes-handler.git
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
# Using uv (recommended)
uv run meeting-notes setup

# Or with activated venv
source .venv/bin/activate
meeting-notes setup
```

### 4. Start Fetching Meeting Notes

#### Using uv (Recommended)
```bash
# Fetch meetings from the last 7 days (default)
uv run meeting-notes fetch

# See all available options
uv run meeting-notes fetch --help
```

#### Using activated virtual environment
```bash
# Activate the virtual environment first
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Then run commands directly
meeting-notes fetch
meeting-notes fetch --help
```

## 📋 Usage

### Core Commands

| Command | Description |
|---------|-------------|
| `setup` | Interactive setup and authentication testing |
| `fetch` | Fetch and process meeting notes (main command) |
| `analyze` | **NEW**: AI-powered analysis of meeting notes with LLM insights |
| `diff` | **NEW**: Compare meeting notes across different instances |
| `changelog` | **NEW**: Show changelog for recurring meetings |
| `list-weeks` | Show available weeks with meeting notes |
| `list-meetings WEEK` | Show meetings in a specific week (e.g., 2024-W03) |
| `config-show` | Display current configuration settings |

### Fetch Command Options

| Option | Short | Description |
|--------|-------|-------------|
| `--days N` | `-d` | Number of days back to search (default: 7) |
| `--accepted` | | Only fetch meetings you've accepted or are tentative for |
| `--declined` | | Only fetch meetings you've declined (mutually exclusive with --accepted) |
| `--gemini-only` | `-g` | Only fetch Gemini notes and transcripts, skip other documents |
| `--smart-filter` | `-s` | Apply smart content filtering to extract only new content from recurring meetings |
| `--diff-mode` | | **NEW**: Only save new content compared to previous meetings |
| `--dry-run` | | Preview what would be fetched without saving files |
| `--force` | `-f` | Force re-fetch meetings even if already processed |
| `--week YYYY-WW` | `-w` | Fetch specific week (e.g., 2024-W03) |

**Note**: The `--accepted` and `--declined` options are mutually exclusive - you cannot use both at the same time. If neither is specified, all meetings (regardless of response status) will be fetched.

### New Diff and Changelog Commands

#### Diff Command
Compare meeting notes across different instances to see what has changed:

```bash
# Compare last 2 meetings in a series by name
meeting-notes diff "Sprint Planning"

# Compare last 3 meetings by series ID
meeting-notes diff --series-id abc123 --last 3

# Show only summary (no detailed changes)
meeting-notes diff "Team Standup" --summary

# Compare specific weeks (planned feature)
meeting-notes diff "Sprint Demo" --weeks 2024-W29 2024-W30
```

#### Changelog Command
Show a changelog of changes for recurring meetings:

```bash
# Show changelog for last 4 meetings
meeting-notes changelog "Team Standup"

# Show changes for all series since a date
meeting-notes changelog --all-series --since 2024-07-01

# Export changelog in markdown format
meeting-notes changelog "Sprint Planning" --format markdown

# Show changes for specific series by ID
meeting-notes changelog --series-id abc123 --last 6
```

### New Analyze Command
Leverage AI to extract insights and summaries from your meeting notes:

```bash
# Weekly summary of most important points
meeting-notes analyze --week 2024-W33

# Analyze last 7 days for key decisions and themes  
meeting-notes analyze --days 7

# Personal analysis - find your action items and discussions
meeting-notes analyze --personal --days 30
meeting-notes analyze --personal --week 2024-W33

# Use different LLM providers
meeting-notes analyze --provider openai --week 2024-W33
meeting-notes analyze --provider anthropic --model claude-3-opus
meeting-notes analyze --provider gemini --days 14
meeting-notes analyze --provider openrouter --model "meta-llama/llama-3-70b"

# Save analysis results to file
meeting-notes analyze --week 2024-W33 --output weekly-summary.json
meeting-notes analyze --personal --output my-actions.json

# Adjust relevance threshold for personal analysis
meeting-notes analyze --personal --min-relevance 0.5 --days 14
```

#### Analyze Command Options

| Option | Short | Description |
|--------|-------|-------------|
| `--days N` | `-d` | Number of days back to analyze (default: 7 for weekly, 30 for personal) |
| `--week YYYY-WW` | `-w` | Analyze specific week (e.g., 2024-W33) |
| `--personal` | `-p` | Focus on personal action items and discussions |
| `--provider` | | LLM provider: openai, anthropic, gemini, openrouter |
| `--model` | | Specific model to use (overrides config) |
| `--output` | `-o` | Save analysis results to file |
| `--format` | | Output format: json, markdown (default: markdown) |
| `--min-relevance` | | Minimum relevance score for personal analysis (0.0-1.0, default: 0.3) |

### Example Usage

**Note**: If not using an activated virtual environment, prefix all commands with `uv run`

```bash
# Basic usage - fetch last 7 days
uv run meeting-notes fetch

# Fetch from last 14 days, only accepted meetings
uv run meeting-notes fetch --days 14 --accepted

# Fetch from last 7 days, only declined meetings
uv run meeting-notes fetch --days 7 --declined

# Only fetch Gemini-generated notes and transcripts
uv run meeting-notes fetch --gemini-only

# Preview what would be fetched without saving
uv run meeting-notes fetch --dry-run --days 30

# Force re-fetch everything from last week
uv run meeting-notes fetch --force --days 7

# Apply smart filtering to extract only new content from recurring meetings
uv run meeting-notes fetch --smart-filter --days 14

# Combine options for specific workflow
uv run meeting-notes fetch --gemini-only --accepted --days 14

# Use smart filtering with Gemini-only for optimal LLM processing
uv run meeting-notes fetch --smart-filter --gemini-only --accepted

# NEW: Only save meetings that have changed content (diff mode)
uv run meeting-notes fetch --diff-mode --accepted

# List all available weeks
uv run meeting-notes list-weeks

# Show meetings in a specific week
uv run meeting-notes list-meetings 2024-W15

# Check current configuration
uv run meeting-notes config-show

# Using short aliases
uv run mns fetch -g -d 14  # Gemini-only for last 14 days
uv run mns fetch -s -g     # Smart filter + Gemini for new content only
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

## 🧠 AI-Powered Meeting Analysis (New Feature)

Transform your meeting notes into actionable insights using state-of-the-art LLM analysis. Extract key decisions, personal action items, and important themes automatically with **97% cost reduction** through smart content filtering.

### Key Features:
- **Weekly Summaries**: Identify the most important decisions and themes from a week's meetings
- **Personal Analysis**: Find meetings where you had action items or participated in discussions
- **Multi-Provider Support**: Works with OpenAI, Anthropic, Gemini, and OpenRouter
- **Smart Content Filtering**: Reduces analysis costs by 97% (from ~$20-40 to ~$0.61 per week)
- **Token Usage Estimation**: Preview costs before running expensive analyses
- **Cost Protection**: Automatic warnings and confirmation prompts
- **Flexible Output**: Save results as JSON or view formatted summaries

### Quick Start

#### 1. Set up API Key
```bash
# Choose your preferred provider
export OPENAI_API_KEY=your_key_here
# OR
export ANTHROPIC_API_KEY=your_key_here
# OR 
export GEMINI_API_KEY=your_key_here
# OR
export OPENROUTER_API_KEY=your_key_here
```

#### 2. Configure User Context (for personal analysis)
```yaml
# In your config.yaml
analysis:
  user_context:
    user_name: "Your Name"
    user_aliases: ["@yourname", "your.email@company.com"]
```

#### 3. Run Analysis with Cost Optimization
```bash
# Weekly summary with cost estimation (recommended first step)
meeting-notes analyze --week 2024-W33 --show-token-usage

# Cost-efficient analysis using Gemini-only filtering (default)
meeting-notes analyze --week 2024-W33 --content-filter gemini-only

# Personal analysis with cost protection
meeting-notes analyze --personal --days 30 --content-filter gemini-only

# Full content analysis (expensive - for comprehensive needs only)
meeting-notes analyze --week 2024-W33 --content-filter all --show-token-usage
```

### 💰 Smart Content Filtering (Cost Optimization)

The biggest breakthrough for practical AI analysis is **smart content filtering** that reduces costs by 97% while preserving key insights.

#### Content Filtering Modes

**🎯 Gemini-Only (Recommended - Default)**
- Extracts only AI-generated meeting summaries (Summary, Details, Suggested next steps)
- **97% cost reduction**: ~2M tokens → ~61k tokens per week
- **Cost**: ~$0.61 per weekly analysis (vs $20-40 without filtering)
- **Best for**: Regular weekly/monthly analysis, cost-conscious users

```bash
# Default mode - most cost-efficient
meeting-notes analyze --week 2024-W33 --content-filter gemini-only
```

**📝 No-Transcripts**
- Includes meeting content but excludes verbose transcripts (~70-80% of content)
- **Moderate cost reduction**: Good balance of content and cost
- **Includes**: Gemini notes + embedded documents (optional)
- **Best for**: Comprehensive analysis without transcript noise

```bash
# Include more context without transcripts
meeting-notes analyze --week 2024-W33 --content-filter no-transcripts

# Include embedded documents too
meeting-notes analyze --week 2024-W33 --content-filter no-transcripts --include-docs
```

**📊 All Content**
- Full meeting content including transcripts
- **Expensive**: Original token usage (~$20-40 per busy week)
- **Best for**: Occasional deep-dive analysis, compliance requirements

```bash
# Full analysis - check costs first!
meeting-notes analyze --week 2024-W33 --content-filter all --show-token-usage
```

#### Real-World Cost Comparison

**Before Content Filtering:**
```
2025-W29: 38 meetings → 2,018,765 tokens → ~$40.00 (GPT-4)
2025-W32: 26 meetings → 1,708,573 tokens → ~$34.00 (GPT-4)
```

**After Gemini-Only Filtering:**
```
2025-W29: 38 meetings → 61,247 tokens → ~$0.61 (GPT-4)
2025-W32: 26 meetings → 41,556 tokens → ~$0.42 (GPT-4)
```

**🎉 Result: 97% cost reduction with preserved insights!**

#### Token Usage Preview
Always check costs before expensive operations:

```bash
# Preview tokens and costs before analysis
meeting-notes analyze --week 2024-W33 --show-token-usage

# Example output:
# 📊 Analyzing token usage...
#    📝 Meetings to analyze: 23
#    🔢 Total tokens: 61,247
#    💰 Estimated cost (GPT-4): $0.61
#    Content filter: gemini-only
```

### Analysis Types

#### Weekly Summary Analysis
Extracts the most important information from a set of meetings:

**What it identifies:**
- 🎯 **Key Decisions**: Important decisions that impact future work
- 📋 **Major Themes**: Recurring topics across multiple meetings  
- ✅ **Critical Action Items**: High-priority tasks with owners and deadlines
- ⚠️ **Notable Risks**: Potential blockers or concerns raised

**Example Output:**
```
📊 Weekly Analysis Results for 2024-W33:
   📈 Meetings analyzed: 5

🎯 Most Important Decisions:
   1. OAuth 2.0 Implementation - Decided to use Auth0 for mobile apps
   2. Database Migration - Approved PostgreSQL migration for Q2
   3. Security Review Process - New mandatory review for external providers

📋 Key Themes:
   • Authentication system overhaul (3 meetings)
   • Performance optimization discussions (2 meetings)
   • Q2 planning and resource allocation

✅ Critical Action Items:
   [HIGH] John: Complete OAuth integration by Friday
   [HIGH] Sarah: Security audit documentation by Wednesday
   [MEDIUM] Team: Prepare client demo for Tuesday
```

#### Personal Analysis
Finds meetings where you had involvement or relevance:

**What it identifies:**
- 📋 **Your Action Items**: Tasks specifically assigned to you
- 💬 **Discussions You Led**: Topics where you were consulted or presented
- 🎯 **Decisions Affecting You**: Changes that impact your work
- 🔍 **Relevance Scoring**: Automatically filters for personally relevant content

**Example Output:**
```
📊 Personal Analysis Results (last 30 days):
   📈 Meetings analyzed: 12
   🎯 Relevant meetings: 7
   ✅ Action items assigned: 4
   💬 Discussions involved: 8

📋 Your Action Items:
   [HIGH] Review authentication flow documentation - Due Thursday
   [MEDIUM] Update API endpoints for new auth system - Due next Monday
   [LOW] Participate in security review meeting - Wednesday 2pm

📝 Meetings with your involvement:
   • Sprint Planning (4/8): Assigned to API security review
   • Architecture Review (4/10): Your expertise needed for OAuth
   • Team Standup (4/11): Blocker discussion about your PR
```

### LLM Provider Configuration with Cost Protection

Configure your preferred LLM provider with the new cost-aware defaults:

#### Complete Configuration Example
```yaml
analysis:
  provider: "openai"  # openai, anthropic, gemini, openrouter
  
  # Content filtering for cost efficiency (NEW)
  content_filter: "gemini-only"       # Default: only AI-generated notes
  include_embedded_docs: false        # Exclude documents by default
  exclude_transcripts: true           # Always exclude verbose transcripts
  
  # Cost protection settings (NEW)
  max_input_tokens: 100000           # Safety limit for input tokens
  cost_warning_threshold: 5.0        # Warn if cost > $5
  require_confirmation: true         # Require confirmation for expensive ops
  
  # Chunking settings for large content (NEW)
  chunk_strategy: "by-meeting"       # Process meetings individually
  max_chunk_size: 50000             # Max tokens per chunk
  
  # User context for personal analysis
  user_context:
    user_name: "Your Name"
    user_aliases: ["@yourname", "your.email@company.com"]
```

#### Provider-Specific Settings

**OpenAI (Default)**
```yaml
analysis:
  provider: "openai"
  openai:
    api_key_env: "OPENAI_API_KEY"
    model: "gpt-4-turbo-preview"
    temperature: 0.3
    max_tokens: 16000                # Increased from 4000
```

**Anthropic (Claude)**
```yaml
analysis:
  provider: "anthropic"
  anthropic:
    api_key_env: "ANTHROPIC_API_KEY"
    model: "claude-3-opus-20240229"
    temperature: 0.3
    max_tokens: 16000                # Increased from 4000
```

**Google Gemini**
```yaml
analysis:
  provider: "gemini"
  gemini:
    api_key_env: "GEMINI_API_KEY"
    model: "gemini-pro"
    temperature: 0.3
    max_tokens: 16000                # Increased from 4000
```

**OpenRouter (Access to Multiple Models)**
```yaml
analysis:
  provider: "openrouter"
  openrouter:
    api_key_env: "OPENROUTER_API_KEY"
    model: "anthropic/claude-3-opus"
    base_url: "https://openrouter.ai/api/v1"
    temperature: 0.3
    max_tokens: 16000                # Increased from 4000
```

### ⚠️ **Critical: Token Usage and Costs (SOLVED with Content Filtering!)**

**BREAKTHROUGH**: Smart content filtering has solved the cost problem! Here's the reality of costs with and without filtering:

#### Without Content Filtering (Original Problem)
```
2025-W29: 38 meetings → 2,018,765 tokens → ~$40.00 (GPT-4)
2025-W32: 26 meetings → 1,708,573 tokens → ~$34.00 (GPT-4)
```
**Result**: Too expensive for regular use!

#### With Smart Content Filtering (Current Solution)
```
🎯 Gemini-Only Filtering (Default):
2025-W29: 38 meetings → 61,247 tokens → ~$0.61 (GPT-4)
2025-W32: 26 meetings → 41,556 tokens → ~$0.42 (GPT-4)

📝 No-Transcripts Filtering:
2025-W29: 38 meetings → ~400,000 tokens → ~$8.00 (GPT-4)
2025-W32: 26 meetings → ~300,000 tokens → ~$6.00 (GPT-4)
```
**Result**: 97% cost reduction with preserved insights! 🎉

#### Content Breakdown Analysis
**What gets filtered out:**
- **Transcripts**: 70-80% of content (very verbose, low insight density)
- **Embedded Documents**: 5-10% of content (often duplicated info)
- **Metadata/Formatting**: 5-10% of content (structural overhead)

**What gets preserved (Gemini-only):**
- **Summary**: Key decisions and outcomes
- **Details**: Important discussion points with timestamps
- **Suggested next steps**: Action items and follow-ups

#### Cost Protection Features:
- **Automatic cost estimation** before analysis (`--show-token-usage`)
- **Warning prompts** for expensive operations (configurable threshold)
- **Smart defaults**: Gemini-only filtering enabled by default
- **Confirmation prompts**: Required for operations over cost threshold
- **Real-time token counting**: Exact cost preview before spending

#### Recommended Approach:
1. **Use default filtering**: Start with `--content-filter gemini-only` (default)
2. **Preview costs**: Always use `--show-token-usage` for new weeks
3. **Upgrade selectively**: Use `--content-filter no-transcripts` for more context when needed
4. **Reserve full analysis**: Only use `--content-filter all` for special cases

### Advanced Usage

#### Content Filtering Strategies
- **Weekly routine**: Use `--content-filter gemini-only` for regular analysis
- **Deep dives**: Use `--content-filter no-transcripts` when you need more context
- **Compliance/legal**: Use `--content-filter all` only when full transcript is required
- **Cost budgeting**: Set `cost_warning_threshold` to your monthly AI budget

#### Integration Tips with Cost Optimization
```bash
# Weekly digest automation with cost control
meeting-notes analyze --week $(date +%Y-W%V) --content-filter gemini-only --output weekly-digest.json

# Cost-efficient personal action item tracking
meeting-notes analyze --personal --days 7 --content-filter gemini-only --min-relevance 0.6 --output my-actions.json

# Multi-provider comparison with cost awareness
meeting-notes analyze --provider openai --week 2024-W33 --content-filter gemini-only --show-token-usage --output openai-analysis.json

# Comprehensive analysis with cost preview
meeting-notes analyze --week 2024-W33 --content-filter no-transcripts --include-docs --show-token-usage --output comprehensive-analysis.json

# Budget-conscious automation
meeting-notes analyze --week 2024-W33 --content-filter gemini-only --show-token-usage && \
meeting-notes analyze --week 2024-W33 --content-filter gemini-only --output weekly-summary.json
```

#### Cost Monitoring and Budgeting
```bash
# Check costs before committing to analysis
meeting-notes analyze --week 2024-W33 --show-token-usage

# Set up cost warnings in config.yaml
analysis:
  cost_warning_threshold: 2.0  # Warn if analysis > $2
  require_confirmation: true   # Always confirm expensive operations
  max_input_tokens: 100000    # Hard limit to prevent runaway costs
```

#### Error Handling
- **Missing API Key**: Clear instructions provided for each provider
- **Rate Limiting**: Automatic retry with exponential backoff
- **Content Too Large**: Automatic chunking for large meeting sets
- **Provider Failures**: Graceful error messages with suggested fixes

### Benefits:
- **Time Savings**: Instantly extract key information from hours of meetings
- **Never Miss Action Items**: Automatic detection of your responsibilities
- **Pattern Recognition**: Identify recurring themes and decision trends
- **Multi-Provider Flexibility**: Choose the best LLM for your needs and budget
- **Privacy Focused**: All analysis runs on your chosen provider - no data stored externally

## 🔍 Meeting Notes Diffing & Change Tracking (New Feature)

The tool now supports advanced diffing functionality to track changes in recurring meetings and only save new content.

### Key Features:
- **Content Hashing**: Automatically generates content signatures for meetings
- **Series Tracking**: Identifies recurring meetings across weeks
- **Smart Diffing**: Compares meeting content at paragraph and section levels
- **Change Detection**: Shows what's added, removed, modified, or moved
- **Diff Mode**: Only saves meetings with changed content

### Diff Mode (`--diff-mode`)
Only save meetings that have changed content compared to previous instances:

```bash
# Only save meetings with new content
meeting-notes fetch --diff-mode

# Combine with other filters for efficiency  
meeting-notes fetch --diff-mode --gemini-only --accepted
```

### Compare Meetings
Compare specific meetings to see what changed:

```bash
# Compare last 2 meetings by name
meeting-notes diff "Sprint Planning"

# Compare by series ID with more history
meeting-notes diff --series-id series_123 --last 3

# Show summary only
meeting-notes diff "Team Standup" --summary
```

### Track Changes Over Time
Generate changelogs for recurring meetings:

```bash
# Show recent changes for a specific meeting
meeting-notes changelog "Weekly Status"

# See all changes across series
meeting-notes changelog --all-series --last 2

# Export as markdown
meeting-notes changelog "Sprint Review" --format markdown
```

### Benefits:
- **Storage Efficiency**: Skip saving duplicate content
- **Change Awareness**: Easily see what's new in recurring meetings
- **Content Evolution**: Track how meeting content changes over time
- **Integration Ready**: Perfect for automated processing of new content only

## 🧠 Smart Content Filtering (New Feature)

The `--smart-filter` flag provides intelligent content diffing for recurring meetings, extracting only genuinely new content for optimal LLM processing.

### How it works:
- **Automatic Series Detection**: Identifies recurring meetings using normalized titles, organizer, and time patterns
- **Document Classification**: Distinguishes between ephemeral content (always new) and persistent content (may have updates)
- **Section-Level Comparison**: Compares previous meeting content at paragraph/section level to identify new information
- **Content Reduction**: Filters out duplicate content while preserving all genuinely new information

### What gets filtered:
- **Ephemeral Content** (always included): Gemini notes, transcripts, chat logs, meeting-specific recordings
- **Persistent Content** (compared): Shared project documents, planning boards, action item lists, status updates

### Benefits:
- **Reduced Processing Time**: Significantly smaller files for LLM analysis
- **Focus on New Information**: Eliminates repetitive content from recurring meetings
- **Automatic Operation**: No manual intervention required - works intelligently in the background
- **Safe Filtering**: Conservative approach ensures important content is never lost

### Example Results:
```bash
# Before smart filtering: 50,000 words across all documents
# After smart filtering: 12,000 words (76% reduction, only new content)

uv run meeting-notes fetch --smart-filter --days 14
# 🧠 SMART FILTER - Extracting only new content from recurring meetings
# Smart filtering reduced content by 76.0% (50000 → 12000 words)
```

### Perfect for:
```bash
# LLM-optimized content extraction
meeting-notes fetch --smart-filter --gemini-only --accepted

# Analyze only what's new in weekly status meetings
meeting-notes fetch --smart-filter --days 7

# Extract new content from specific recurring meeting series
meeting-notes fetch --smart-filter --force  # Re-analyze all previous meetings
```

## 📁 File Organization

Meeting notes are automatically organized in a clean, searchable structure:

> 📋 **[Complete File Organization Documentation](docs/file-organization.md)** - Detailed specification of directory structure, file formats, metadata schemas, and content caching system.

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

# NEW: AI Analysis Configuration
analysis:
  provider: "openai"           # openai, anthropic, gemini, openrouter
  templates_dir: "./meeting_notes_handler/templates"
  
  # Cost and safety settings  
  max_cost_warning: 10.0       # Warn if estimated cost exceeds this amount ($USD)
  enable_chunking: true        # Enable automatic chunking for large weeks
  chunk_size: 100000           # Max tokens per chunk for large weeks
  
  # Provider-specific settings
  openai:
    api_key_env: "OPENAI_API_KEY"
    model: "gpt-4-turbo-preview"
    temperature: 0.3
    max_tokens: 16000           # Increased for real-world usage
  
  anthropic:
    api_key_env: "ANTHROPIC_API_KEY"
    model: "claude-3-opus-20240229"
    temperature: 0.3
    max_tokens: 16000           # Increased for real-world usage
  
  gemini:
    api_key_env: "GEMINI_API_KEY"
    model: "gemini-pro"
    temperature: 0.3
    max_tokens: 16000           # Increased for real-world usage
  
  openrouter:
    api_key_env: "OPENROUTER_API_KEY"
    model: "anthropic/claude-3-opus"
    base_url: "https://openrouter.ai/api/v1"
    temperature: 0.3
    max_tokens: 16000           # Increased for real-world usage
  
  # User context for personal analysis
  user_context:
    user_name: "Your Name"
    user_aliases: ["@yourname", "your.email@company.com"]

logging:
  level: "INFO"
```

### Environment Variables
Override configuration with environment variables:

**Google API Settings:**
- `GOOGLE_CREDENTIALS_FILE` - Path to OAuth2 credentials
- `GOOGLE_TOKEN_FILE` - Path to store authentication token

**Analysis Settings:**
- `LLM_PROVIDER` - Default LLM provider (openai, anthropic, gemini, openrouter)
- `OPENAI_API_KEY` - OpenAI API key for GPT models
- `ANTHROPIC_API_KEY` - Anthropic API key for Claude models
- `GEMINI_API_KEY` - Google Gemini API key
- `OPENROUTER_API_KEY` - OpenRouter API key for multiple model access
- `USER_NAME` - Your name for personal analysis

**General Settings:**
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

### Testing

The project includes a comprehensive test suite covering all major functionality:

#### Test Coverage
- **Error Handling**: Google API errors (404, 403, 429, 5xx) with user-friendly messages
- **Rate Limiting**: Exponential backoff retry logic with jitter
- **Document Classification**: Identification of Gemini vs human-created documents
- **Meeting Series Tracking**: Recurring meeting detection and fingerprinting
- **Content Extraction**: Smart content filtering and section parsing
- **Google API Integration**: Mocked tests for Calendar and Drive APIs

#### Running Tests

##### Using uv (Recommended)
```bash
# Install development dependencies including pytest
uv pip install -e ".[dev]"

# Run all tests with verbose output
uv run pytest tests/ -v

# Run specific test files
uv run pytest tests/test_docs_converter.py -v
uv run pytest tests/test_document_classifier.py -v

# Run tests with coverage reporting
uv run pytest tests/ --cov=meeting_notes_handler --cov-report=html
uv run pytest tests/ --cov=meeting_notes_handler --cov-report=term-missing

# Run only fast unit tests (skip integration tests)
uv run pytest tests/ -m "not integration" -v
```

##### Using standard pip
```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pytest if not included in dev dependencies
pip install pytest pytest-cov

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=meeting_notes_handler --cov-report=html
```

#### Test Structure
```
tests/
├── __init__.py
├── test_document_classifier.py    # Document type classification tests
├── test_series_tracker.py         # Meeting series detection tests  
├── test_smart_extractor_simple.py # Content extraction core tests
├── test_docs_converter.py         # Error handling and rate limiting tests
└── test_google_meet_fetcher.py    # Google Calendar integration tests
```

#### Test Guidelines for Contributors

When adding new features, always include corresponding tests:

1. **Test File Naming**: Use `test_<module_name>.py` format in `tests/` directory
2. **Mock External APIs**: Never hit real Google APIs in tests - use mocks
3. **Test Error Paths**: Include tests for error conditions and edge cases
4. **Coverage Target**: Aim for >80% code coverage on new features
5. **Test Categories**:
   - Constructor/initialization tests
   - Core functionality tests
   - Error handling tests
   - Integration tests with mocks

#### Example Test Pattern
```python
"""Tests for NewModule."""

import pytest
from unittest.mock import Mock, patch
from meeting_notes_handler.new_module import NewClass


class TestNewClass:
    """Test cases for NewClass."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.instance = NewClass()
        
    def test_core_functionality(self):
        """Test core functionality with descriptive name."""
        # Arrange
        test_input = "test_data"
        expected_output = "expected_result"
        
        # Act
        result = self.instance.process(test_input)
        
        # Assert
        assert result == expected_output
        
    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        with pytest.raises(ValueError, match="Invalid input"):
            self.instance.process(None)
```

### Building and Linting

#### Using uv (Recommended)
```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run linting and formatting
uv run black meeting_notes_handler/
uv run isort meeting_notes_handler/
uv run flake8 meeting_notes_handler/

# Type checking (if mypy is installed)
uv run mypy meeting_notes_handler/

# Build package
uv run python -m build
```

#### Using standard pip
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run linting and formatting
black meeting_notes_handler/
isort meeting_notes_handler/
flake8 meeting_notes_handler/

# Build package
python -m build
```

#### Pre-commit Hooks (Recommended)
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass and code is properly formatted
5. Submit a pull request with a clear description

## 🔮 Roadmap

### ✅ Phase 1: Smart Content Processing (COMPLETED)
- **Smart content filtering** for recurring meetings
- **Document classification** (ephemeral vs persistent)
- **Automatic series detection** and tracking
- **Section-level content comparison** and diffing
- **LLM-optimized output** with content reduction

### ✅ Phase 2: AI-Powered Analysis (COMPLETED)
- **Multi-provider LLM integration** (OpenAI, Anthropic, Gemini, OpenRouter)
- **Weekly summary analysis** with key decisions and themes
- **Personal action item extraction** and discussion tracking
- **Smart relevance scoring** for personalized insights
- **Flexible output formats** (JSON, Markdown)

### Phase 3: Enhanced Intelligence
- **Cross-meeting pattern analysis** and trend detection
- **Action item tracking** with deadline monitoring
- **Meeting series insights** and optimization suggestions
- **Content similarity analysis** across different meeting series
- **Attendee analysis** and collaboration patterns
- **Topic clustering** and meeting effectiveness metrics

### Phase 4: Integration and Automation
- **Slack/Teams integration** for automatic sharing
- **Calendar integration** for action item scheduling
- **Email digest** of weekly meeting summaries
- **API endpoints** for custom integrations
- **Webhook support** for real-time processing

### Phase 5: User Experience
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