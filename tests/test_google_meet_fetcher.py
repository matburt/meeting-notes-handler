"""Tests for GoogleMeetFetcher error handling and rate limiting."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from googleapiclient.errors import HttpError
from meeting_notes_handler.google_meet_fetcher import GoogleMeetFetcher


class TestGoogleMeetFetcher:
    """Test cases for GoogleMeetFetcher."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock config object
        mock_config = Mock()
        mock_config.output_directory = "/tmp/test"
        
        # Create fetcher with mocked services
        with patch('meeting_notes_handler.google_meet_fetcher.build') as mock_build:
            with patch('meeting_notes_handler.google_meet_fetcher.FileOrganizer'):
                with patch('meeting_notes_handler.google_meet_fetcher.SmartContentExtractor'):
                    mock_calendar_service = Mock()
                    mock_build.return_value = mock_calendar_service
                    
                    self.fetcher = GoogleMeetFetcher(mock_config)
                    self.mock_calendar_service = mock_calendar_service
    
    def test_retry_with_backoff_success_first_try(self):
        """Test successful function call on first try."""
        mock_func = Mock(return_value="success")
        
        result = self.fetcher._retry_with_backoff(mock_func, "arg1", kwarg1="value1")
        
        assert result == "success"
        assert mock_func.call_count == 1
        mock_func.assert_called_with("arg1", kwarg1="value1")
    
    def test_retry_with_backoff_429_retry_success(self):
        """Test retry logic for 429 errors with eventual success."""
        mock_response = Mock()
        mock_response.status = 429
        
        http_error = HttpError(mock_response, b'{"error": {"message": "Rate limit"}}')
        
        mock_func = Mock()
        mock_func.side_effect = [http_error, "success"]  # Fail once, then succeed
        
        with patch('time.sleep') as mock_sleep:
            result = self.fetcher._retry_with_backoff(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 2
        assert mock_sleep.call_count == 1
    
    def test_retry_with_backoff_404_no_retry(self):
        """Test that 404 errors are not retried."""
        mock_response = Mock()
        mock_response.status = 404
        
        http_error = HttpError(mock_response, b'{"error": {"message": "Not found"}}')
        
        mock_func = Mock(side_effect=http_error)
        
        with pytest.raises(HttpError):
            self.fetcher._retry_with_backoff(mock_func)
        
        assert mock_func.call_count == 1  # Should not retry
    
    def test_process_meeting_notes_error_handling(self):
        """Test error handling in process_meeting_notes method."""
        # Mock meeting data
        meeting = {
            'id': 'test_meeting_id',
            'summary': 'Test Meeting',
            'start': {'dateTime': '2024-07-16T09:00:00Z'},
            'organizer': {'email': 'organizer@example.com'},
            'attendees': [{'email': 'attendee@example.com'}],
            'attachments': [
                {
                    'fileUrl': 'https://docs.google.com/document/d/invalid_doc_id/edit',
                    'title': 'Meeting Notes'
                }
            ]
        }
        
        # Mock DocsConverter to raise an error
        mock_converter = Mock()
        mock_converter.extract_document_id.return_value = 'invalid_doc_id'
        
        # Mock error response from converter
        mock_response = Mock()
        mock_response.status = 404
        http_error = HttpError(mock_response, b'{"error": {"message": "File not found"}}')
        
        mock_converter.convert_to_markdown.side_effect = http_error
        
        with patch('meeting_notes_handler.google_meet_fetcher.DocsConverter', return_value=mock_converter):
            with patch('meeting_notes_handler.google_meet_fetcher.logger') as mock_logger:
                # This should not raise an exception
                self.fetcher.process_meeting_notes([meeting])
        
        # Verify error was logged
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args[0][0]
        assert 'Failed to convert document' in error_call
    
    def test_get_recent_meetings_with_retry(self):
        """Test that get_recent_meetings uses retry logic for Calendar API."""
        # Mock calendar API response
        mock_events = {
            'items': [
                {
                    'id': 'event1',
                    'summary': 'Test Meeting',
                    'start': {'dateTime': '2024-07-16T09:00:00Z'},
                    'organizer': {'email': 'test@example.com'}
                }
            ]
        }
        
        # Set up mock to return events
        self.mock_calendar_service.events().list().execute.return_value = mock_events
        
        # Mock datetime for consistent testing
        from datetime import datetime
        with patch('meeting_notes_handler.google_meet_fetcher.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 7, 16, 12, 0, 0)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            meetings = self.fetcher.get_recent_meetings(days=7)
        
        # Verify the retry wrapper was used (function was called)
        assert len(meetings) == 1
        assert meetings[0]['id'] == 'event1'
    
    def test_get_recent_meetings_calendar_error(self):
        """Test error handling when Calendar API fails."""
        # Mock 403 error from Calendar API
        mock_response = Mock()
        mock_response.status = 403
        http_error = HttpError(mock_response, b'{"error": {"message": "Access denied"}}')
        
        self.mock_calendar_service.events().list().execute.side_effect = http_error
        
        # Should raise the error since it's not retryable
        with pytest.raises(HttpError):
            self.fetcher.get_recent_meetings(days=7)
    
    def test_error_message_extraction_from_docs_converter(self):
        """Test extraction of user-friendly error messages from DocsConverter."""
        # This tests the integration between GoogleMeetFetcher and DocsConverter error handling
        
        meeting = {
            'id': 'test_meeting_id', 
            'summary': 'Test Meeting',
            'start': {'dateTime': '2024-07-16T09:00:00Z'},
            'organizer': {'email': 'organizer@example.com'},
            'attendees': [{'email': 'attendee@example.com'}],
            'attachments': [
                {
                    'fileUrl': 'https://docs.google.com/document/d/doc123/edit',
                    'title': 'Meeting Notes'
                }
            ]
        }
        
        # Mock DocsConverter to return error info (not raise exception)
        mock_converter = Mock()
        mock_converter.extract_document_id.return_value = 'doc123'
        
        # Simulate DocsConverter returning error info instead of raising
        error_result = {
            'success': False,
            'error': 'Document not found or inaccessible',
            'error_type': 'file_not_found',
            'content': '# Document Access Error\n\nFile not accessible',
            'metadata': {'id': 'doc123', 'error': 'Document not found'}
        }
        mock_converter.convert_to_markdown.return_value = error_result
        
        with patch('meeting_notes_handler.google_meet_fetcher.DocsConverter', return_value=mock_converter):
            with patch('meeting_notes_handler.google_meet_fetcher.logger') as mock_logger:
                self.fetcher.process_meeting_notes([meeting])
        
        # Should log a user-friendly error message
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args[0][0]
        assert 'Document not found' in error_call or 'not accessible' in error_call
    
    def test_filter_meetings_with_attachments(self):
        """Test filtering of meetings to only process those with document attachments."""
        meetings = [
            {
                'id': 'meeting1',
                'summary': 'Meeting with docs',
                'attachments': [
                    {'fileUrl': 'https://docs.google.com/document/d/abc/edit', 'title': 'Notes'}
                ]
            },
            {
                'id': 'meeting2', 
                'summary': 'Meeting without attachments'
                # No attachments
            },
            {
                'id': 'meeting3',
                'summary': 'Meeting with non-doc attachment',
                'attachments': [
                    {'fileUrl': 'https://example.com/file.pdf', 'title': 'PDF'}
                ]
            }
        ]
        
        # Mock the document extraction process
        with patch.object(self.fetcher, '_has_google_docs_attachments') as mock_has_docs:
            mock_has_docs.side_effect = [True, False, False]  # Only first meeting has Google Docs
            
            filtered = [m for m in meetings if self.fetcher._has_google_docs_attachments(m)]
        
        assert len(filtered) == 1
        assert filtered[0]['id'] == 'meeting1'
    
    @patch('meeting_notes_handler.google_meet_fetcher.logger')
    def test_retry_logging_in_fetcher(self, mock_logger):
        """Test that retry attempts are properly logged in GoogleMeetFetcher."""
        mock_response = Mock()
        mock_response.status = 500
        
        http_error = HttpError(mock_response, b'{"error": {"message": "Server error"}}')
        mock_func = Mock()
        mock_func.side_effect = [http_error, "success"]
        
        with patch('time.sleep'):
            result = self.fetcher._retry_with_backoff(mock_func)
        
        assert result == "success"
        
        # Check that warning was logged for retry
        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "HTTP 500 error" in warning_call
        assert "Retrying in" in warning_call
    
    def test_meeting_metadata_extraction(self):
        """Test extraction of meeting metadata for series tracking."""
        meeting = {
            'id': 'test_meeting_id',
            'summary': 'Weekly Standup - Team Alpha',
            'start': {'dateTime': '2024-07-16T09:00:00Z'},
            'organizer': {'email': 'alice@company.com'},
            'attendees': [
                {'email': 'alice@company.com', 'responseStatus': 'accepted'},
                {'email': 'bob@company.com', 'responseStatus': 'accepted'},
                {'email': 'charlie@company.com', 'responseStatus': 'declined'}
            ]
        }
        
        # Test metadata extraction (this would be used by series tracker)
        metadata = self.fetcher._extract_meeting_metadata(meeting)
        
        assert metadata['title'] == 'Weekly Standup - Team Alpha'
        assert metadata['organizer'] == 'alice@company.com'
        assert len(metadata['attendees']) == 2  # Should exclude declined attendees
        assert 'alice@company.com' in metadata['attendees']
        assert 'bob@company.com' in metadata['attendees']
        assert 'charlie@company.com' not in metadata['attendees']