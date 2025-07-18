"""Google Docs to Markdown conversion utilities."""

import re
import logging
import time
import random
from typing import Dict, Any, Optional, Callable
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from markdownify import markdownify as md

logger = logging.getLogger(__name__)

class DocsConverter:
    """Converts Google Docs to Markdown format."""
    
    def __init__(self, credentials: Credentials):
        """Initialize the docs converter.
        
        Args:
            credentials: Google API credentials.
        """
        self.credentials = credentials
        self.docs_service = build('docs', 'v1', credentials=credentials)
        self.drive_service = build('drive', 'v3', credentials=credentials)
        
        # Rate limiting configuration
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay in seconds
        self.max_delay = 60.0  # Maximum delay in seconds
    
    def _parse_google_api_error(self, error: Exception, file_id: str) -> Dict[str, str]:
        """Parse Google API errors and provide user-friendly messages.
        
        Args:
            error: The exception that occurred
            file_id: The file ID that caused the error
            
        Returns:
            Dictionary with error details and user-friendly message
        """
        if isinstance(error, HttpError):
            status_code = error.resp.status
            error_details = error.error_details if hasattr(error, 'error_details') else []
            
            if status_code == 404:
                return {
                    'type': 'file_not_found',
                    'user_message': 'Document not found or inaccessible',
                    'detailed_message': f'The document with ID {file_id} was not found. This could mean:\n'
                                      f'• The document has been deleted\n'
                                      f'• The document is private and you don\'t have access\n'
                                      f'• The document link is broken or expired\n'
                                      f'• The document was moved to a different location',
                    'technical_error': str(error),
                    'suggestions': [
                        'Check if the document still exists by opening the original link',
                        'Verify you have permission to access the document',
                        'Ask the document owner to share it with you',
                        'Remove this document from the meeting if it\'s no longer needed'
                    ]
                }
            elif status_code == 403:
                return {
                    'type': 'access_denied',
                    'user_message': 'Access denied to document',
                    'detailed_message': f'You don\'t have permission to access document {file_id}. This could mean:\n'
                                      f'• The document is private\n'
                                      f'• Your Google account doesn\'t have the required permissions\n'
                                      f'• The document\'s sharing settings have changed',
                    'technical_error': str(error),
                    'suggestions': [
                        'Ask the document owner to share it with your account',
                        'Check if you\'re signed in with the correct Google account',
                        'Request "View" or "Comment" access to the document'
                    ]
                }
            elif status_code == 429:
                return {
                    'type': 'rate_limit',
                    'user_message': 'API rate limit exceeded after retries',
                    'detailed_message': f'Too many requests to Google Drive API. The system automatically retried {self.max_retries} times with exponential backoff, but the rate limit persisted.',
                    'technical_error': str(error),
                    'suggestions': [
                        'This is temporary - try running the command again in a few minutes',
                        'Consider processing fewer documents at once using --days with a smaller number',
                        'Use --accepted flag to process only accepted meetings',
                        'Process meetings in smaller batches'
                    ]
                }
            elif status_code >= 500:
                return {
                    'type': 'server_error',
                    'user_message': 'Google Drive service temporarily unavailable',
                    'detailed_message': f'Google\'s servers are experiencing issues (HTTP {status_code}). This is temporary.',
                    'technical_error': str(error),
                    'suggestions': [
                        'Try again in a few minutes',
                        'Check Google Workspace Status page for service issues'
                    ]
                }
            else:
                return {
                    'type': 'api_error',
                    'user_message': f'Google API error (HTTP {status_code})',
                    'detailed_message': f'An unexpected API error occurred while accessing document {file_id}.',
                    'technical_error': str(error),
                    'suggestions': [
                        'Try again in a few moments',
                        'Check your internet connection'
                    ]
                }
        else:
            return {
                'type': 'unknown_error',
                'user_message': 'Unknown error accessing document',
                'detailed_message': f'An unexpected error occurred while processing document {file_id}.',
                'technical_error': str(error),
                'suggestions': [
                    'Try again later',
                    'Check your internet connection and authentication'
                ]
            }
    
    def _retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """Retry a function with exponential backoff for rate limiting and transient errors.
        
        Args:
            func: Function to retry
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            The last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                return func(*args, **kwargs)
                
            except HttpError as e:
                last_exception = e
                status_code = e.resp.status
                
                # Only retry on rate limiting (429) and server errors (5xx)
                if status_code == 429 or status_code >= 500:
                    if attempt < self.max_retries:
                        # Calculate delay with exponential backoff + jitter
                        delay = min(
                            self.base_delay * (2 ** attempt) + random.uniform(0, 1),
                            self.max_delay
                        )
                        
                        logger.warning(
                            f"HTTP {status_code} error (attempt {attempt + 1}/{self.max_retries + 1}). "
                            f"Retrying in {delay:.1f} seconds..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            f"HTTP {status_code} error after {self.max_retries + 1} attempts. Giving up."
                        )
                        break
                else:
                    # Don't retry on other errors (404, 403, etc.)
                    logger.debug(f"HTTP {status_code} error - not retrying")
                    break
                    
            except Exception as e:
                # Don't retry on non-HTTP errors
                last_exception = e
                logger.debug(f"Non-HTTP error - not retrying: {e}")
                break
        
        # If we get here, all retries failed
        raise last_exception
    
    def extract_document_id(self, doc_url: str) -> Optional[str]:
        """Extract document ID from Google Docs URL.
        
        Args:
            doc_url: Google Docs URL.
            
        Returns:
            Document ID if found, None otherwise.
        """
        if not doc_url:
            return None
            
        patterns = [
            r'/document/d/([a-zA-Z0-9-_]+)',      # Google Docs
            r'/spreadsheets/d/([a-zA-Z0-9-_]+)',  # Google Sheets
            r'/presentation/d/([a-zA-Z0-9-_]+)',  # Google Slides
            r'/file/d/([a-zA-Z0-9-_]+)',          # Generic Drive URLs
            r'id=([a-zA-Z0-9-_]+)',               # Query parameter
        ]
        
        # Check URL patterns first
        for pattern in patterns:
            match = re.search(pattern, doc_url)
            if match:
                return match.group(1)
        
        # Only treat as direct ID if it looks like a valid Google Drive ID (no invalid characters)
        if re.match(r'^[a-zA-Z0-9-_]{20,}$', doc_url):
            return doc_url
        
        logger.warning(f"Could not extract document ID from URL: {doc_url}")
        return None
    
    def get_document_metadata(self, doc_id: str) -> Dict[str, Any]:
        """Get metadata for a Google Doc.
        
        Args:
            doc_id: Google Docs document ID.
            
        Returns:
            Dictionary with document metadata.
        """
        try:
            # Get file metadata from Drive API with retry
            file_metadata = self._retry_with_backoff(
                lambda: self.drive_service.files().get(
                    fileId=doc_id,
                    fields='id,name,createdTime,modifiedTime,owners,shared'
                ).execute()
            )
            
            # Get document content structure from Docs API with retry
            doc = self._retry_with_backoff(
                lambda: self.docs_service.documents().get(documentId=doc_id).execute()
            )
            
            metadata = {
                'id': file_metadata['id'],
                'title': file_metadata['name'],
                'created': file_metadata['createdTime'],
                'modified': file_metadata['modifiedTime'],
                'owners': [owner.get('displayName', owner.get('emailAddress', 'Unknown')) 
                          for owner in file_metadata.get('owners', [])],
                'shared': file_metadata.get('shared', False),
                'revision_id': doc.get('revisionId'),
                'word_count': self._estimate_word_count(doc)
            }
            
            return metadata
            
        except Exception as e:
            error_info = self._parse_google_api_error(e, doc_id)
            logger.error(f"Error getting document metadata for {doc_id}: {error_info['user_message']}")
            logger.debug(f"Technical details: {error_info['technical_error']}")
            
            return {
                'id': doc_id, 
                'title': f"Error: {error_info['user_message']}",
                'error': error_info['user_message'],
                'error_type': error_info['type'],
                'technical_error': error_info['technical_error']
            }
    
    def convert_to_markdown(self, doc_id: str, use_native_export: bool = True, fallback_enabled: bool = True) -> Dict[str, Any]:
        """Convert a Google file to Markdown.
        
        Args:
            doc_id: Google Drive file ID.
            use_native_export: If True, use native Google export (recommended).
                             If False, use manual parsing method for Docs.
            fallback_enabled: If True and native export fails, fall back to manual parsing.
            
        Returns:
            Dictionary with markdown content and metadata.
        """
        # First, check the file type
        file_info = self._get_file_info(doc_id)
        if not file_info['success']:
            return file_info
        
        mime_type = file_info['mime_type']
        file_type = file_info['file_type']
        
        logger.info(f"Processing {file_type} file: {doc_id}")
        
        # Handle different file types
        if mime_type == 'application/vnd.google-apps.document':
            # Google Docs
            if use_native_export:
                return self._convert_using_native_export(doc_id, fallback_enabled, 'text/markdown')
            else:
                return self._convert_using_manual_parsing(doc_id)
        
        elif mime_type in ['application/vnd.google-apps.spreadsheet', 'application/vnd.google-apps.presentation']:
            # Google Sheets or Slides - use native export only
            export_mime = 'text/markdown' if mime_type == 'application/vnd.google-apps.presentation' else 'text/csv'
            return self._convert_using_native_export(doc_id, False, export_mime)
        
        else:
            # Unsupported file type
            return {
                'content': f"# {file_info.get('title', 'Unsupported File')}\n\n**File Type**: {file_type}\n**Note**: This file type cannot be converted to Markdown.\n**File ID**: {doc_id}",
                'metadata': file_info,
                'success': True,
                'export_method': 'unsupported_placeholder'
            }
    
    def _get_file_info(self, file_id: str) -> Dict[str, Any]:
        """Get file information including type from Google Drive.
        
        Args:
            file_id: Google Drive file ID.
            
        Returns:
            Dictionary with file information.
        """
        try:
            file_metadata = self._retry_with_backoff(
                lambda: self.drive_service.files().get(
                    fileId=file_id,
                    fields='id,name,mimeType,createdTime,modifiedTime,owners,shared'
                ).execute()
            )
            
            mime_type = file_metadata.get('mimeType', '')
            
            # Determine human-readable file type
            file_type_map = {
                'application/vnd.google-apps.document': 'Google Docs',
                'application/vnd.google-apps.spreadsheet': 'Google Sheets', 
                'application/vnd.google-apps.presentation': 'Google Slides',
                'application/vnd.google-apps.folder': 'Google Drive Folder',
                'application/pdf': 'PDF',
                'text/plain': 'Text File',
                'image/': 'Image File',
                'video/': 'Video File'
            }
            
            file_type = 'Unknown File'
            for mime_prefix, type_name in file_type_map.items():
                if mime_type.startswith(mime_prefix) or mime_type == mime_prefix:
                    file_type = type_name
                    break
            
            return {
                'success': True,
                'id': file_metadata['id'],
                'title': file_metadata['name'],
                'mime_type': mime_type,
                'file_type': file_type,
                'created': file_metadata.get('createdTime'),
                'modified': file_metadata.get('modifiedTime'),
                'owners': [owner.get('displayName', owner.get('emailAddress', 'Unknown')) 
                          for owner in file_metadata.get('owners', [])],
                'shared': file_metadata.get('shared', False)
            }
            
        except Exception as e:
            error_info = self._parse_google_api_error(e, file_id)
            
            # Log the detailed error for debugging
            logger.error(f"Error getting file info for {file_id}: {error_info['user_message']}")
            logger.debug(f"Technical details: {error_info['technical_error']}")
            
            # Create user-friendly content for the markdown output
            content_parts = [
                f"# ⚠️ Document Access Error",
                "",
                f"**File ID**: `{file_id}`",
                f"**Error**: {error_info['user_message']}",
                "",
                "## What this means:",
                error_info['detailed_message'],
                "",
                "## Suggested actions:",
            ]
            
            for suggestion in error_info['suggestions']:
                content_parts.append(f"• {suggestion}")
                
            content_parts.extend([
                "",
                "---",
                "*This document was skipped during processing but the meeting notes will continue.*"
            ])
            
            return {
                'success': False,
                'id': file_id,
                'title': f"Error: {error_info['user_message']}",
                'error': error_info['user_message'],
                'error_type': error_info['type'],
                'technical_error': error_info['technical_error'],
                'content': '\n'.join(content_parts),
                'metadata': {
                    'id': file_id, 
                    'error': error_info['user_message'],
                    'error_type': error_info['type']
                }
            }
    
    def _convert_using_native_export(self, doc_id: str, fallback_enabled: bool = True, export_mime: str = 'text/markdown') -> Dict[str, Any]:
        """Convert a Google file using native export API.
        
        Args:
            doc_id: Google Drive file ID.
            fallback_enabled: Whether to fall back to manual parsing on failure.
            export_mime: MIME type for export (text/markdown, text/csv, etc.).
            
        Returns:
            Dictionary with content and metadata.
        """
        try:
            export_type = export_mime.split('/')[-1].upper()
            logger.info(f"Converting file {doc_id} using native {export_type} export")
            
            # Export file with retry
            content_bytes = self._retry_with_backoff(
                lambda: self.drive_service.files().export(
                    fileId=doc_id,
                    mimeType=export_mime
                ).execute()
            )
            content = content_bytes.decode('utf-8')
            
            # For CSV files, add some basic markdown formatting
            if export_mime == 'text/csv':
                content = self._format_csv_as_markdown(content, doc_id)
            
            # Get metadata
            metadata = self.get_document_metadata(doc_id)
            
            logger.info(f"Successfully exported file {doc_id} as {export_type} ({len(content)} chars)")
            
            return {
                'content': content,
                'metadata': metadata,
                'success': True,
                'export_method': f'native_{export_type.lower()}'
            }
            
        except Exception as e:
            error_info = self._parse_google_api_error(e, doc_id)
            logger.warning(f"Native {export_type} export failed for file {doc_id}: {error_info['user_message']}")
            logger.debug(f"Technical details: {error_info['technical_error']}")
            
            if fallback_enabled and export_mime == 'text/markdown':
                logger.info(f"Falling back to manual parsing for document {doc_id}")
                return self._convert_using_manual_parsing(doc_id)
            else:
                # Get basic file info for error message
                file_info = self._get_file_info(doc_id)
                file_type = file_info.get('file_type', 'Unknown File')
                title = file_info.get('title', 'Unknown')
                
                # Create user-friendly error content
                content_parts = [
                    f"# {title}",
                    "",
                    f"**File Type**: {file_type}",
                    f"**File ID**: `{doc_id}`",
                    f"**Export Error**: {error_info['user_message']}",
                    "",
                    "## What happened:",
                    error_info['detailed_message'],
                    "",
                    "## Suggested actions:",
                ]
                
                for suggestion in error_info['suggestions']:
                    content_parts.append(f"• {suggestion}")
                    
                content_parts.extend([
                    "",
                    "---",
                    f"*Failed to export as {export_type}, but processing will continue.*"
                ])
                
                return {
                    'content': '\n'.join(content_parts),
                    'metadata': {**file_info, 'export_error': error_info['user_message']},
                    'success': True,  # Mark as success with error message instead of failing
                    'export_method': 'error_placeholder',
                    'error_type': error_info['type']
                }
    
    def _convert_using_manual_parsing(self, doc_id: str) -> Dict[str, Any]:
        """Convert a Google Doc to Markdown using manual parsing (fallback method).
        
        Args:
            doc_id: Google Docs document ID.
            
        Returns:
            Dictionary with markdown content and metadata.
        """
        try:
            logger.info(f"Converting document {doc_id} using manual parsing")
            
            # Get document content with retry
            doc = self._retry_with_backoff(
                lambda: self.docs_service.documents().get(documentId=doc_id).execute()
            )
            
            # Extract text content
            content = self._extract_text_content(doc)
            
            # Convert to markdown
            markdown_content = self._text_to_markdown(content, doc)
            
            # Get metadata
            metadata = self.get_document_metadata(doc_id)
            
            return {
                'content': markdown_content,
                'metadata': metadata,
                'success': True,
                'export_method': 'manual'
            }
            
        except Exception as e:
            error_info = self._parse_google_api_error(e, doc_id)
            logger.error(f"Error converting document {doc_id} to markdown: {error_info['user_message']}")
            logger.debug(f"Technical details: {error_info['technical_error']}")
            
            return {
                'content': '',
                'metadata': {
                    'id': doc_id, 
                    'error': error_info['user_message'],
                    'error_type': error_info['type']
                },
                'success': False,
                'error': error_info['user_message'],
                'error_type': error_info['type']
            }
    
    def _extract_text_content(self, doc: Dict[str, Any]) -> str:
        """Extract plain text content from a Google Doc.
        
        Args:
            doc: Google Docs document object.
            
        Returns:
            Plain text content.
        """
        content_parts = []
        
        body = doc.get('body', {})
        content = body.get('content', [])
        
        for element in content:
            if 'paragraph' in element:
                paragraph_text = self._extract_paragraph_text(element['paragraph'])
                if paragraph_text:
                    content_parts.append(paragraph_text)
            elif 'table' in element:
                table_text = self._extract_table_text(element['table'])
                if table_text:
                    content_parts.append(table_text)
        
        return '\n\n'.join(content_parts)
    
    def _extract_paragraph_text(self, paragraph: Dict[str, Any]) -> str:
        """Extract text from a paragraph element.
        
        Args:
            paragraph: Paragraph element from Google Docs.
            
        Returns:
            Text content of the paragraph.
        """
        text_parts = []
        elements = paragraph.get('elements', [])
        
        for element in elements:
            if 'textRun' in element:
                text_content = element['textRun'].get('content', '')
                text_parts.append(text_content)
        
        return ''.join(text_parts).strip()
    
    def _extract_table_text(self, table: Dict[str, Any]) -> str:
        """Extract text from a table element.
        
        Args:
            table: Table element from Google Docs.
            
        Returns:
            Text representation of the table.
        """
        table_parts = []
        rows = table.get('tableRows', [])
        
        for row in rows:
            row_parts = []
            cells = row.get('tableCells', [])
            
            for cell in cells:
                cell_content = []
                for content_element in cell.get('content', []):
                    if 'paragraph' in content_element:
                        cell_text = self._extract_paragraph_text(content_element['paragraph'])
                        if cell_text:
                            cell_content.append(cell_text)
                
                row_parts.append(' '.join(cell_content))
            
            if any(part.strip() for part in row_parts):
                table_parts.append(' | '.join(row_parts))
        
        return '\n'.join(table_parts)
    
    def _text_to_markdown(self, text: str, doc: Dict[str, Any]) -> str:
        """Convert plain text to markdown with basic formatting.
        
        Args:
            text: Plain text content.
            doc: Original document for style information.
            
        Returns:
            Markdown formatted text.
        """
        # Basic cleanup
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Convert basic patterns to markdown
            line = self._apply_basic_markdown_formatting(line)
            formatted_lines.append(line)
        
        return '\n\n'.join(formatted_lines)
    
    def _apply_basic_markdown_formatting(self, text: str) -> str:
        """Apply basic markdown formatting to text.
        
        Args:
            text: Input text.
            
        Returns:
            Text with basic markdown formatting.
        """
        # Look for patterns that suggest headers
        if len(text) < 100 and text.isupper():
            return f"## {text.title()}"
        
        if text.endswith(':') and len(text) < 80:
            return f"### {text}"
        
        # Look for bullet points
        if re.match(r'^[\u2022\u25cf\u25e6\u2023\u2043]\s+', text):
            return f"- {text[2:].strip()}"
        
        if re.match(r'^\d+[\.\)]\s+', text):
            number = re.match(r'^(\d+)', text).group(1)
            content = re.sub(r'^\d+[\.\)]\s+', '', text)
            return f"{number}. {content}"
        
        return text
    
    def _estimate_word_count(self, doc: Dict[str, Any]) -> int:
        """Estimate word count for a document.
        
        Args:
            doc: Google Docs document object.
            
        Returns:
            Estimated word count.
        """
        content = self._extract_text_content(doc)
        words = content.split()
        return len(words)
    
    def _format_csv_as_markdown(self, csv_content: str, file_id: str) -> str:
        """Format CSV content as a markdown table.
        
        Args:
            csv_content: Raw CSV content.
            file_id: File ID for reference.
            
        Returns:
            Markdown formatted content.
        """
        try:
            lines = csv_content.strip().split('\n')
            if not lines:
                return f"# Google Sheets Export\n\n**File ID**: {file_id}\n\n*Empty spreadsheet*"
            
            markdown_lines = [f"# Google Sheets Export", "", f"**File ID**: {file_id}", ""]
            
            # Convert first few rows to markdown table
            max_rows = min(50, len(lines))  # Limit to first 50 rows
            
            for i, line in enumerate(lines[:max_rows]):
                if i == 0:
                    # Header row
                    cells = [cell.strip('"').replace('""', '"') for cell in line.split(',')]
                    markdown_lines.append('| ' + ' | '.join(cells) + ' |')
                    markdown_lines.append('|' + '---|' * len(cells))
                else:
                    # Data rows
                    cells = [cell.strip('"').replace('""', '"') for cell in line.split(',')]
                    markdown_lines.append('| ' + ' | '.join(cells) + ' |')
            
            if len(lines) > max_rows:
                markdown_lines.append("")
                markdown_lines.append(f"*... ({len(lines) - max_rows} more rows not shown)*")
            
            return '\n'.join(markdown_lines)
            
        except Exception as e:
            logger.warning(f"Error formatting CSV as markdown for {file_id}: {e}")
            return f"# Google Sheets Export\n\n**File ID**: {file_id}\n\n```\n{csv_content[:1000]}\n```\n\n*Note: Raw CSV format due to formatting error*"