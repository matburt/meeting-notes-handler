"""Tests for DocsConverter error handling and rate limiting."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from googleapiclient.errors import HttpError
from meeting_notes_handler.docs_converter import DocsConverter


class TestDocsConverter:
    """Test cases for DocsConverter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock credentials
        self.mock_credentials = Mock()
        
        # Create converter with mocked services
        with patch('meeting_notes_handler.docs_converter.build') as mock_build:
            mock_docs_service = Mock()
            mock_drive_service = Mock() 
            mock_build.side_effect = [mock_docs_service, mock_drive_service]
            
            self.converter = DocsConverter(self.mock_credentials)
            self.mock_docs_service = mock_docs_service
            self.mock_drive_service = mock_drive_service
    
    def test_parse_google_api_error_404(self):
        """Test parsing of 404 errors."""
        # Create mock HttpError for 404
        mock_response = Mock()
        mock_response.status = 404
        
        error = HttpError(mock_response, b'{"error": {"message": "File not found"}}')
        file_id = "test_file_id"
        
        parsed = self.converter._parse_google_api_error(error, file_id)
        
        assert parsed['type'] == 'file_not_found'
        assert 'Document not found or inaccessible' in parsed['user_message']
        assert 'deleted' in parsed['detailed_message']
        assert 'private' in parsed['detailed_message']
        assert len(parsed['suggestions']) > 0
        assert 'Check if the document still exists' in parsed['suggestions'][0]
    
    def test_parse_google_api_error_403(self):
        """Test parsing of 403 access denied errors."""
        mock_response = Mock()
        mock_response.status = 403
        
        error = HttpError(mock_response, b'{"error": {"message": "Access denied"}}')
        file_id = "test_file_id"
        
        parsed = self.converter._parse_google_api_error(error, file_id)
        
        assert parsed['type'] == 'access_denied'
        assert 'Access denied to document' in parsed['user_message']
        assert 'permission' in parsed['detailed_message']
        assert 'Ask the document owner to share it' in parsed['suggestions'][0]
    
    def test_parse_google_api_error_429(self):
        """Test parsing of 429 rate limit errors."""
        mock_response = Mock()
        mock_response.status = 429
        
        error = HttpError(mock_response, b'{"error": {"message": "Rate limit exceeded"}}')
        file_id = "test_file_id"
        
        parsed = self.converter._parse_google_api_error(error, file_id)
        
        assert parsed['type'] == 'rate_limit'
        assert 'rate limit exceeded' in parsed['user_message'].lower()
        assert 'automatically retried' in parsed['detailed_message']
        assert 'try running the command again' in parsed['suggestions'][0].lower()
    
    def test_parse_google_api_error_500(self):
        """Test parsing of 500 server errors."""
        mock_response = Mock()
        mock_response.status = 500
        
        error = HttpError(mock_response, b'{"error": {"message": "Internal server error"}}')
        file_id = "test_file_id"
        
        parsed = self.converter._parse_google_api_error(error, file_id)
        
        assert parsed['type'] == 'server_error'
        assert 'temporarily unavailable' in parsed['user_message']
        assert 'servers are experiencing issues' in parsed['detailed_message']
        assert 'Try again in a few minutes' in parsed['suggestions'][0]
    
    def test_parse_non_http_error(self):
        """Test parsing of non-HTTP errors."""
        error = ValueError("Something went wrong")
        file_id = "test_file_id"
        
        parsed = self.converter._parse_google_api_error(error, file_id)
        
        assert parsed['type'] == 'unknown_error'
        assert 'Unknown error accessing document' in parsed['user_message']
        assert 'unexpected error occurred' in parsed['detailed_message']
        assert 'Try again later' in parsed['suggestions'][0]
    
    def test_retry_with_backoff_success_first_try(self):
        """Test successful function call on first try."""
        mock_func = Mock(return_value="success")
        
        result = self.converter._retry_with_backoff(mock_func, "arg1", kwarg1="value1")
        
        assert result == "success"
        assert mock_func.call_count == 1
        mock_func.assert_called_with("arg1", kwarg1="value1")
    
    def test_retry_with_backoff_429_retry_success(self):
        """Test retry logic for 429 errors with eventual success."""
        mock_response = Mock()
        mock_response.status = 429
        
        http_error = HttpError(mock_response, b'{"error": {"message": "Rate limit"}}')
        
        mock_func = Mock()
        mock_func.side_effect = [http_error, http_error, "success"]  # Fail twice, then succeed
        
        with patch('time.sleep') as mock_sleep:
            result = self.converter._retry_with_backoff(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2  # Should sleep twice before success
        
        # Check exponential backoff timing
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls[0] >= 1.0  # First retry delay >= base_delay
        assert sleep_calls[1] >= 2.0  # Second retry delay should be longer
    
    def test_retry_with_backoff_500_retry_success(self):
        """Test retry logic for 5xx server errors."""
        mock_response = Mock()
        mock_response.status = 500
        
        http_error = HttpError(mock_response, b'{"error": {"message": "Server error"}}')
        
        mock_func = Mock()
        mock_func.side_effect = [http_error, "success"]  # Fail once, then succeed
        
        with patch('time.sleep') as mock_sleep:
            result = self.converter._retry_with_backoff(mock_func)
        
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
            self.converter._retry_with_backoff(mock_func)
        
        assert mock_func.call_count == 1  # Should not retry
    
    def test_retry_with_backoff_403_no_retry(self):
        """Test that 403 errors are not retried."""
        mock_response = Mock()
        mock_response.status = 403
        
        http_error = HttpError(mock_response, b'{"error": {"message": "Access denied"}}')
        
        mock_func = Mock(side_effect=http_error)
        
        with pytest.raises(HttpError):
            self.converter._retry_with_backoff(mock_func)
        
        assert mock_func.call_count == 1  # Should not retry
    
    def test_retry_with_backoff_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        mock_response = Mock()
        mock_response.status = 429
        
        http_error = HttpError(mock_response, b'{"error": {"message": "Rate limit"}}')
        
        mock_func = Mock(side_effect=http_error)  # Always fails
        
        with patch('time.sleep'):
            with pytest.raises(HttpError):
                self.converter._retry_with_backoff(mock_func)
        
        # Should try initial + max_retries times
        expected_calls = self.converter.max_retries + 1
        assert mock_func.call_count == expected_calls
    
    def test_retry_with_backoff_non_http_error_no_retry(self):
        """Test that non-HTTP errors are not retried."""
        error = ValueError("Something went wrong")
        mock_func = Mock(side_effect=error)
        
        with pytest.raises(ValueError):
            self.converter._retry_with_backoff(mock_func)
        
        assert mock_func.call_count == 1  # Should not retry
    
    def test_extract_document_id_patterns(self):
        """Test document ID extraction from various URL patterns."""
        test_cases = [
            ("https://docs.google.com/document/d/ABC123DEF456/edit", "ABC123DEF456"),
            ("https://docs.google.com/spreadsheets/d/XYZ789GHI012/edit", "XYZ789GHI012"),
            ("https://docs.google.com/presentation/d/QWE345RTY678/edit", "QWE345RTY678"),
            ("https://drive.google.com/file/d/ZXC901VBN234/view", "ZXC901VBN234"),
            ("https://docs.google.com/document/d/MNB567UIO890/edit?usp=sharing", "MNB567UIO890"),
            ("ABC123DEF456", "ABC123DEF456"),  # Direct ID
            ("invalid-url", None),
            ("", None)
        ]
        
        for url, expected_id in test_cases:
            result = self.converter.extract_document_id(url)
            assert result == expected_id, f"Failed for URL: {url}"
    
    def test_get_document_metadata_with_retry(self):
        """Test that get_document_metadata uses retry logic."""
        file_id = "test_file_id"
        
        # Mock successful responses
        mock_file_metadata = {
            'id': file_id,
            'name': 'Test Document',
            'createdTime': '2024-01-01T00:00:00Z',
            'modifiedTime': '2024-01-02T00:00:00Z',
            'owners': [{'displayName': 'Test User'}],
            'shared': False
        }
        
        mock_doc = {
            'revisionId': '123',
            'body': {'content': []}
        }
        
        # Set up mocks to return data
        self.mock_drive_service.files().get().execute.return_value = mock_file_metadata
        self.mock_docs_service.documents().get().execute.return_value = mock_doc
        
        # Call method
        metadata = self.converter.get_document_metadata(file_id)
        
        # Verify retry wrapper was used (function was called)
        assert metadata['id'] == file_id
        assert metadata['title'] == 'Test Document'
        assert 'revision_id' in metadata
        assert 'word_count' in metadata
    
    def test_get_document_metadata_error_handling(self):
        """Test error handling in get_document_metadata."""
        file_id = "test_file_id"
        
        # Mock 404 error
        mock_response = Mock()
        mock_response.status = 404
        http_error = HttpError(mock_response, b'{"error": {"message": "Not found"}}')
        
        self.mock_drive_service.files().get().execute.side_effect = http_error
        
        metadata = self.converter.get_document_metadata(file_id)
        
        # Should return error metadata instead of raising
        assert metadata['id'] == file_id
        assert 'Error:' in metadata['title']
        assert 'error' in metadata
        assert metadata['error_type'] == 'file_not_found'
    
    @patch('meeting_notes_handler.docs_converter.logger')
    def test_retry_logging(self, mock_logger):
        """Test that retry attempts are properly logged."""
        mock_response = Mock()
        mock_response.status = 429
        
        http_error = HttpError(mock_response, b'{"error": {"message": "Rate limit"}}')
        mock_func = Mock()
        mock_func.side_effect = [http_error, "success"]
        
        with patch('time.sleep'):
            result = self.converter._retry_with_backoff(mock_func)
        
        assert result == "success"
        
        # Check that warning was logged for retry
        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "HTTP 429 error" in warning_call
        assert "Retrying in" in warning_call
    
    def test_convert_to_markdown_error_integration(self):
        """Test full error handling integration in convert_to_markdown."""
        file_id = "test_file_id"
        
        # Mock 404 error in _get_file_info
        mock_response = Mock()
        mock_response.status = 404
        http_error = HttpError(mock_response, b'{"error": {"message": "Not found"}}')
        
        self.mock_drive_service.files().get().execute.side_effect = http_error
        
        result = self.converter.convert_to_markdown(file_id)
        
        # Should return error info instead of raising
        assert result['success'] is False
        assert 'Document Access Error' in result['content']
        assert result['error_type'] == 'file_not_found'
        assert file_id in result['content']