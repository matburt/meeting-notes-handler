"""Tests for DocumentClassifier."""

import pytest
from meeting_notes_handler.document_classifier import DocumentClassifier, DocumentType, DocumentInfo


class TestDocumentClassifier:
    """Test cases for DocumentClassifier."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = DocumentClassifier()
    
    def test_gemini_notes_classification(self):
        """Test that Gemini notes are classified as ephemeral."""
        test_cases = [
            "Meeting Notes by Gemini",
            "Notes by Gemini - Sprint Planning",
            "Auto-generated meeting summary",
            "Weekly Standup - 2024/07/16 - Notes by Gemini"
        ]
        
        for title in test_cases:
            doc_type, confidence = self.classifier.classify_document(title)
            assert doc_type == DocumentType.EPHEMERAL, f"Failed for title: {title}"
            assert confidence > 0.5, f"Low confidence for title: {title}"
    
    def test_transcript_classification(self):
        """Test that transcripts are classified as ephemeral."""
        test_cases = [
            "Meeting Transcript",
            "Sprint Planning - Transcript",
            "Chat Log",
            "Meeting Recording"
        ]
        
        for title in test_cases:
            doc_type, confidence = self.classifier.classify_document(title)
            assert doc_type == DocumentType.EPHEMERAL, f"Failed for title: {title}"
            assert confidence > 0.5, f"Low confidence for title: {title}"
    
    def test_persistent_document_classification(self):
        """Test that persistent documents are classified correctly."""
        test_cases = [
            "Project Planning Document",
            "Sprint Backlog",
            "Requirements Specification",
            "Team Action Items",
            "Design Document"
        ]
        
        for title in test_cases:
            doc_type, confidence = self.classifier.classify_document(title)
            assert doc_type == DocumentType.PERSISTENT, f"Failed for title: {title}"
            assert confidence > 0.5, f"Low confidence for title: {title}"
    
    def test_url_pattern_recognition(self):
        """Test URL pattern recognition for Gemini content."""
        gemini_url = "https://docs.google.com/document/d/abc123/edit?usp=meet_tnfm_calendar"
        regular_url = "https://docs.google.com/document/d/xyz789/edit"
        
        doc_type, confidence = self.classifier.classify_document(
            "Meeting Notes", url=gemini_url
        )
        assert doc_type == DocumentType.EPHEMERAL
        
        doc_type, confidence = self.classifier.classify_document(
            "Meeting Notes", url=regular_url
        )
        # Should be unknown without other indicators
        assert doc_type == DocumentType.UNKNOWN
    
    def test_content_indicators(self):
        """Test content-based classification."""
        ephemeral_content = """
        Transcript of meeting started at 2:00 PM
        Participants joined: Alice, Bob, Charlie
        Meeting ended at 3:00 PM
        """
        
        persistent_content = """
        Last updated: 2024-07-15
        Document owner: Alice
        Shared with: team@company.com
        """
        
        doc_type, _ = self.classifier.classify_document(
            "Meeting Content", content=ephemeral_content
        )
        assert doc_type == DocumentType.EPHEMERAL
        
        doc_type, _ = self.classifier.classify_document(
            "Project Doc", content=persistent_content
        )
        assert doc_type == DocumentType.PERSISTENT
    
    def test_classify_documents_batch(self):
        """Test batch classification of multiple documents."""
        documents = [
            {
                'title': 'Notes by Gemini',
                'url': 'https://docs.google.com/document/d/abc/edit?usp=meet_tnfm_calendar',
                'content': 'Meeting transcript content'
            },
            {
                'title': 'Project Backlog',
                'url': 'https://docs.google.com/document/d/xyz/edit',
                'content': 'Sprint planning document with action items'
            },
            {
                'title': 'Unknown Document',
                'url': '',
                'content': ''
            }
        ]
        
        classified = self.classifier.classify_documents(documents)
        
        assert len(classified) == 3
        assert classified[0].doc_type == DocumentType.EPHEMERAL
        assert classified[1].doc_type == DocumentType.PERSISTENT
        assert classified[2].doc_type == DocumentType.UNKNOWN
    
    def test_classification_summary(self):
        """Test the classification summary functionality."""
        documents = [
            DocumentInfo("Doc 1", "url1", "content1", DocumentType.EPHEMERAL, 0.9, {}, 0),
            DocumentInfo("Doc 2", "url2", "content2", DocumentType.PERSISTENT, 0.8, {}, 1),
            DocumentInfo("Doc 3", "url3", "content3", DocumentType.UNKNOWN, 0.3, {}, 2),
        ]
        
        summary = self.classifier.get_classification_summary(documents)
        
        assert summary['total_documents'] == 3
        assert summary['ephemeral_count'] == 1
        assert summary['persistent_count'] == 1
        assert summary['unknown_count'] == 1
        assert summary['average_confidence'] == pytest.approx(0.67, rel=0.1)
    
    def test_edge_cases(self):
        """Test edge cases and empty inputs."""
        # Empty title
        doc_type, confidence = self.classifier.classify_document("")
        assert doc_type == DocumentType.UNKNOWN
        assert confidence == 0.0
        
        # None inputs
        doc_type, confidence = self.classifier.classify_document(None)
        assert doc_type == DocumentType.UNKNOWN
        
        # Empty document list
        classified = self.classifier.classify_documents([])
        assert len(classified) == 0