"""Tests for MeetingContentCache."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from meeting_notes_handler.content_cache import MeetingContentCache
from meeting_notes_handler.content_hasher import ContentHasher


class TestMeetingContentCache:
    """Test cases for MeetingContentCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = MeetingContentCache(self.temp_dir)
        self.hasher = ContentHasher()
        
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_store_and_retrieve_signature(self):
        """Test storing and retrieving content signatures."""
        content = """# Meeting Notes
- Action item 1
- Action item 2"""
        
        signature = self.hasher.create_content_signature(
            "test_meeting", content, datetime.now().isoformat()
        )
        
        # Store signature
        success = self.cache.store_content_signature("series_123", "2024-07-22", signature)
        assert success
        
        # Retrieve signature
        retrieved = self.cache.get_content_signature("series_123", "2024-07-22")
        assert retrieved is not None
        assert retrieved.meeting_id == signature.meeting_id
        assert retrieved.full_content_hash == signature.full_content_hash
        assert len(retrieved.sections) == len(signature.sections)
        
    def test_signature_not_found(self):
        """Test retrieving non-existent signature."""
        result = self.cache.get_content_signature("nonexistent_series", "2024-07-22")
        assert result is None
        
    def test_has_content_signature(self):
        """Test checking signature existence."""
        content = """# Test Content"""
        signature = self.hasher.create_content_signature(
            "test_meeting", content, datetime.now().isoformat()
        )
        
        # Should not exist initially
        assert not self.cache.has_content_signature("series_123", "2024-07-22")
        
        # Store signature
        self.cache.store_content_signature("series_123", "2024-07-22", signature)
        
        # Should exist now
        assert self.cache.has_content_signature("series_123", "2024-07-22")
        
    def test_get_latest_signatures(self):
        """Test retrieving latest signatures for a series."""
        # Create multiple signatures
        dates = ["2024-07-20", "2024-07-21", "2024-07-22"]
        
        for i, date in enumerate(dates):
            content = f"# Meeting {i+1}\n- Content for meeting {i+1}"
            signature = self.hasher.create_content_signature(
                f"meeting_{i+1}", content, datetime.now().isoformat()
            )
            self.cache.store_content_signature("series_123", date, signature)
        
        # Get latest 2 signatures
        latest = self.cache.get_latest_signatures("series_123", limit=2)
        
        assert len(latest) == 2
        # Should be in reverse chronological order (most recent first)
        assert latest[0].meeting_id == "meeting_3"
        assert latest[1].meeting_id == "meeting_2"
        
    def test_cache_directory_creation(self):
        """Test that cache directories are created properly."""
        content = """# Test Content"""
        signature = self.hasher.create_content_signature(
            "test_meeting", content, datetime.now().isoformat()
        )
        
        # Store signature for new series
        self.cache.store_content_signature("new_series", "2024-07-22", signature)
        
        # Check that directory structure was created
        cache_dir = Path(self.temp_dir) / ".meeting_content_cache"
        series_dir = cache_dir / "new_series"
        
        assert cache_dir.exists()
        assert series_dir.exists()
        
    def test_cache_statistics(self):
        """Test cache statistics generation."""
        # Create signatures for multiple series
        for series_id in ["series_1", "series_2"]:
            for i in range(3):
                content = f"# Content for {series_id} meeting {i}"
                signature = self.hasher.create_content_signature(
                    f"{series_id}_meeting_{i}", content, datetime.now().isoformat()
                )
                date = f"2024-07-{20+i:02d}"
                self.cache.store_content_signature(series_id, date, signature)
        
        stats = self.cache.get_cache_statistics()
        
        assert stats['total_series'] == 2
        assert stats['total_signatures'] == 6
        assert stats['total_size_bytes'] > 0
        assert 'series_1' in stats['series_details']
        assert 'series_2' in stats['series_details']
        assert stats['series_details']['series_1']['signature_count'] == 3
        assert stats['series_details']['series_2']['signature_count'] == 3
        
    def test_compression_handling(self):
        """Test that compression works correctly."""
        # Force compression on
        self.cache.use_compression = True
        
        content = """# Large Content
This is a larger piece of content that should benefit from compression.
It contains multiple lines and repeated words that should compress well.
Compression compression compression should reduce the file size significantly."""
        
        signature = self.hasher.create_content_signature(
            "test_meeting", content, datetime.now().isoformat()
        )
        
        # Store with compression
        success = self.cache.store_content_signature("series_123", "2024-07-22", signature)
        assert success
        
        # Retrieve and verify
        retrieved = self.cache.get_content_signature("series_123", "2024-07-22")
        assert retrieved is not None
        assert retrieved.meeting_id == signature.meeting_id
        
        # Check that compressed file exists
        cache_dir = Path(self.temp_dir) / ".meeting_content_cache" / "series_123"
        compressed_file = cache_dir / "2024-07-22_content.json.gz"
        assert compressed_file.exists()
        
    def test_data_integrity_after_roundtrip(self):
        """Test that data remains intact after store/retrieve cycle."""
        content = """# Comprehensive Meeting Notes

## Action Items
- Alice to review the documentation thoroughly
- Bob to update the API endpoints
- Carol to prepare the deployment pipeline

## Decisions Made
- Use PostgreSQL 15 for the database
- Deploy to AWS ECS for containerization
- Implement rate limiting at 1000 requests/minute

## Discussion Points
**Performance Optimization**
We discussed various approaches to optimize the system performance.
The team agreed that caching would be the most effective immediate improvement.

**Security Considerations**  
Authentication should use OAuth 2.0 with JWT tokens.
All API endpoints must be protected with proper authorization checks."""
        
        signature = self.hasher.create_content_signature(
            "comprehensive_meeting", content, "2024-07-22T14:30:00Z"
        )
        
        # Store signature
        self.cache.store_content_signature("weekly_standup", "2024-07-22", signature)
        
        # Retrieve signature
        retrieved = self.cache.get_content_signature("weekly_standup", "2024-07-22")
        
        # Verify all fields
        assert retrieved.meeting_id == signature.meeting_id
        assert retrieved.content_version == signature.content_version
        assert retrieved.extracted_at == signature.extracted_at
        assert retrieved.full_content_hash == signature.full_content_hash
        assert retrieved.total_words == signature.total_words
        assert retrieved.total_paragraphs == signature.total_paragraphs
        assert len(retrieved.sections) == len(signature.sections)
        
        # Verify section integrity
        for orig_section, retr_section in zip(signature.sections, retrieved.sections):
            assert orig_section.header == retr_section.header
            assert orig_section.header_hash == retr_section.header_hash
            assert orig_section.position == retr_section.position
            assert len(orig_section.paragraphs) == len(retr_section.paragraphs)
            
            # Verify paragraph integrity
            for orig_para, retr_para in zip(orig_section.paragraphs, retr_section.paragraphs):
                assert orig_para.hash == retr_para.hash
                assert orig_para.content == retr_para.content
                assert orig_para.preview == retr_para.preview
                assert orig_para.word_count == retr_para.word_count
                assert orig_para.position == retr_para.position