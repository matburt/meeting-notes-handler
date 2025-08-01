"""Google Meet meeting fetcher and processor."""

import re
import logging
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Callable
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import Config
from .docs_converter import DocsConverter
from .file_organizer import FileOrganizer
from .smart_extractor import SmartContentExtractor
from .series_tracker import MeetingSeriesTracker

logger = logging.getLogger(__name__)

class GoogleMeetFetcher:
    """Fetches meeting notes from Google Calendar and Google Docs."""
    
    def __init__(self, config: Config):
        """Initialize the Google Meet fetcher.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.credentials = None
        self.calendar_service = None
        self.docs_converter = None
        self.file_organizer = FileOrganizer(config.output_directory)
        self.series_tracker = MeetingSeriesTracker(config.output_directory)
        self.smart_extractor = SmartContentExtractor(config.output_directory)
        
        # Rate limiting configuration (same as DocsConverter)
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay in seconds
        self.max_delay = 60.0  # Maximum delay in seconds
    
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
                            f"Calendar API HTTP {status_code} error (attempt {attempt + 1}/{self.max_retries + 1}). "
                            f"Retrying in {delay:.1f} seconds..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            f"Calendar API HTTP {status_code} error after {self.max_retries + 1} attempts. Giving up."
                        )
                        break
                else:
                    # Don't retry on other errors (404, 403, etc.)
                    logger.debug(f"Calendar API HTTP {status_code} error - not retrying")
                    break
                    
            except Exception as e:
                # Don't retry on non-HTTP errors
                last_exception = e
                logger.debug(f"Calendar API non-HTTP error - not retrying: {e}")
                break
        
        # If we get here, all retries failed
        raise last_exception
    
    def authenticate(self) -> bool:
        """Authenticate with Google APIs.
        
        Returns:
            True if authentication successful, False otherwise.
        """
        try:
            creds = None
            
            # Try Application Default Credentials first (gcloud CLI)
            try:
                from google.auth import default
                creds, project = default(scopes=self.config.google_scopes)
                logger.info("Using Application Default Credentials (gcloud CLI)")
            except Exception as e:
                logger.debug(f"Application Default Credentials not available: {e}")
                creds = None
            
            # Fallback to manual OAuth flow if ADC not available
            if not creds:
                # Load existing token
                if self.config.google_token_file.exists():
                    creds = Credentials.from_authorized_user_file(
                        str(self.config.google_token_file), 
                        self.config.google_scopes
                    )
                
                # If there are no (valid) credentials available, let the user log in
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        if not self.config.google_credentials_file.exists():
                            logger.error(f"No authentication method available. Please either:")
                            logger.error(f"1. Run 'gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/documents.readonly'")
                            logger.error(f"2. Or provide credentials file at: {self.config.google_credentials_file}")
                            return False
                        
                        flow = InstalledAppFlow.from_client_secrets_file(
                            str(self.config.google_credentials_file), 
                            self.config.google_scopes
                        )
                        creds = flow.run_local_server(port=0)
                    
                    # Save credentials for the next run
                    with open(self.config.google_token_file, 'w') as token:
                        token.write(creds.to_json())
            
            self.credentials = creds
            self.calendar_service = build('calendar', 'v3', credentials=creds)
            self.docs_converter = DocsConverter(creds)
            
            logger.info("Successfully authenticated with Google APIs")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def fetch_recent_meetings(self, days_back: Optional[int] = None, accepted_only: bool = False, gemini_only: bool = False) -> List[Dict[str, Any]]:
        """Fetch recent Google Meet meetings from calendar.
        
        Args:
            days_back: Number of days back to search. Uses config default if not provided.
            accepted_only: If True, only fetch meetings the user has accepted or is tentative.
            gemini_only: If True, only fetch Gemini notes and transcripts.
            
        Returns:
            List of meeting dictionaries.
        """
        if not self.calendar_service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        days_back = days_back or self.config.days_back
        
        # Calculate time range
        now = datetime.utcnow()
        time_min = (now - timedelta(days=days_back)).isoformat() + 'Z'
        time_max = now.isoformat() + 'Z'
        
        try:
            logger.info(f"Fetching meetings from {days_back} days back")
            
            events_result = self._retry_with_backoff(
                lambda: self.calendar_service.events().list(
                    calendarId='primary',
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=100,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
            )
            
            events = events_result.get('items', [])
            
            # Filter for Google Meet meetings
            meet_meetings = []
            for event in events:
                if self._is_google_meet_meeting(event):
                    if accepted_only and not self._is_user_attending(event):
                        logger.debug(f"Skipping meeting due to non-accepted status: {event.get('summary')}")
                        continue

                    meeting_info = self._extract_meeting_info(event, gemini_only)
                    if meeting_info:
                        meet_meetings.append(meeting_info)
            
            logger.info(f"Found {len(meet_meetings)} Google Meet meetings")
            return meet_meetings
            
        except Exception as e:
            logger.error(f"Error fetching meetings: {e}")
            return []

    def _is_user_attending(self, event: Dict[str, Any]) -> bool:
        """Check if the current user has accepted or is tentatively attending the event."""
        attendees = event.get('attendees', [])
        for attendee in attendees:
            if attendee.get('self'):
                status = attendee.get('responseStatus')
                # Return True if user has accepted, is tentative, or hasn't responded yet.
                # Exclude only if they have explicitly declined.
                return status != 'declined'
        
        # If the user is the organizer, they are considered to be attending.
        if event.get('organizer', {}).get('self'):
            return True

        # If no 'self' attendee is found, but there are attendees, assume not attending.
        # If there are no attendees, it might be a personal event, so we include it.
        return not attendees

    def _is_google_meet_meeting(self, event: Dict[str, Any]) -> bool:
        """Check if an event is a Google Meet meeting.
        
        Args:
            event: Calendar event object.
            
        Returns:
            True if the event is a Google Meet meeting.
        """
        # Check for Google Meet in various fields
        keywords = self.config.calendar_keywords
        
        # Check description
        description = event.get('description', '').lower()
        if any(keyword.lower() in description for keyword in keywords):
            return True
        
        # Check location
        location = event.get('location', '').lower()
        if any(keyword.lower() in location for keyword in keywords):
            return True
        
        # Check conference data
        conference_data = event.get('conferenceData', {})
        if conference_data.get('conferenceSolution', {}).get('name') == 'Google Meet':
            return True
        
        # Check hangout link
        if event.get('hangoutLink'):
            return True
        
        return False
    
    def _extract_meeting_info(self, event: Dict[str, Any], gemini_only: bool = False) -> Optional[Dict[str, Any]]:
        """Extract relevant information from a calendar event.
        
        Args:
            event: Calendar event object.
            gemini_only: If True, only extract Gemini notes and transcripts.
            
        Returns:
            Dictionary with meeting information.
        """
        try:
            start_time = event['start'].get('dateTime', event['start'].get('date'))
            end_time = event['end'].get('dateTime', event['end'].get('date'))
            
            if 'T' not in start_time:  # All-day event
                start_dt = datetime.fromisoformat(start_time)
            else:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            
            # Extract all docs links first
            all_docs_links = self._extract_all_docs_links(event)
            
            # Filter to only Gemini docs if requested
            if gemini_only:
                docs_links = self._filter_gemini_documents(event, all_docs_links)
            else:
                docs_links = all_docs_links
            
            meeting_info = {
                'id': event['id'],
                'title': event.get('summary', 'Untitled Meeting'),
                'description': event.get('description', ''),
                'start_time': start_dt,
                'end_time': datetime.fromisoformat(end_time.replace('Z', '+00:00')) if 'T' in end_time else None,
                'attendees': [attendee.get('email') for attendee in event.get('attendees', [])],
                'organizer': event.get('organizer', {}).get('email'),
                'location': event.get('location', ''),
                'hangout_link': event.get('hangoutLink'),
                'docs_links': docs_links,
                'attachments': event.get('attachments', [])
            }
            
            return meeting_info
            
        except Exception as e:
            logger.error(f"Error extracting meeting info from event {event.get('id', 'unknown')}: {e}")
            return None
    
    def _extract_all_docs_links(self, event: Dict[str, Any]) -> List[str]:
        """Extract Google Docs links from both description and attachments.
        
        Args:
            event: Calendar event object.
            
        Returns:
            List of Google Docs URLs found in the event.
        """
        docs_links = []
        
        # Extract from description
        description_links = self._extract_docs_links(event.get('description', ''))
        docs_links.extend(description_links)
        
        # Extract from attachments (e.g., Gemini notes)
        attachments = event.get('attachments', [])
        for attachment in attachments:
            file_url = attachment.get('fileUrl')
            file_id = attachment.get('fileId')
            
            # Try to use fileUrl first, then construct from fileId if needed
            if file_url:
                if 'docs.google.com' in file_url or 'drive.google.com' in file_url:
                    docs_links.append(file_url)
                    logger.info(f"Found attachment: {attachment.get('title', 'Untitled')} - {file_url}")
            elif file_id:
                # Construct Google Docs URL from file ID
                constructed_url = f"https://docs.google.com/document/d/{file_id}/edit"
                docs_links.append(constructed_url)
                logger.info(f"Found attachment (via fileId): {attachment.get('title', 'Untitled')} - {constructed_url}")
        
        return list(set(docs_links))  # Remove duplicates
    
    def _is_gemini_or_transcript_document(self, doc_url: str, attachment_info: Dict[str, Any] = None) -> bool:
        """Check if a document is a Gemini note or transcript.
        
        Args:
            doc_url: Document URL.
            attachment_info: Optional attachment metadata.
            
        Returns:
            True if document appears to be Gemini notes or transcript.
        """
        # Check attachment title if available
        if attachment_info and attachment_info.get('title'):
            title = attachment_info['title'].lower()
            gemini_keywords = [
                'gemini', 'notes by gemini', 'meeting notes', 'transcript',
                'recording', 'chat', 'meeting summary', 'auto-generated'
            ]
            if any(keyword in title for keyword in gemini_keywords):
                return True
        
        # Check URL patterns that might indicate Gemini content
        # Gemini notes often have specific URL patterns or parameters
        if 'meet_tnfm_calendar' in doc_url:
            return True
        
        # For now, if we can't determine, assume it might be Gemini-related
        # This is conservative - we'll include it rather than miss important content
        return False
    
    def _filter_gemini_documents(self, event: Dict[str, Any], docs_links: List[str]) -> List[str]:
        """Filter document links to only include Gemini notes and transcripts.
        
        Args:
            event: Calendar event object.
            docs_links: List of all document URLs.
            
        Returns:
            Filtered list of document URLs.
        """
        if not docs_links:
            return []
        
        gemini_docs = []
        attachments = event.get('attachments', [])
        
        # Create a map of file URLs to attachment info
        attachment_map = {}
        for attachment in attachments:
            file_url = attachment.get('fileUrl')
            file_id = attachment.get('fileId')
            if file_url:
                attachment_map[file_url] = attachment
            elif file_id:
                # Try to match constructed URLs
                constructed_url = f"https://docs.google.com/document/d/{file_id}/edit"
                attachment_map[constructed_url] = attachment
        
        for doc_url in docs_links:
            attachment_info = attachment_map.get(doc_url)
            
            if self._is_gemini_or_transcript_document(doc_url, attachment_info):
                gemini_docs.append(doc_url)
                logger.info(f"Including Gemini/transcript document: {attachment_info.get('title', doc_url) if attachment_info else doc_url}")
            else:
                logger.info(f"Skipping non-Gemini document: {attachment_info.get('title', doc_url) if attachment_info else doc_url}")
        
        return gemini_docs
    
    def _extract_docs_links(self, description: str) -> List[str]:
        """Extract Google Docs links from meeting description.
        
        Args:
            description: Meeting description text.
            
        Returns:
            List of Google Docs URLs found in the description.
        """
        if not description:
            return []
        
        # Patterns for Google Docs URLs
        patterns = [
            r'https://docs\.google\.com/document/d/[a-zA-Z0-9-_]+[/\w]*',
            r'https://drive\.google\.com/file/d/[a-zA-Z0-9-_]+[/\w]*'
        ]
        
        docs_links = []
        for pattern in patterns:
            matches = re.findall(pattern, description)
            docs_links.extend(matches)
        
        return list(set(docs_links))  # Remove duplicates
    
    def process_meeting_notes(self, meeting: Dict[str, Any], save_to_file: bool = True, 
                             smart_filtering: bool = False, diff_mode: bool = False) -> Dict[str, Any]:
        """Process meeting notes by fetching and converting associated docs.
        
        Args:
            meeting: Meeting information dictionary.
            save_to_file: Whether to save the processed notes to file.
            smart_filtering: Whether to apply smart content filtering for new content only.
            
        Returns:
            Dictionary with processed meeting notes and metadata.
        """
        if not self.docs_converter:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        result = {
            'meeting': meeting,
            'notes': [],
            'success': False,
            'errors': []
        }
        
        docs_links = meeting.get('docs_links', [])
        attachments = meeting.get('attachments', [])
        
        if not docs_links:
            logger.warning(f"No docs links found for meeting: {meeting['title']}")
            result['errors'].append("No Google Docs links found in meeting description or attachments")
            return result
        
        # Log document sources
        attachment_count = len(attachments)
        total_docs = len(docs_links)
        logger.info(f"Found {total_docs} document(s) for meeting '{meeting['title']}' ({attachment_count} from attachments)")
        
        # Process each document
        for doc_url in docs_links:
            doc_id = self.docs_converter.extract_document_id(doc_url)
            if not doc_id:
                error_msg = f"Could not extract document ID from URL: {doc_url}"
                logger.warning(error_msg)
                result['errors'].append(error_msg)
                continue
            
            try:
                logger.info(f"Converting document: {doc_id}")
                conversion_result = self.docs_converter.convert_to_markdown(
                    doc_id, 
                    use_native_export=self.config.use_native_export,
                    fallback_enabled=self.config.fallback_to_manual
                )
                
                if conversion_result['success']:
                    note_data = {
                        'doc_id': doc_id,
                        'doc_url': doc_url,
                        'content': conversion_result['content'],
                        'metadata': conversion_result['metadata']
                    }
                    result['notes'].append(note_data)
                    
                    # Check if this was an error placeholder that succeeded
                    if conversion_result.get('export_method') == 'error_placeholder':
                        logger.warning(f"Document {doc_id} converted with errors - check content for details")
                    else:
                        logger.info(f"Successfully converted document: {doc_id}")
                else:
                    # Provide more detailed error information
                    error_type = conversion_result.get('error_type', 'unknown')
                    error_msg = conversion_result.get('error', 'Unknown error')
                    
                    if error_type == 'file_not_found':
                        friendly_error = f"Document not found (may be deleted or private): {doc_url}"
                    elif error_type == 'access_denied':
                        friendly_error = f"Access denied to document (permission required): {doc_url}"
                    elif error_type == 'rate_limit':
                        friendly_error = f"Rate limit exceeded - will retry later: {doc_url}"
                    else:
                        friendly_error = f"Failed to convert document {doc_id}: {error_msg}"
                    
                    logger.error(friendly_error)
                    result['errors'].append(friendly_error)
                    
            except Exception as e:
                error_msg = f"Error processing document {doc_id}: {e}"
                logger.error(error_msg)
                result['errors'].append(error_msg)
        
        if result['notes']:
            result['success'] = True
            
            # Apply smart content filtering if enabled
            if smart_filtering:
                try:
                    logger.info(f"Applying smart content filtering for meeting: {meeting['title']}")
                    
                    # Prepare documents for filtering
                    documents = []
                    for note in result['notes']:
                        doc_dict = {
                            'title': note['metadata'].get('title', 'Untitled Document'),
                            'url': note['doc_url'],
                            'content': note['content'],
                            'metadata': note['metadata']
                        }
                        documents.append(doc_dict)
                    
                    # Apply smart filtering
                    filtering_result = self.smart_extractor.extract_new_content_only(meeting, documents)
                    
                    # Register this meeting with the series tracker if new content was found
                    if filtering_result.has_new_content and filtering_result.series_id:
                        meeting_file_path = f"{meeting['start_time'].strftime('%Y-W%U')}/meeting_{meeting['start_time'].strftime('%Y%m%d_%H%M%S')}_{meeting['title'].lower().replace(' ', '_')}.md"
                        self.smart_extractor.series_tracker.add_meeting_to_series(filtering_result.series_id, meeting_file_path)
                    
                    if filtering_result.has_new_content:
                        # Replace notes with filtered content
                        filtered_notes = []
                        for filtered_doc in filtering_result.filtered_documents:
                            filtered_note = {
                                'doc_id': self.docs_converter.extract_document_id(filtered_doc.original_url),
                                'doc_url': filtered_doc.original_url,
                                'content': filtered_doc.filtered_content,
                                'metadata': {
                                    'title': filtered_doc.title,
                                    'change_summary': filtered_doc.change_summary,
                                    'doc_type': filtered_doc.doc_type.value
                                }
                            }
                            filtered_notes.append(filtered_note)
                        
                        result['notes'] = filtered_notes
                        result['filtering_applied'] = True
                        result['content_reduction'] = filtering_result.content_reduction_percentage
                        result['original_word_count'] = filtering_result.original_word_count
                        result['filtered_word_count'] = filtering_result.filtered_word_count
                        
                        logger.info(f"Smart filtering reduced content by {filtering_result.content_reduction_percentage:.1f}% "
                                   f"({filtering_result.original_word_count} → {filtering_result.filtered_word_count} words)")
                    else:
                        logger.info("No new content found after smart filtering - no files will be saved")
                        result['notes'] = []
                        result['filtering_applied'] = True
                        result['content_reduction'] = 100.0
                        result['has_new_content'] = False
                        
                except Exception as e:
                    error_msg = f"Error during smart content filtering: {e}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
                    # Continue with unfiltered content if filtering fails
            
            if save_to_file and result['notes']:
                try:
                    self._save_meeting_notes(meeting, result['notes'], diff_mode=diff_mode)
                    logger.info(f"Saved notes for meeting: {meeting['title']}")
                except Exception as e:
                    error_msg = f"Error saving meeting notes: {e}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
        
        return result
    
    def _save_meeting_notes(self, meeting: Dict[str, Any], notes: List[Dict[str, Any]], diff_mode: bool = False) -> None:
        """Save meeting notes to organized file structure.
        
        Args:
            meeting: Meeting information.
            notes: List of note documents.
        """
        # Combine all notes into a single document
        content_parts = []
        
        # Add meeting information
        content_parts.append(f"**Date:** {meeting['start_time'].strftime('%Y-%m-%d %H:%M')}")
        if meeting.get('organizer'):
            content_parts.append(f"**Organizer:** {meeting['organizer']}")
        
        if meeting.get('attendees'):
            attendee_list = ', '.join(meeting['attendees'])
            content_parts.append(f"**Attendees:** {attendee_list}")
        
        if meeting.get('hangout_link'):
            content_parts.append(f"**Meeting Link:** {meeting['hangout_link']}")
        
        content_parts.append("")  # Empty line
        
        # Add each document's content
        for i, note in enumerate(notes, 1):
            if len(notes) > 1:
                content_parts.append(f"## Document {i}")
                if note['metadata'].get('title'):
                    content_parts.append(f"**Title:** {note['metadata']['title']}")
                content_parts.append("")
            
            content_parts.append(note['content'])
            content_parts.append("")  # Empty line between documents
        
        full_content = "\n".join(content_parts)
        
        # Prepare metadata
        metadata = {
            'meeting_id': meeting['id'],
            'organizer': meeting.get('organizer'),
            'attendees_count': len(meeting.get('attendees', [])),
            'docs_count': len(notes),
            'docs_links': [note['doc_url'] for note in notes]
        }
        
        # Handle diff mode
        if diff_mode:
            # Identify or create meeting series
            series_id = self.series_tracker.identify_series(meeting)
            if not series_id:
                series_id = self.series_tracker.create_new_series(meeting)
            
            # Check if content has changed from previous meeting
            meeting_date = meeting['start_time'].strftime('%Y-%m-%d')
            has_changed, similarity = self.series_tracker.has_content_changed(
                series_id, meeting_date, full_content
            )
            
            if not has_changed and similarity is not None:
                logger.info(f"Content unchanged for meeting {meeting['title']} (similarity: {similarity:.1f}%)")
                return  # Skip saving if content hasn't changed
            
            logger.info(f"Content changed for meeting {meeting['title']}, saving...")
            
            # Store content signature for future comparisons
            self.series_tracker.store_meeting_content_signature(
                series_id, meeting_date, full_content
            )
        
        # Save to file
        self.file_organizer.save_meeting_note(
            content=full_content,
            meeting_date=meeting['start_time'],
            title=meeting['title'],
            metadata=metadata
        )
        
        # Always store content signature for series tracking (even if not in diff mode)
        if not diff_mode:
            try:
                series_id = self.series_tracker.identify_series(meeting)
                if not series_id:
                    series_id = self.series_tracker.create_new_series(meeting)
                
                meeting_date = meeting['start_time'].strftime('%Y-%m-%d')
                self.series_tracker.store_meeting_content_signature(
                    series_id, meeting_date, full_content
                )
            except Exception as e:
                logger.warning(f"Failed to store content signature: {e}")
    
    def fetch_and_process_all(self, days_back: Optional[int] = None, 
                             dry_run: bool = False,
                             accepted_only: bool = False,
                             force_refetch: bool = False,
                             gemini_only: bool = False,
                             smart_filtering: bool = False,
                             diff_mode: bool = False) -> Dict[str, Any]:
        """Fetch and process all recent meeting notes.
        
        Args:
            days_back: Number of days back to search.
            dry_run: If True, don't save files, just return results.
            accepted_only: If True, only fetch meetings the user has accepted.
            force_refetch: If True, reprocess meetings even if already processed.
            gemini_only: If True, only fetch Gemini notes and transcripts.
            smart_filtering: If True, apply smart content filtering for new content only.
            diff_mode: If True, only save new content compared to previous meetings.
            
        Returns:
            Dictionary with processing results.
        """
        if not self.authenticate():
            return {'success': False, 'error': 'Authentication failed'}
        
        meetings = self.fetch_recent_meetings(days_back, accepted_only=accepted_only, gemini_only=gemini_only)
        
        results = {
            'success': True,
            'meetings_found': len(meetings),
            'meetings_processed': 0,
            'meetings_skipped': 0,
            'meetings_with_notes': 0,
            'total_documents': 0,
            'errors': [],
            'processed_meetings': []
        }
        
        for meeting in meetings:
            try:
                meeting_id = meeting['id']
                docs_links = meeting.get('docs_links', [])
                
                # Check if already processed (unless force_refetch is True)
                if not force_refetch and not dry_run:
                    if self.file_organizer.is_meeting_already_processed(meeting_id, docs_links):
                        logger.info(f"Skipping already processed meeting: {meeting['title']}")
                        results['meetings_skipped'] += 1
                        results['processed_meetings'].append({
                            'title': meeting['title'],
                            'date': meeting['start_time'].isoformat(),
                            'success': True,
                            'notes_count': 0,
                            'skipped': True,
                            'reason': 'Already processed'
                        })
                        continue
                
                logger.info(f"Processing meeting: {meeting['title']}")
                process_result = self.process_meeting_notes(meeting, save_to_file=not dry_run, smart_filtering=smart_filtering, diff_mode=diff_mode)
                
                results['meetings_processed'] += 1
                
                if process_result['success']:
                    results['meetings_with_notes'] += 1
                    results['total_documents'] += len(process_result['notes'])
                
                results['processed_meetings'].append({
                    'title': meeting['title'],
                    'date': meeting['start_time'].isoformat(),
                    'success': process_result['success'],
                    'notes_count': len(process_result['notes']),
                    'errors': process_result['errors']
                })
                
                if process_result['errors']:
                    results['errors'].extend(process_result['errors'])
                    
            except Exception as e:
                error_msg = f"Error processing meeting '{meeting['title']}': {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        return results