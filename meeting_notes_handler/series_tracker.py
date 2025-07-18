"""Meeting series tracking for identifying recurring meetings."""

import json
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class MeetingSeries:
    """Information about a meeting series."""
    series_id: str
    normalized_title: str
    organizer: str
    time_pattern: str  # e.g., "MON-09:00"
    attendee_pattern: List[str]  # Common attendees
    first_seen: str  # ISO date
    last_seen: str   # ISO date
    meeting_count: int
    meetings: List[str]  # List of meeting file paths
    confidence: float


@dataclass
class MeetingFingerprint:
    """Fingerprint for matching meetings to series."""
    normalized_title: str
    organizer: str
    time_pattern: str
    attendee_fingerprint: str
    raw_title: str


class MeetingSeriesTracker:
    """Tracks and identifies recurring meeting series."""
    
    def __init__(self, notes_directory: str):
        """Initialize the series tracker."""
        self.notes_dir = Path(notes_directory)
        self.series_registry_file = self.notes_dir / ".meeting_series_registry.json"
        self.series_registry = self._load_series_registry()
        
        # Words to ignore when normalizing titles
        self.title_noise_words = {
            'weekly', 'daily', 'monthly', 'meeting', 'sync', 'standup',
            'demo', 'review', 'planning', 'retrospective', 'retro',
            'sprint', 'scrum', 'session', 'call', 'discussion'
        }
        
        # Date/number patterns to remove from titles
        self.title_cleanup_patterns = [
            r'\b\d{4}[-/]\d{2}[-/]\d{2}\b',  # Dates: 2024-07-16
            r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',  # Dates: 7/16/24
            r'\bweek\s+\d+\b',               # Week numbers
            r'\bw\d+\b',                     # W29, W30
            r'\bsprint\s+\d+\b',            # Sprint numbers
            r'\b#\d+\b',                     # Issue numbers
            r'\bv\d+\.\d+\b',               # Version numbers
            r'\b\d{1,2}:\d{2}\s*(?:am|pm)?\b',  # Times
        ]
    
    def identify_series(self, meeting_metadata: Dict) -> Optional[str]:
        """
        Identify which series this meeting belongs to.
        
        Args:
            meeting_metadata: Meeting metadata dict
            
        Returns:
            Series ID if match found, None if new series needed
        """
        fingerprint = self._generate_fingerprint(meeting_metadata)
        
        # Check existing series for matches
        for series_id, series_data in self.series_registry.items():
            if self._matches_series(fingerprint, series_data):
                # Update series with this meeting
                self._add_meeting_to_series(series_id, meeting_metadata)
                return series_id
        
        # No match found - this is a new series
        return None
    
    def create_new_series(self, meeting_metadata: Dict) -> str:
        """
        Create a new meeting series.
        
        Args:
            meeting_metadata: Meeting metadata dict
            
        Returns:
            New series ID
        """
        fingerprint = self._generate_fingerprint(meeting_metadata)
        series_id = self._generate_series_id(fingerprint)
        
        # Create new series entry
        series = MeetingSeries(
            series_id=series_id,
            normalized_title=fingerprint.normalized_title,
            organizer=fingerprint.organizer,
            time_pattern=fingerprint.time_pattern,
            attendee_pattern=self._extract_attendee_pattern(meeting_metadata),
            first_seen=meeting_metadata['start_time'] if isinstance(meeting_metadata['start_time'], str) else meeting_metadata['start_time'].isoformat(),
            last_seen=meeting_metadata['start_time'] if isinstance(meeting_metadata['start_time'], str) else meeting_metadata['start_time'].isoformat(),
            meeting_count=1,
            meetings=[],  # Will be filled when file is saved
            confidence=1.0
        )
        
        self.series_registry[series_id] = asdict(series)
        self._save_series_registry()
        
        logger.info(f"Created new meeting series: {series_id} for '{fingerprint.raw_title}'")
        return series_id
    
    def get_latest_meeting(self, series_id: str) -> Optional[str]:
        """
        Get the path to the most recent meeting in a series.
        
        Args:
            series_id: Series identifier
            
        Returns:
            Path to latest meeting file, or None if not found
        """
        if series_id not in self.series_registry:
            return None
        
        series_data = self.series_registry[series_id]
        meetings = series_data.get('meetings', [])
        
        if not meetings:
            return None
        
        # Meetings should be stored in chronological order
        # Return the most recent one
        latest_meeting = meetings[-1]
        
        # Verify file exists
        meeting_path = self.notes_dir / latest_meeting
        if meeting_path.exists():
            return str(meeting_path)
        
        logger.warning(f"Latest meeting file not found: {meeting_path}")
        return None
    
    def get_series_meetings(self, series_id: str, limit: Optional[int] = None) -> List[str]:
        """
        Get all meetings in a series.
        
        Args:
            series_id: Series identifier
            limit: Maximum number of meetings to return (most recent first)
            
        Returns:
            List of meeting file paths
        """
        if series_id not in self.series_registry:
            return []
        
        meetings = self.series_registry[series_id].get('meetings', [])
        
        if limit:
            meetings = meetings[-limit:]  # Get most recent N meetings
        
        # Verify files exist and return full paths
        existing_meetings = []
        for meeting_file in meetings:
            meeting_path = self.notes_dir / meeting_file
            if meeting_path.exists():
                existing_meetings.append(str(meeting_path))
        
        return existing_meetings
    
    def add_meeting_to_series(self, series_id: str, meeting_file_path: str):
        """
        Add a meeting file to an existing series.
        
        Args:
            series_id: Series identifier  
            meeting_file_path: Relative path to meeting file from notes directory
        """
        if series_id not in self.series_registry:
            logger.error(f"Series {series_id} not found")
            return
        
        # Convert to relative path if absolute
        meeting_path = Path(meeting_file_path)
        if meeting_path.is_absolute():
            try:
                relative_path = meeting_path.relative_to(self.notes_dir)
            except ValueError:
                logger.error(f"Meeting file {meeting_file_path} is not within notes directory")
                return
        else:
            relative_path = meeting_path
        
        # Add to series
        series_data = self.series_registry[series_id]
        if str(relative_path) not in series_data['meetings']:
            series_data['meetings'].append(str(relative_path))
            series_data['meeting_count'] = len(series_data['meetings'])
            
            # Update last_seen
            # Would need meeting metadata to get accurate timestamp
            series_data['last_seen'] = datetime.now().isoformat()
            
            self._save_series_registry()
            logger.debug(f"Added meeting {relative_path} to series {series_id}")
    
    def _generate_fingerprint(self, meeting_metadata: Dict) -> MeetingFingerprint:
        """Generate a fingerprint for meeting series matching."""
        
        raw_title = meeting_metadata.get('title', '')
        normalized_title = self._normalize_title(raw_title)
        organizer = meeting_metadata.get('organizer', '')
        
        # Extract time pattern (day of week + hour)
        start_time = meeting_metadata.get('start_time')
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        
        time_pattern = f"{start_time.strftime('%a').upper()}-{start_time.strftime('%H:%M')}"
        
        # Create attendee fingerprint
        attendees = meeting_metadata.get('attendees', [])
        attendee_fingerprint = self._generate_attendee_fingerprint(attendees)
        
        return MeetingFingerprint(
            normalized_title=normalized_title,
            organizer=organizer,
            time_pattern=time_pattern,
            attendee_fingerprint=attendee_fingerprint,
            raw_title=raw_title
        )
    
    def _normalize_title(self, title: str) -> str:
        """Normalize meeting title for comparison."""
        if not title:
            return ""
        
        # Convert to lowercase
        normalized = title.lower()
        
        # Remove date/time patterns
        for pattern in self.title_cleanup_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Remove common noise words
        words = normalized.split()
        filtered_words = [word for word in words if word not in self.title_noise_words]
        
        # Clean up spacing and punctuation
        normalized = ' '.join(filtered_words)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _generate_attendee_fingerprint(self, attendees: List[str]) -> str:
        """Generate a stable fingerprint from attendee list."""
        if not attendees:
            return ""
        
        # Sort attendees and take a hash
        sorted_attendees = sorted([email.lower() for email in attendees if email])
        attendee_string = '|'.join(sorted_attendees)
        
        # Return first 8 chars of hash for compactness
        return hashlib.md5(attendee_string.encode()).hexdigest()[:8]
    
    def _extract_attendee_pattern(self, meeting_metadata: Dict) -> List[str]:
        """Extract consistent attendee pattern for series."""
        attendees = meeting_metadata.get('attendees', [])
        # For now, just return all attendees
        # Could be enhanced to identify "core" attendees vs occasional ones
        return sorted([email.lower() for email in attendees if email])
    
    def _generate_series_id(self, fingerprint: MeetingFingerprint) -> str:
        """Generate a unique series ID from fingerprint."""
        # Create readable but unique ID
        title_part = fingerprint.normalized_title[:20] if fingerprint.normalized_title else "meeting"
        title_part = re.sub(r'[^\w]', '_', title_part)
        
        organizer_part = fingerprint.organizer.split('@')[0] if '@' in fingerprint.organizer else fingerprint.organizer
        organizer_part = organizer_part[:10]
        
        time_part = fingerprint.time_pattern.lower().replace(':', '')
        
        base_id = f"{title_part}_{organizer_part}_{time_part}"
        
        # Add hash suffix to ensure uniqueness
        full_string = f"{fingerprint.normalized_title}:{fingerprint.organizer}:{fingerprint.time_pattern}:{fingerprint.attendee_fingerprint}"
        hash_suffix = hashlib.md5(full_string.encode()).hexdigest()[:6]
        
        return f"{base_id}_{hash_suffix}"
    
    def _matches_series(self, fingerprint: MeetingFingerprint, series_data: Dict) -> bool:
        """Check if a fingerprint matches an existing series."""
        
        # Check organizer (should be exact match)
        if fingerprint.organizer != series_data.get('organizer', ''):
            return False
        
        # Check time pattern (should be exact match)
        if fingerprint.time_pattern != series_data.get('time_pattern', ''):
            return False
        
        # Check title similarity
        series_title = series_data.get('normalized_title', '')
        title_similarity = self._calculate_title_similarity(fingerprint.normalized_title, series_title)
        
        # Require high title similarity for match
        if title_similarity < 0.8:
            return False
        
        return True
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two normalized titles."""
        if not title1 or not title2:
            return 0.0 if title1 != title2 else 1.0
        
        # Simple word overlap similarity
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _add_meeting_to_series(self, series_id: str, meeting_metadata: Dict):
        """Update series data with new meeting information."""
        series_data = self.series_registry[series_id]
        
        # Update last_seen
        series_data['last_seen'] = meeting_metadata['start_time'].isoformat()
        
        # Note: meeting file path will be added later via add_meeting_to_series
        # when the file is actually saved
    
    def _load_series_registry(self) -> Dict:
        """Load the series registry from file."""
        if not self.series_registry_file.exists():
            return {}
        
        try:
            with open(self.series_registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Error loading series registry: {e}")
            return {}
    
    def _save_series_registry(self):
        """Save the series registry to file."""
        try:
            # Ensure directory exists
            self.series_registry_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.series_registry_file, 'w', encoding='utf-8') as f:
                json.dump(self.series_registry, f, indent=2, ensure_ascii=False)
                
        except OSError as e:
            logger.error(f"Error saving series registry: {e}")
    
    def get_all_series(self) -> Dict:
        """Get all tracked meeting series."""
        return self.series_registry.copy()
    
    def get_series_summary(self) -> Dict:
        """Get a summary of all tracked series."""
        summary = {
            'total_series': len(self.series_registry),
            'series': []
        }
        
        for series_id, series_data in self.series_registry.items():
            summary['series'].append({
                'series_id': series_id,
                'title': series_data.get('normalized_title', ''),
                'organizer': series_data.get('organizer', ''),
                'meeting_count': series_data.get('meeting_count', 0),
                'last_seen': series_data.get('last_seen', ''),
                'time_pattern': series_data.get('time_pattern', '')
            })
        
        return summary