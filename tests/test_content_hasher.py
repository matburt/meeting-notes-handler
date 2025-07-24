"""Tests for ContentHasher."""

import pytest
from datetime import datetime
from meeting_notes_handler.content_hasher import ContentHasher, ContentSignature, Section, Paragraph


class TestContentHasher:
    """Test cases for ContentHasher."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.hasher = ContentHasher()
        
    def test_hash_consistency(self):
        """Test that identical content produces identical hashes."""
        text1 = "This is a test paragraph."
        text2 = "This is a test paragraph."
        
        hash1 = self.hasher._hash_text(text1)
        hash2 = self.hasher._hash_text(text2)
        
        assert hash1 == hash2
        
    def test_hash_difference(self):
        """Test that different content produces different hashes."""
        text1 = "This is a test paragraph."
        text2 = "This is a different paragraph."
        
        hash1 = self.hasher._hash_text(text1)
        hash2 = self.hasher._hash_text(text2)
        
        assert hash1 != hash2
        
    def test_paragraph_extraction(self):
        """Test paragraph extraction from text."""
        text = """First paragraph content.

Second paragraph content.

Third paragraph content."""
        
        paragraphs = self.hasher.extract_paragraphs(text)
        
        assert len(paragraphs) == 3
        assert paragraphs[0].content == "First paragraph content."
        assert paragraphs[1].content == "Second paragraph content."
        assert paragraphs[2].content == "Third paragraph content."
        
    def test_section_extraction(self):
        """Test section extraction from content."""
        content = """# Introduction
This is the introduction.

## Action Items
- Item 1
- Item 2

### Discussion
We discussed various topics."""
        
        sections = self.hasher.extract_sections(content)
        
        assert len(sections) >= 2  # At least Introduction and Action Items
        
        # Check that we found the main sections
        section_headers = [s.header for s in sections]
        assert "Introduction" in section_headers
        assert "Action Items" in section_headers
        
    def test_content_signature_creation(self):
        """Test complete content signature creation."""
        meeting_id = "test_meeting_123"
        content = """# Meeting Notes

## Action Items
- Alice to review documentation
- Bob to update the API

## Decisions
- Use PostgreSQL for database
- Deploy on Friday"""
        
        signature = self.hasher.create_content_signature(
            meeting_id=meeting_id,
            content=content,
            extracted_at=datetime.now().isoformat()
        )
        
        assert signature.meeting_id == meeting_id
        assert signature.full_content_hash is not None
        assert len(signature.sections) >= 2
        assert signature.total_words > 0
        assert signature.total_paragraphs > 0
        
    def test_empty_content_handling(self):
        """Test handling of empty content."""
        signature = self.hasher.create_content_signature(
            meeting_id="empty_test",
            content="",
            extracted_at=datetime.now().isoformat()
        )
        
        assert signature.meeting_id == "empty_test"
        assert signature.total_words == 0
        assert signature.total_paragraphs == 0
        assert len(signature.sections) == 0
        
    def test_similarity_calculation(self):
        """Test similarity calculation between texts."""
        text1 = "The quick brown fox jumps over the lazy dog"
        text2 = "The quick brown fox jumps over the lazy cat"
        text3 = "Completely different text with no similarities"
        
        # High similarity (one word different)
        similarity1 = self.hasher.calculate_similarity(text1, text2)
        assert similarity1 > 0.7
        
        # Low similarity (completely different)
        similarity2 = self.hasher.calculate_similarity(text1, text3)
        assert similarity2 < 0.2
        
        # Identical text
        similarity3 = self.hasher.calculate_similarity(text1, text1)
        assert similarity3 == 1.0
        
    def test_header_detection(self):
        """Test various header detection patterns."""
        # Markdown headers
        assert self.hasher._extract_header("# Main Header", "") == "Main Header"
        assert self.hasher._extract_header("## Sub Header", "") == "Sub Header"
        
        # Bold headers
        assert self.hasher._extract_header("**Bold Header**", "") == "Bold Header"
        assert self.hasher._extract_header("__Underline Header__:", "") == "Underline Header"
        
        # Underline headers
        assert self.hasher._extract_header("Underline Header", "===============") == "Underline Header"
        
        # All caps headers
        assert self.hasher._extract_header("ACTION ITEMS", "") == "ACTION ITEMS"
        
        # Non-headers
        assert self.hasher._extract_header("This is regular text", "") is None
        
    def test_paragraph_normalization(self):
        """Test paragraph text normalization."""
        # Test whitespace normalization
        text1 = "  Multiple   spaces   and\n\ntabs\t\there  "
        normalized1 = self.hasher._normalize_paragraph(text1)
        assert normalized1 == "Multiple spaces and tabs here"
        
        # Test zero-width character removal
        text2 = "Text\u200bwith\u200czero\u200dwidth\ufeffchars"
        normalized2 = self.hasher._normalize_paragraph(text2)
        assert normalized2 == "Textwithzerowidthchars"