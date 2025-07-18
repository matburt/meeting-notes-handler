"""Tests for MeetingSeriesTracker."""

import pytest
import tempfile
import json
from datetime import datetime
from pathlib import Path
from meeting_notes_handler.series_tracker import MeetingSeriesTracker, MeetingFingerprint


class TestMeetingSeriesTracker:
    """Test cases for MeetingSeriesTracker."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.tracker = MeetingSeriesTracker(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_title_normalization(self):
        """Test meeting title normalization."""
        test_cases = [
            ("Weekly Standup - 2024/07/16", ""),  # All noise words removed
            ("Sprint Planning Week 29", ""),  # All noise words removed  
            ("Team Sync Meeting #3", "team 3"),  # Team and number remain, sync/meeting removed
            ("Daily Meeting - W30", ""),  # All noise words removed
            ("Project Review v2.1", "project"),  # Project remains, review removed
            ("Standup 09:00 AM", ""),  # All noise words removed
        ]
        
        for original, expected in test_cases:
            normalized = self.tracker._normalize_title(original)
            assert normalized == expected, f"Failed for title: {original} -> {normalized} (expected: {expected})"
    
    def test_meeting_fingerprint_generation(self):
        """Test meeting fingerprint generation."""
        meeting_metadata = {
            'title': 'Weekly Standup - 2024/07/16',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 16, 9, 0, 0),
            'attendees': ['alice@company.com', 'bob@company.com', 'charlie@company.com']
        }
        
        fingerprint = self.tracker._generate_fingerprint(meeting_metadata)
        
        assert fingerprint.normalized_title == ""  # All words are noise words
        assert fingerprint.organizer == "alice@company.com"
        assert fingerprint.time_pattern == "TUE-09:00"
        assert fingerprint.raw_title == "Weekly Standup - 2024/07/16"
        assert len(fingerprint.attendee_fingerprint) == 8  # MD5 hash first 8 chars
    
    def test_series_creation(self):
        """Test creating a new meeting series."""
        meeting_metadata = {
            'title': 'Weekly Standup',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 16, 9, 0, 0),
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        series_id = self.tracker.create_new_series(meeting_metadata)
        
        assert series_id is not None
        assert series_id in self.tracker.series_registry
        
        series_data = self.tracker.series_registry[series_id]
        assert series_data['normalized_title'] == ""  # All words are noise words
        assert series_data['organizer'] == "alice@company.com"
        assert series_data['time_pattern'] == "TUE-09:00"
        assert series_data['meeting_count'] == 1
    
    def test_series_identification(self):
        """Test identifying recurring meeting series."""
        # Create first meeting
        meeting1 = {
            'title': 'Weekly Standup - Week 29',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 16, 9, 0, 0),
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        # First meeting should create new series
        series_id1 = self.tracker.identify_series(meeting1)
        assert series_id1 is None  # Returns None for new series
        
        series_id1 = self.tracker.create_new_series(meeting1)
        
        # Second meeting with similar pattern should match
        meeting2 = {
            'title': 'Weekly Standup - Week 30',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 23, 9, 0, 0),  # Same day/time next week
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        series_id2 = self.tracker.identify_series(meeting2)
        assert series_id2 == series_id1  # Should match existing series
    
    def test_series_identification_different_organizer(self):
        """Test that meetings with different organizers don't match."""
        meeting1 = {
            'title': 'Weekly Standup',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 16, 9, 0, 0),
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        meeting2 = {
            'title': 'Weekly Standup',
            'organizer': 'bob@company.com',  # Different organizer
            'start_time': datetime(2024, 7, 16, 9, 0, 0),
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        series_id1 = self.tracker.create_new_series(meeting1)
        series_id2 = self.tracker.identify_series(meeting2)
        
        assert series_id2 is None  # Should not match due to different organizer
    
    def test_series_identification_different_time(self):
        """Test that meetings at different times don't match."""
        meeting1 = {
            'title': 'Weekly Standup',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 16, 9, 0, 0),  # 9 AM
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        meeting2 = {
            'title': 'Weekly Standup',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 16, 14, 0, 0),  # 2 PM
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        series_id1 = self.tracker.create_new_series(meeting1)
        series_id2 = self.tracker.identify_series(meeting2)
        
        assert series_id2 is None  # Should not match due to different time
    
    def test_meeting_file_registration(self):
        """Test adding meeting files to series."""
        meeting_metadata = {
            'title': 'Weekly Standup',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 16, 9, 0, 0),
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        series_id = self.tracker.create_new_series(meeting_metadata)
        
        # Add a meeting file
        meeting_file = "2024-W29/meeting_20240716_090000_standup.md"
        self.tracker.add_meeting_to_series(series_id, meeting_file)
        
        series_data = self.tracker.series_registry[series_id]
        assert meeting_file in series_data['meetings']
        assert series_data['meeting_count'] == 1
    
    def test_get_latest_meeting(self):
        """Test retrieving the latest meeting from a series."""
        meeting_metadata = {
            'title': 'Weekly Standup',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 16, 9, 0, 0),
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        series_id = self.tracker.create_new_series(meeting_metadata)
        
        # Add multiple meeting files
        meeting_files = [
            "2024-W28/meeting_20240709_090000_standup.md",
            "2024-W29/meeting_20240716_090000_standup.md",
            "2024-W30/meeting_20240723_090000_standup.md"
        ]
        
        for meeting_file in meeting_files:
            self.tracker.add_meeting_to_series(series_id, meeting_file)
        
        # Create actual files for testing
        for meeting_file in meeting_files:
            file_path = Path(self.temp_dir) / meeting_file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("test content")
        
        latest_meeting = self.tracker.get_latest_meeting(series_id)
        expected_path = str(Path(self.temp_dir) / meeting_files[-1])
        assert latest_meeting == expected_path
    
    def test_series_registry_persistence(self):
        """Test that series registry is saved and loaded correctly."""
        meeting_metadata = {
            'title': 'Weekly Standup',
            'organizer': 'alice@company.com',
            'start_time': datetime(2024, 7, 16, 9, 0, 0),
            'attendees': ['alice@company.com', 'bob@company.com']
        }
        
        series_id = self.tracker.create_new_series(meeting_metadata)
        
        # Create new tracker instance to test loading
        new_tracker = MeetingSeriesTracker(self.temp_dir)
        
        assert series_id in new_tracker.series_registry
        assert new_tracker.series_registry[series_id]['normalized_title'] == ""  # All words are noise words
    
    def test_attendee_fingerprint_stability(self):
        """Test that attendee fingerprints are stable."""
        attendees1 = ['alice@company.com', 'bob@company.com', 'charlie@company.com']
        attendees2 = ['charlie@company.com', 'alice@company.com', 'bob@company.com']  # Different order
        
        fingerprint1 = self.tracker._generate_attendee_fingerprint(attendees1)
        fingerprint2 = self.tracker._generate_attendee_fingerprint(attendees2)
        
        assert fingerprint1 == fingerprint2  # Should be same regardless of order
        assert len(fingerprint1) == 8  # Should be 8 characters
    
    def test_series_summary(self):
        """Test getting series summary."""
        # Create a few series
        for i in range(3):
            meeting_metadata = {
                'title': f'Meeting {i}',
                'organizer': f'user{i}@company.com',
                'start_time': datetime(2024, 7, 16, 9 + i, 0, 0),
                'attendees': [f'user{i}@company.com']
            }
            self.tracker.create_new_series(meeting_metadata)
        
        summary = self.tracker.get_series_summary()
        
        assert summary['total_series'] == 3
        assert len(summary['series']) == 3
        
        for series_info in summary['series']:
            assert 'series_id' in series_info
            assert 'title' in series_info
            assert 'organizer' in series_info
            assert 'meeting_count' in series_info