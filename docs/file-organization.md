# Meeting Notes File Organization & Format Specification

This document provides comprehensive documentation of how meeting notes are organized, stored, and formatted by the Meeting Notes Handler.

## 📁 Directory Structure Overview

The Meeting Notes Handler organizes all files in a structured hierarchy based on ISO weeks and meeting series. Here's the complete topology:

```
meeting_notes/                           # Base output directory (configurable)
├── 2024-W29/                           # ISO Week directory (YYYY-WDD format)
│   ├── meeting_20240715_140000_sprint_planning.md
│   ├── meeting_20240717_090000_team_standup.md
│   └── meeting_20240719_100000_architecture_review.md
├── 2024-W30/                           # Next week
│   ├── meeting_20240722_140000_sprint_planning.md
│   ├── meeting_20240724_090000_team_standup.md
│   └── meeting_20240726_100000_architecture_review.md
├── .meeting_series_registry.json       # Series tracking metadata (hidden)
└── .meeting_content_cache/              # Content diffing cache (hidden)
    ├── sprint_planning_alice_mon1400_abc123/
    │   ├── 2024-07-15_content.json.gz
    │   ├── 2024-07-22_content.json.gz
    │   └── 2024-07-29_content.json.gz
    ├── team_standup_bob_wed0900_def456/
    │   ├── 2024-07-17_content.json.gz
    │   ├── 2024-07-24_content.json.gz
    │   └── 2024-07-31_content.json.gz
    └── arch_review_carol_fri1000_ghi789/
        ├── 2024-07-19_content.json.gz
        ├── 2024-07-26_content.json.gz
        └── 2024-08-02_content.json.gz
```

## 📂 Directory Organization Details

### Week Directories (`YYYY-WDD`)

- **Format**: ISO 8601 week numbering (e.g., `2024-W29`, `2024-W52`)
- **Purpose**: Groups meetings by calendar week for easy chronological browsing
- **Creation**: Automatically created when first meeting of the week is saved
- **Sorting**: Naturally sorts chronologically due to YYYY-WDD format

**Week Calculation Example**:
```python
# Meeting on July 15, 2024 (Monday)
year, week, weekday = datetime(2024, 7, 15).isocalendar()
# Result: year=2024, week=29, weekday=1
# Directory: "2024-W29"
```

### Hidden Metadata Directories

#### `.meeting_series_registry.json`
- **Purpose**: Tracks recurring meeting series for diffing functionality
- **Format**: JSON with series fingerprints and metadata
- **Location**: Root of meeting notes directory

#### `.meeting_content_cache/`
- **Purpose**: Stores content signatures for diffing and change detection
- **Structure**: One subdirectory per meeting series
- **Compression**: Files are gzip-compressed JSON

## 📄 Meeting Note File Format

### Filename Convention

```
meeting_YYYYMMDD_HHMMSS_cleaned_title.md
```

**Components**:
- `meeting_` - Fixed prefix
- `YYYYMMDD` - Date in ISO format (e.g., `20240715`)
- `HHMMSS` - Time in 24-hour format (e.g., `140000` for 2:00 PM)
- `cleaned_title` - Meeting title with special characters removed, spaces → underscores
- `.md` - Markdown file extension

**Title Cleaning Rules**:
- Convert to lowercase
- Keep only alphanumeric characters, spaces, hyphens, underscores
- Replace spaces with underscores
- Truncate to 50 characters maximum

**Examples**:
```
"Sprint Planning - July 2024" → "sprint_planning_july_2024"
"Team Standup #47" → "team_standup_47"
"Architecture Review: Q3 Goals" → "architecture_review_q3_goals"
```

### File Content Structure

Each meeting note file follows this standardized format:

```markdown
---
date: 2024-07-15T14:00:00+00:00
title: Sprint Planning - July 2024
week: 2024-W29
meeting_id: c_abcd1234567890@google.com
organizer: alice@company.com
attendees_count: 8
docs_count: 2
docs_links:
  - https://docs.google.com/document/d/1abc.../edit
  - https://docs.google.com/document/d/2def.../edit
---

# Sprint Planning - July 2024

**Date:** 2024-07-15 14:00
**Organizer:** alice@company.com
**Attendees:** alice@company.com, bob@company.com, carol@company.com, dave@company.com, eve@company.com, frank@company.com, grace@company.com, henry@company.com
**Meeting Link:** https://meet.google.com/abc-defg-hij

## Document 1
**Title:** Sprint 23 Planning Notes

### Sprint Goals
- Complete user authentication system
- Implement API rate limiting
- Deploy staging environment

### Team Capacity
- 8 developers available
- 2 developers on vacation next week
- Estimated 60 story points capacity

## Document 2
**Title:** Technical Architecture Decisions

### Database Migration
We decided to migrate from MySQL to PostgreSQL for better JSON support and performance.

### Deployment Strategy
Rolling deployment with blue-green strategy for zero downtime.
```

## 📋 YAML Front Matter Specification

Every meeting note includes a YAML front matter header with standardized metadata:

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `date` | ISO 8601 DateTime | Meeting start time with timezone | `2024-07-15T14:00:00+00:00` |
| `title` | String | Original meeting title from calendar | `Sprint Planning - July 2024` |
| `week` | String | ISO week identifier | `2024-W29` |

### Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `meeting_id` | String | Google Calendar event ID | `c_abcd1234567890@google.com` |
| `organizer` | String | Meeting organizer email | `alice@company.com` |
| `attendees_count` | Integer | Number of meeting attendees | `8` |
| `docs_count` | Integer | Number of documents processed | `2` |
| `docs_links` | Array | URLs of processed documents | `[url1, url2]` |

### Custom Metadata
Additional fields may be present based on meeting-specific information or future enhancements.

## 📝 Content Body Structure

### Meeting Information Section
Always includes standardized meeting metadata:
```markdown
**Date:** 2024-07-15 14:00
**Organizer:** alice@company.com
**Attendees:** alice@company.com, bob@company.com, carol@company.com
**Meeting Link:** https://meet.google.com/abc-defg-hij
```

### Document Sections
When multiple documents are processed, each gets its own section:
```markdown
## Document 1
**Title:** Original Document Title

[Document content...]

## Document 2
**Title:** Another Document Title

[Document content...]
```

### Content Processing
- **Gemini Notes**: AI-generated meeting summaries and transcripts
- **Manual Notes**: User-created Google Docs, Sheets, or Slides
- **Smart Filtering**: Processed content with duplicates and boilerplate removed
- **Native Export**: High-quality conversion using Google's native export APIs

## 🔍 Content Diffing Cache Format

### Cache Directory Structure
```
.meeting_content_cache/
└── {series_id}/                    # Unique identifier for meeting series
    ├── 2024-07-15_content.json.gz  # Compressed content signature
    ├── 2024-07-22_content.json.gz
    └── 2024-07-29_content.json.gz
```

### Series ID Format
```
{normalized_title}_{organizer}_{time_pattern}_{hash}
```

**Example**: `sprint_planning_alice_mon1400_abc123`

**Components**:
- `normalized_title` - Cleaned meeting title (max 20 chars)
- `organizer` - Organizer username (before @, max 10 chars)
- `time_pattern` - Day of week + time (e.g., `mon1400` for Monday 2:00 PM)
- `hash` - 6-character MD5 hash for uniqueness

### Content Signature Schema
```json
{
  "meeting_id": "sprint_planning_alice_mon1400_abc123_2024-07-15",
  "content_version": "1.0",
  "extracted_at": "2024-07-15T14:30:00Z",
  "full_content_hash": "sha256:abcd1234...",
  "total_words": 847,
  "total_paragraphs": 23,
  "sections": [
    {
      "header": "Sprint Goals",
      "header_hash": "sha256:5678efgh...",
      "position": 0,
      "paragraphs": [
        {
          "hash": "sha256:9012ijkl...",
          "content": "Complete user authentication system",
          "preview": "Complete user authentication system",
          "word_count": 4,
          "position": 0
        }
      ]
    }
  ]
}
```

## 📊 Series Registry Schema

The `.meeting_series_registry.json` file tracks recurring meetings:

```json
{
  "sprint_planning_alice_mon1400_abc123": {
    "series_id": "sprint_planning_alice_mon1400_abc123",
    "normalized_title": "sprint planning",
    "organizer": "alice@company.com",
    "time_pattern": "MON-14:00",
    "attendee_pattern": ["alice@company.com", "bob@company.com", "carol@company.com"],
    "first_seen": "2024-06-17T14:00:00Z",
    "last_seen": "2024-07-29T14:00:00Z",
    "meeting_count": 7,
    "meetings": [
      "2024-W25/meeting_20240617_140000_sprint_planning.md",
      "2024-W26/meeting_20240624_140000_sprint_planning.md",
      "2024-W27/meeting_20240701_140000_sprint_planning.md",
      "2024-W28/meeting_20240708_140000_sprint_planning.md",
      "2024-W29/meeting_20240715_140000_sprint_planning.md",
      "2024-W30/meeting_20240722_140000_sprint_planning.md",
      "2024-W31/meeting_20240729_140000_sprint_planning.md"
    ],
    "confidence": 1.0
  }
}
```

### Series Detection Algorithm
Meeting series are identified by comparing:
1. **Normalized title** - Similarity > 80%
2. **Organizer** - Exact match
3. **Time pattern** - Exact match (day + time)
4. **Attendee fingerprint** - MD5 hash of sorted attendee list

## 🧹 File Management & Cleanup

### Automatic Cleanup
- **Content cache**: Entries older than 180 days are automatically archived
- **Empty directories**: Removed when no meetings remain
- **Compression**: Content signatures are gzip-compressed to save space

### Manual Maintenance
```bash
# Clean up old cache entries (older than 90 days)
meeting-notes cache-cleanup --days 90

# Get cache statistics
meeting-notes cache-stats

# List all tracked series
meeting-notes list-series
```

## 🔧 Configuration Impact on Organization

### Configurable Paths
```yaml
# config.yaml
output:
  directory: "/path/to/meeting_notes"  # Base directory for all files

google:
  credentials_file: "~/.config/meeting-notes/credentials.json"
  token_file: "~/.config/meeting-notes/token.json"
```

### Environment Variables
```bash
MEETING_NOTES_OUTPUT_DIR="/custom/path"
MEETING_NOTES_CACHE_COMPRESSION=true
MEETING_NOTES_CLEANUP_DAYS=180
```

## 📈 Usage Patterns & Best Practices

### Recommended Directory Structure
```bash
# Organized by project/team
meeting_notes/
├── team-alpha/          # Team-specific notes
├── team-beta/           # Another team
└── company-wide/        # All-hands, etc.
```

### Integration Patterns
```bash
# Daily sync to shared storage
rsync -av meeting_notes/ /shared/team-notes/

# Weekly cleanup and archival
find meeting_notes/ -name "*.md" -mtime +365 -exec gzip {} \;

# Backup content cache
tar -czf backup-$(date +%Y%m%d).tar.gz .meeting_content_cache/
```

## 🚨 Important Notes

### File Safety
- Never manually edit cache files - they are managed automatically
- Meeting note `.md` files are safe to edit manually
- Registry files are rebuilt if corrupted

### Performance Considerations
- Cache directory grows over time - monitor disk usage
- Compressed cache files are ~10% of original size
- Large meetings (>1000 paragraphs) may impact diff performance

### Compatibility
- All files use UTF-8 encoding
- Markdown follows CommonMark specification
- YAML front matter compatible with Jekyll, Hugo, and other static site generators
- JSON cache files follow semantic versioning for compatibility

---

This organization system ensures consistent, discoverable, and maintainable meeting notes while supporting advanced features like content diffing and change tracking.