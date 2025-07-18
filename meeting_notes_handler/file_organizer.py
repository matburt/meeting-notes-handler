"""File organization utilities for meeting notes."""

import os
import yaml
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, Optional, Set, List
import logging

logger = logging.getLogger(__name__)

class FileOrganizer:
    """Organizes meeting notes files by week."""
    
    def __init__(self, base_directory: Path):
        """Initialize the file organizer.
        
        Args:
            base_directory: Base directory for storing meeting notes.
        """
        self.base_directory = Path(base_directory)
        self.base_directory.mkdir(parents=True, exist_ok=True)
    
    def get_week_directory(self, meeting_date: date) -> Path:
        """Get the directory for a given meeting date's week.
        
        Args:
            meeting_date: Date of the meeting.
            
        Returns:
            Path to the week directory (YYYY-WW format).
        """
        year, week, _ = meeting_date.isocalendar()
        week_dir = self.base_directory / f"{year}-W{week:02d}"
        week_dir.mkdir(parents=True, exist_ok=True)
        return week_dir
    
    def generate_filename(self, meeting_date: datetime, title: Optional[str] = None) -> str:
        """Generate a filename for a meeting note.
        
        Args:
            meeting_date: DateTime of the meeting.
            title: Optional meeting title to include in filename.
            
        Returns:
            Generated filename.
        """
        date_str = meeting_date.strftime("%Y%m%d")
        time_str = meeting_date.strftime("%H%M%S")
        
        if title:
            # Clean title for filename
            clean_title = self._clean_title(title)
            return f"meeting_{date_str}_{time_str}_{clean_title}.md"
        else:
            return f"meeting_{date_str}_{time_str}.md"
    
    def _clean_title(self, title: str) -> str:
        """Clean a title for use in a filename.
        
        Args:
            title: Meeting title to clean.
            
        Returns:
            Cleaned title suitable for filename.
        """
        # Remove or replace problematic characters
        clean = title.lower()
        clean = "".join(c if c.isalnum() or c in " -_" else "" for c in clean)
        clean = "_".join(clean.split())  # Replace spaces with underscores
        return clean[:50]  # Limit length
    
    def get_file_path(self, meeting_date: datetime, title: Optional[str] = None) -> Path:
        """Get the full file path for a meeting note.
        
        Args:
            meeting_date: DateTime of the meeting.
            title: Optional meeting title.
            
        Returns:
            Full path where the meeting note should be saved.
        """
        week_dir = self.get_week_directory(meeting_date.date())
        filename = self.generate_filename(meeting_date, title)
        return week_dir / filename
    
    def save_meeting_note(self, content: str, meeting_date: datetime, 
                         title: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Path:
        """Save a meeting note to the organized directory structure.
        
        Args:
            content: Meeting note content in markdown format.
            meeting_date: DateTime of the meeting.
            title: Optional meeting title.
            metadata: Optional metadata to include in the file header.
            
        Returns:
            Path where the file was saved.
        """
        file_path = self.get_file_path(meeting_date, title)
        
        # Prepare the full content with metadata
        full_content = self._prepare_content(content, meeting_date, title, metadata)
        
        # Write the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(full_content)
        
        logger.info(f"Saved meeting note to {file_path}")
        return file_path
    
    def _prepare_content(self, content: str, meeting_date: datetime, 
                        title: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Prepare the full content including metadata header.
        
        Args:
            content: Meeting note content.
            meeting_date: DateTime of the meeting.
            title: Optional meeting title.
            metadata: Optional additional metadata.
            
        Returns:
            Full content with metadata header.
        """
        lines = []
        
        # Add metadata header
        lines.append("---")
        lines.append(f"date: {meeting_date.isoformat()}")
        if title:
            lines.append(f"title: {title}")
        lines.append(f"week: {meeting_date.date().isocalendar()[0]}-W{meeting_date.date().isocalendar()[1]:02d}")
        
        if metadata:
            for key, value in metadata.items():
                lines.append(f"{key}: {value}")
        
        lines.append("---")
        lines.append("")
        
        # Add title as H1 if provided
        if title:
            lines.append(f"# {title}")
            lines.append("")
        
        # Add the main content
        lines.append(content)
        
        return "\n".join(lines)
    
    def list_weeks(self) -> list[str]:
        """List all week directories that exist.
        
        Returns:
            List of week directory names (YYYY-WW format).
        """
        if not self.base_directory.exists():
            return []
        
        weeks = []
        for item in self.base_directory.iterdir():
            if item.is_dir() and item.name.match(r"^\d{4}-W\d{2}$"):
                weeks.append(item.name)
        
        return sorted(weeks)
    
    def list_meetings_in_week(self, week: str) -> list[Path]:
        """List all meeting files in a specific week.
        
        Args:
            week: Week in YYYY-WW format.
            
        Returns:
            List of meeting file paths.
        """
        week_dir = self.base_directory / week
        if not week_dir.exists():
            return []
        
        meetings = []
        for item in week_dir.iterdir():
            if item.is_file() and item.suffix == ".md":
                meetings.append(item)
        
        return sorted(meetings)
    
    def is_meeting_already_processed(self, meeting_id: str, docs_links: List[str]) -> bool:
        """Check if a meeting with these docs has already been processed.
        
        Args:
            meeting_id: Google Calendar meeting ID.
            docs_links: List of document URLs for this meeting.
            
        Returns:
            True if meeting already exists with same or more docs.
        """
        try:
            # Find any existing file with this meeting ID
            existing_file = self._find_meeting_file(meeting_id)
            if not existing_file:
                return False
            
            # Read the existing file's metadata
            existing_metadata = self._read_file_metadata(existing_file)
            if not existing_metadata:
                return False
            
            existing_docs = existing_metadata.get('docs_links', [])
            if isinstance(existing_docs, str):
                # Handle single doc as string
                existing_docs = [existing_docs]
            
            # Convert sets for comparison
            new_docs_set = set(docs_links)
            existing_docs_set = set(existing_docs)
            
            # If existing file has same or more docs, consider it already processed
            if new_docs_set.issubset(existing_docs_set):
                logger.info(f"Meeting {meeting_id} already processed with same docs")
                return True
            
            # If new docs are different/additional, we should reprocess
            if new_docs_set != existing_docs_set:
                logger.info(f"Meeting {meeting_id} has new/different docs - will reprocess")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error checking if meeting {meeting_id} already processed: {e}")
            return False
    
    def _find_meeting_file(self, meeting_id: str) -> Optional[Path]:
        """Find a meeting file by meeting ID.
        
        Args:
            meeting_id: Google Calendar meeting ID.
            
        Returns:
            Path to the meeting file if found, None otherwise.
        """
        if not self.base_directory.exists():
            return None
        
        # Search through all week directories
        for week_dir in self.base_directory.iterdir():
            if not week_dir.is_dir():
                continue
                
            for meeting_file in week_dir.glob("*.md"):
                try:
                    metadata = self._read_file_metadata(meeting_file)
                    if metadata and metadata.get('meeting_id') == meeting_id:
                        return meeting_file
                except Exception as e:
                    logger.debug(f"Error reading metadata from {meeting_file}: {e}")
                    continue
        
        return None
    
    def _read_file_metadata(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Read YAML metadata from a meeting file.
        
        Args:
            file_path: Path to the meeting file.
            
        Returns:
            Dictionary with metadata, or None if not found.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract YAML frontmatter
            if content.startswith('---\n'):
                end_marker = content.find('\n---\n', 4)
                if end_marker != -1:
                    yaml_content = content[4:end_marker]
                    return yaml.safe_load(yaml_content)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error reading metadata from {file_path}: {e}")
            return None
    
    def get_processed_meeting_ids(self) -> Set[str]:
        """Get all meeting IDs that have already been processed.
        
        Returns:
            Set of meeting IDs that have been processed.
        """
        processed_ids = set()
        
        if not self.base_directory.exists():
            return processed_ids
        
        # Search through all week directories
        for week_dir in self.base_directory.iterdir():
            if not week_dir.is_dir():
                continue
                
            for meeting_file in week_dir.glob("*.md"):
                try:
                    metadata = self._read_file_metadata(meeting_file)
                    if metadata and metadata.get('meeting_id'):
                        processed_ids.add(metadata['meeting_id'])
                except Exception as e:
                    logger.debug(f"Error reading metadata from {meeting_file}: {e}")
                    continue
        
        return processed_ids