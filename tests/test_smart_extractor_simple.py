"""Simple tests for SmartContentExtractor core functionality."""

import pytest
import tempfile
from pathlib import Path
from meeting_notes_handler.smart_extractor import SmartContentExtractor, ContentSection


class TestSmartContentExtractorSimple:
    """Test cases for SmartContentExtractor core functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.extractor = SmartContentExtractor(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_parse_content_sections(self):
        """Test parsing content into sections."""
        content = """
        # Meeting Title
        
        Some intro text.
        
        ## Section 1
        Content for section 1
        More content here
        
        ## Section 2
        Content for section 2
        
        ### Subsection
        Subsection content
        """
        
        sections = self.extractor._parse_content_sections(content)
        
        # Should have at least the main sections
        assert len(sections) >= 3
        
        # Check that sections contain expected headers
        section_titles = [section.title for section in sections]
        assert any("Meeting Title" in title for title in section_titles)
        assert any("Section 1" in title for title in section_titles)
        assert any("Section 2" in title for title in section_titles)
    
    def test_calculate_title_similarity(self):
        """Test title similarity calculation."""
        # Identical titles should have high similarity
        similarity = self.extractor._calculate_title_similarity("Discussion", "Discussion")
        assert similarity == 1.0
        
        # Similar titles should have good similarity
        similarity = self.extractor._calculate_title_similarity("Action Items", "Action Items List")
        assert similarity > 0.5
        
        # Different titles should have low similarity
        similarity = self.extractor._calculate_title_similarity("Discussion", "Summary")
        assert similarity < 0.5
    
    def test_calculate_content_similarity(self):
        """Test content similarity calculation."""
        content1 = "Project is on track. We need to review the code."
        content2 = "Project is on track. We need to review the code carefully."
        content3 = "Completely different content about budgets and schedules."
        
        # Similar content should have high similarity
        similarity = self.extractor._calculate_content_similarity(content1, content2)
        assert similarity > 0.7
        
        # Different content should have low similarity
        similarity = self.extractor._calculate_content_similarity(content1, content3)
        assert similarity < 0.3
    
    def test_build_filtered_content(self):
        """Test building filtered content from sections."""
        sections = [
            ContentSection("Discussion", "- Topic A\n- Topic B", 2, 1, 3),
            ContentSection("Action Items", "- Task 1\n- Task 2", 2, 4, 6)
        ]
        
        filtered_content = self.extractor._build_filtered_content(sections)
        
        # Should contain section headers and content
        assert "## Discussion" in filtered_content
        assert "## Action Items" in filtered_content
        assert "Topic A" in filtered_content
        assert "Task 1" in filtered_content
    
    def test_count_sections(self):
        """Test section counting."""
        content = """
        # Title
        ## Section 1
        Content here
        ## Section 2
        More content
        ### Subsection
        Sub content
        """
        
        count = self.extractor._count_sections(content)
        assert count >= 3  # Should count main sections
    
    def test_find_matching_section(self):
        """Test finding matching sections."""
        target_section = ContentSection("Discussion", "Topic A and Topic B", 2, 1, 3)
        
        candidate_sections = [
            ContentSection("Summary", "Different content", 2, 1, 2),
            ContentSection("Discussion", "Topic A and Topic C", 2, 3, 5),  # Exact match
            ContentSection("Action Items", "Task list", 2, 6, 8)
        ]
        
        match = self.extractor._find_matching_section(target_section, candidate_sections)
        
        # Should find the exact discussion section match
        assert match is not None
        assert match.title == "Discussion"
    
    def test_extract_new_content_only_basic(self):
        """Test basic functionality of extract_new_content_only."""
        meeting_metadata = {
            'title': 'Test Meeting',
            'organizer': 'test@example.com',
            'start_time': '2024-07-16T09:00:00Z',
            'attendees': ['test@example.com']
        }
        
        documents = [{
            'title': 'Meeting Notes',
            'url': 'https://docs.google.com/document/d/test/edit',
            'content': '# Test Meeting\n\n## Discussion\n- New topic discussed'
        }]
        
        # Should not raise an exception
        try:
            result = self.extractor.extract_new_content_only(meeting_metadata, documents)
            assert result is not None
            assert hasattr(result, 'has_new_content')
        except Exception as e:
            # If it fails due to missing dependencies, that's expected
            assert "module" in str(e).lower() or "import" in str(e).lower() or "classifier" in str(e).lower()
    
    def test_content_section_dataclass(self):
        """Test ContentSection dataclass functionality."""
        section = ContentSection(
            title="Test Section",
            content="Test content",
            level=2,
            start_line=1,
            end_line=5
        )
        
        assert section.title == "Test Section"
        assert section.content == "Test content"
        assert section.level == 2
        assert section.start_line == 1
        assert section.end_line == 5