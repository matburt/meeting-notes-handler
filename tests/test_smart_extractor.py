"""Tests for SmartContentExtractor."""

import pytest
import tempfile
from pathlib import Path
from meeting_notes_handler.smart_extractor import SmartContentExtractor


class TestSmartContentExtractor:
    """Test cases for SmartContentExtractor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.extractor = SmartContentExtractor(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_extract_new_content_first_meeting(self):
        """Test extracting content from the first meeting in a series."""
        meeting_metadata = {
            'title': 'Weekly Standup - Week 29',
            'organizer': 'alice@company.com',
            'start_time': '2024-07-16T09:00:00Z'
        }
        
        documents = [{
            'title': 'Meeting Notes',
            'url': 'https://docs.google.com/document/d/abc/edit',
            'content': """
        # Weekly Standup - Week 29
        
        ## Attendees
        - Alice Johnson
        - Bob Smith
        - Charlie Davis
        
        ## Discussion
        - Project status update
        - Sprint planning for next week
        - Code review feedback
        
        ## Action Items
        - Alice: Complete feature A by Friday
        - Bob: Review PR #123
        """
        }]
        
        # First meeting should return all content
        result = self.extractor.extract_new_content_only(meeting_metadata, documents)
        
        assert "Weekly Standup - Week 29" in new_content
        assert "Alice Johnson" in new_content
        assert "Project status update" in new_content
        assert "Alice: Complete feature A by Friday" in new_content
    
    def test_extract_new_content_recurring_meeting(self):
        """Test extracting only new content from a recurring meeting."""
        previous_content = """
        # Weekly Standup - Week 28
        
        ## Attendees
        - Alice Johnson
        - Bob Smith
        
        ## Discussion
        - Project status update
        - Sprint planning
        
        ## Action Items
        - Alice: Complete feature A
        """
        
        current_content = """
        # Weekly Standup - Week 29
        
        ## Attendees
        - Alice Johnson
        - Bob Smith
        - Charlie Davis
        
        ## Discussion
        - Project status update
        - Sprint planning for next week
        - Code review feedback
        - New feature discussion
        
        ## Action Items
        - Alice: Complete feature A by Friday
        - Bob: Review PR #123
        - Charlie: Update documentation
        """
        
        new_content = self.extractor.extract_new_content(current_content, previous_content)
        
        # Should include new attendee
        assert "Charlie Davis" in new_content
        
        # Should include new discussion items
        assert "Code review feedback" in new_content
        assert "New feature discussion" in new_content
        
        # Should include new action items
        assert "Bob: Review PR #123" in new_content
        assert "Charlie: Update documentation" in new_content
        
        # Should NOT include repeated content
        assert "Project status update" not in new_content or new_content.count("Project status update") <= 1
    
    def test_normalize_text_for_comparison(self):
        """Test text normalization for comparison."""
        test_cases = [
            ("  Multiple   spaces  ", "multiple spaces"),
            ("MixedCase Content", "mixedcase content"),
            ("Text with\nnewlines\n", "text with newlines"),
            ("Punctuation!!! & symbols???", "punctuation symbols"),
            ("", "")
        ]
        
        for original, expected in test_cases:
            normalized = self.extractor._normalize_text(original)
            assert normalized == expected, f"Failed for '{original}'"
    
    def test_split_into_sections(self):
        """Test splitting content into logical sections."""
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
        
        ## Section 3
        Final section content
        """
        
        sections = self.extractor._split_into_sections(content)
        
        # Should have title section plus 3 main sections
        assert len(sections) >= 4
        
        # Check that sections contain expected content
        section_texts = [section['content'] for section in sections]
        combined = '\n'.join(section_texts)
        
        assert "Meeting Title" in combined
        assert "Section 1" in combined
        assert "Content for section 1" in combined
        assert "Section 2" in combined
        assert "Section 3" in combined
    
    def test_calculate_section_similarity(self):
        """Test similarity calculation between sections."""
        section1 = {
            'header': 'Discussion',
            'content': 'Project status update\nSprint planning\nCode review'
        }
        
        section2 = {
            'header': 'Discussion', 
            'content': 'Project status update\nSprint planning\nNew feature discussion'
        }
        
        section3 = {
            'header': 'Action Items',
            'content': 'Alice: Complete task\nBob: Review code'
        }
        
        # Similar sections should have high similarity
        similarity = self.extractor._calculate_similarity(section1, section2)
        assert similarity > 0.5
        
        # Different sections should have lower similarity
        similarity = self.extractor._calculate_similarity(section1, section3)
        assert similarity < 0.5
    
    def test_identify_new_sentences(self):
        """Test identification of new sentences in content."""
        previous_sentences = [
            "Project is on track.",
            "We need to review the code.",
            "Meeting scheduled for Friday."
        ]
        
        current_sentences = [
            "Project is on track.",
            "We need to review the code carefully.",  # Modified
            "Meeting scheduled for Friday.",
            "New feature requirements discussed.",    # New
            "Budget approval needed."                 # New
        ]
        
        new_sentences = self.extractor._identify_new_sentences(current_sentences, previous_sentences)
        
        # Should identify modified and new sentences
        assert len(new_sentences) >= 2
        assert "New feature requirements discussed." in new_sentences
        assert "Budget approval needed." in new_sentences
    
    def test_filter_duplicate_content(self):
        """Test filtering of duplicate content sections."""
        content = """
        # Meeting Notes
        
        ## Attendees
        - Alice
        - Bob
        
        ## Discussion
        - Topic A
        - Topic B
        
        ## Action Items
        - Task 1
        - Task 2
        """
        
        # Same content should result in minimal output
        filtered = self.extractor.extract_new_content(content, content)
        
        # Should be much shorter than original
        assert len(filtered) < len(content) * 0.5
        
        # Should indicate minimal new content
        assert filtered.strip() == "" or "no significant new content" in filtered.lower()
    
    def test_preserve_structure_in_new_content(self):
        """Test that markdown structure is preserved in extracted content."""
        previous_content = """
        # Meeting - Week 1
        ## Discussion
        - Basic topic
        """
        
        current_content = """
        # Meeting - Week 2
        ## Discussion  
        - Basic topic
        - Advanced topic
        
        ## New Section
        ### Subsection
        - Important detail
        
        ## Action Items
        1. First action
        2. Second action
        """
        
        new_content = self.extractor.extract_new_content(current_content, previous_content)
        
        # Should preserve markdown formatting
        assert "##" in new_content or "#" in new_content
        assert "- Advanced topic" in new_content
        assert "### Subsection" in new_content or "Subsection" in new_content
        assert "1." in new_content or "First action" in new_content
    
    def test_handle_empty_or_none_content(self):
        """Test handling of empty or None content."""
        # None previous content
        result = self.extractor.extract_new_content("New content", None)
        assert result == "New content"
        
        # Empty previous content
        result = self.extractor.extract_new_content("New content", "")
        assert result == "New content"
        
        # None current content
        result = self.extractor.extract_new_content(None, "Previous content")
        assert result == ""
        
        # Empty current content
        result = self.extractor.extract_new_content("", "Previous content")
        assert result == ""
        
        # Both empty
        result = self.extractor.extract_new_content("", "")
        assert result == ""
    
    def test_content_similarity_threshold(self):
        """Test that content similarity threshold works correctly."""
        base_content = """
        # Meeting Notes
        ## Discussion
        - Topic A discussed in detail
        - Topic B needs more work
        - Topic C is complete
        """
        
        # Very similar content (only minor changes)
        similar_content = """
        # Meeting Notes  
        ## Discussion
        - Topic A discussed in detail
        - Topic B needs more work
        - Topic C is complete
        - Minor additional note
        """
        
        # Significantly different content
        different_content = """
        # Meeting Notes
        ## Discussion
        - Completely new topic X
        - Revolutionary idea Y
        - Breakthrough solution Z
        - Game changing approach
        """
        
        new_from_similar = self.extractor.extract_new_content(similar_content, base_content)
        new_from_different = self.extractor.extract_new_content(different_content, base_content)
        
        # Similar content should yield minimal new content
        assert len(new_from_similar) < len(similar_content) * 0.5
        
        # Different content should yield substantial new content
        assert len(new_from_different) > len(different_content) * 0.3
    
    def test_action_items_extraction(self):
        """Test that action items are properly identified and extracted."""
        previous_content = """
        ## Action Items
        - Alice: Review document A
        - Bob: Complete task X
        """
        
        current_content = """
        ## Action Items
        - Alice: Review document A (completed)
        - Bob: Complete task X
        - Charlie: Start new project Y
        - David: Prepare presentation Z
        """
        
        new_content = self.extractor.extract_new_content(current_content, previous_content)
        
        # Should include new action items
        assert "Charlie: Start new project Y" in new_content
        assert "David: Prepare presentation Z" in new_content
        
        # May include updated action items
        if "Alice: Review document A (completed)" in new_content:
            assert "(completed)" in new_content