"""Tests for DiffEngine."""

import pytest
from meeting_notes_handler.content_hasher import ContentHasher, ContentSignature, Section, Paragraph
from meeting_notes_handler.diff_engine import DiffEngine, ChangeType


class TestDiffEngine:
    """Test cases for DiffEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.hasher = ContentHasher()
        self.diff_engine = DiffEngine()
        
    def test_identical_meetings_no_changes(self):
        """Test that identical meetings show no changes."""
        content = """# Action Items
- Alice to review documentation
- Bob to update the API"""
        
        sig1 = self.hasher.create_content_signature("meeting1", content, "2024-07-22T10:00:00Z")
        sig2 = self.hasher.create_content_signature("meeting2", content, "2024-07-22T10:00:00Z")
        
        diff = self.diff_engine.compare_meetings(sig1, sig2)
        
        assert diff.summary.total_paragraphs_added == 0
        assert diff.summary.total_paragraphs_removed == 0
        assert diff.summary.total_paragraphs_modified == 0
        assert diff.summary.similarity_percentage > 99.0
        
    def test_paragraph_addition(self):
        """Test detection of added paragraphs."""
        content1 = """# Action Items
- Alice to review documentation"""
        
        content2 = """# Action Items
- Alice to review documentation
- Bob to update the API"""
        
        sig1 = self.hasher.create_content_signature("meeting1", content1, "2024-07-22T10:00:00Z")
        sig2 = self.hasher.create_content_signature("meeting2", content2, "2024-07-22T10:00:00Z")
        
        diff = self.diff_engine.compare_meetings(sig1, sig2)
        
        # Should detect net addition of content
        assert diff.summary.total_paragraphs_added >= 1
        assert diff.summary.total_words_added > 0
        
    def test_paragraph_removal(self):
        """Test detection of removed paragraphs."""
        content1 = """# Action Items
- Alice to review documentation
- Bob to update the API"""
        
        content2 = """# Action Items
- Alice to review documentation"""
        
        sig1 = self.hasher.create_content_signature("meeting1", content1, "2024-07-22T10:00:00Z")
        sig2 = self.hasher.create_content_signature("meeting2", content2, "2024-07-22T10:00:00Z")
        
        diff = self.diff_engine.compare_meetings(sig1, sig2)
        
        # Should detect net removal of content
        assert diff.summary.total_paragraphs_removed >= 1
        assert diff.summary.total_words_removed > 0
        
    def test_section_addition(self):
        """Test detection of new sections."""
        content1 = """# Action Items
- Alice to review documentation"""
        
        content2 = """# Action Items
- Alice to review documentation

# Decisions
- Use PostgreSQL database"""
        
        sig1 = self.hasher.create_content_signature("meeting1", content1, "2024-07-22T10:00:00Z")
        sig2 = self.hasher.create_content_signature("meeting2", content2, "2024-07-22T10:00:00Z")
        
        diff = self.diff_engine.compare_meetings(sig1, sig2)
        
        assert diff.summary.total_sections_added == 1
        assert diff.summary.total_paragraphs_added == 1
        
    def test_paragraph_modification(self):
        """Test detection of modified paragraphs."""
        content1 = """# Action Items
- Alice to review documentation quickly"""
        
        content2 = """# Action Items
- Alice to review documentation thoroughly"""
        
        sig1 = self.hasher.create_content_signature("meeting1", content1, "2024-07-22T10:00:00Z")
        sig2 = self.hasher.create_content_signature("meeting2", content2, "2024-07-22T10:00:00Z")
        
        diff = self.diff_engine.compare_meetings(sig1, sig2)
        
        # Should detect as modification since similarity is high
        assert diff.summary.total_paragraphs_modified >= 1 or diff.summary.total_paragraphs_added == 1
        
    def test_moved_paragraphs(self):
        """Test detection of paragraphs moved between sections."""
        content1 = """# Action Items
- Review the documentation

# Decisions
- Use PostgreSQL database"""
        
        content2 = """# Action Items
- Use PostgreSQL database

# Decisions
- Review the documentation"""
        
        sig1 = self.hasher.create_content_signature("meeting1", content1, "2024-07-22T10:00:00Z")
        sig2 = self.hasher.create_content_signature("meeting2", content2, "2024-07-22T10:00:00Z")
        
        diff = self.diff_engine.compare_meetings(sig1, sig2)
        
        # Should detect moved content
        assert len(diff.moved_paragraphs) >= 1 or diff.summary.total_paragraphs_modified >= 1
        
    def test_similarity_calculation(self):
        """Test similarity calculation accuracy."""
        text1 = "Alice needs to review the documentation thoroughly"
        text2 = "Alice needs to review the documentation quickly"
        
        similarity = self.diff_engine._calculate_similarity(text1, text2)
        assert 0.7 <= similarity <= 0.95  # High similarity, one word different
        
    def test_best_match_finding(self):
        """Test finding best matching paragraph."""
        old_para = Paragraph(
            hash="old_hash",
            content="Alice to review documentation",
            preview="Alice to review documentation",
            word_count=4,
            position=0
        )
        
        candidates = [
            Paragraph(
                hash="new_hash1",
                content="Bob to update API",
                preview="Bob to update API",
                word_count=4,
                position=0
            ),
            Paragraph(
                hash="new_hash2", 
                content="Alice to review documentation quickly",
                preview="Alice to review documentation quickly",
                word_count=5,
                position=1
            )
        ]
        
        best_match = self.diff_engine._find_best_match(old_para, candidates, set())
        
        assert best_match is not None
        assert best_match[0].content == "Alice to review documentation quickly"
        assert best_match[1] > 0.8  # High similarity
        
    def test_diff_summary_formatting(self):
        """Test diff summary formatting."""
        content1 = """# Action Items
- Alice to review documentation"""
        
        content2 = """# Action Items
- Alice to review documentation
- Bob to update the API

# Decisions  
- Use PostgreSQL database"""
        
        sig1 = self.hasher.create_content_signature("meeting1", content1, "2024-07-22T10:00:00Z")
        sig2 = self.hasher.create_content_signature("meeting2", content2, "2024-07-22T10:00:00Z")
        
        diff = self.diff_engine.compare_meetings(sig1, sig2)
        summary_text = self.diff_engine.format_diff_summary(diff)
        
        assert "📊 Meeting Diff Summary" in summary_text
        assert "meeting1 → meeting2" in summary_text
        assert "✅" in summary_text  # Should show additions
        
    def test_empty_content_diff(self):
        """Test diffing when one signature is empty."""
        content1 = ""
        content2 = """# Action Items
- Alice to review documentation"""
        
        sig1 = self.hasher.create_content_signature("meeting1", content1, "2024-07-22T10:00:00Z")
        sig2 = self.hasher.create_content_signature("meeting2", content2, "2024-07-22T10:00:00Z")
        
        diff = self.diff_engine.compare_meetings(sig1, sig2)
        
        assert diff.summary.total_sections_added >= 1
        assert diff.summary.total_paragraphs_added >= 1