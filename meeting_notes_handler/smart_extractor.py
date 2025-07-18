"""Smart content extractor for filtering only new content from meeting notes."""

import re
import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

from .document_classifier import DocumentClassifier, DocumentType, DocumentInfo
from .series_tracker import MeetingSeriesTracker

logger = logging.getLogger(__name__)


@dataclass
class ContentSection:
    """A section of content within a document."""
    title: str
    content: str
    level: int  # Header level (1-6)
    start_line: int
    end_line: int


@dataclass
class ContentDiff:
    """Difference between two content sections."""
    change_type: str  # 'new', 'modified', 'deleted'
    old_content: Optional[str]
    new_content: Optional[str]
    similarity_score: float
    
    
@dataclass
class FilteredDocument:
    """A document with only new/changed content."""
    title: str
    original_url: str
    filtered_content: str
    change_summary: Dict
    doc_type: DocumentType
    

@dataclass
class FilteringResult:
    """Result of content filtering for a meeting."""
    has_new_content: bool
    filtered_documents: List[FilteredDocument]
    content_reduction_percentage: float
    original_word_count: int
    filtered_word_count: int
    series_id: Optional[str]
    previous_meeting_path: Optional[str]


class SmartContentExtractor:
    """Extracts only genuinely new content from meeting notes."""
    
    def __init__(self, notes_directory: str):
        """Initialize the smart content extractor."""
        self.notes_dir = Path(notes_directory)
        self.classifier = DocumentClassifier()
        self.series_tracker = MeetingSeriesTracker(notes_directory)
        
        # Content similarity thresholds
        self.section_similarity_threshold = 0.8  # 80% similar = same section
        self.content_change_threshold = 0.3      # 30% change = worth including
        self.min_new_content_words = 10          # Minimum words to consider new content
        
    def extract_new_content_only(self, meeting_metadata: Dict, 
                                documents: List[Dict]) -> FilteringResult:
        """
        Extract only new content from a meeting by comparing with previous meeting in series.
        
        Args:
            meeting_metadata: Meeting metadata dict
            documents: List of document dicts with content
            
        Returns:
            FilteringResult with filtered content
        """
        # Identify or create meeting series
        series_id = self.series_tracker.identify_series(meeting_metadata)
        
        if series_id is None:
            # This is a new series - everything is new
            series_id = self.series_tracker.create_new_series(meeting_metadata)
            return self._process_first_meeting(meeting_metadata, documents, series_id)
        
        # Get previous meeting for comparison
        previous_meeting_path = self.series_tracker.get_latest_meeting(series_id)
        
        if not previous_meeting_path:
            # No previous meeting found - treat as first meeting
            return self._process_first_meeting(meeting_metadata, documents, series_id)
        
        # Compare with previous meeting and extract new content
        return self._extract_new_content_vs_previous(
            meeting_metadata, documents, series_id, previous_meeting_path
        )
    
    def _process_first_meeting(self, meeting_metadata: Dict, documents: List[Dict], 
                              series_id: str) -> FilteringResult:
        """Process the first meeting in a series (all content is new)."""
        
        classified_docs = self.classifier.classify_documents(documents)
        filtered_documents = []
        
        total_words = 0
        
        for doc_info in classified_docs:
            word_count = len(doc_info.content.split())
            total_words += word_count
            
            filtered_doc = FilteredDocument(
                title=doc_info.title,
                original_url=doc_info.url,
                filtered_content=doc_info.content,
                change_summary={
                    'change_type': 'first_meeting',
                    'total_words': word_count,
                    'new_sections': self._count_sections(doc_info.content)
                },
                doc_type=doc_info.doc_type
            )
            
            filtered_documents.append(filtered_doc)
        
        return FilteringResult(
            has_new_content=True,
            filtered_documents=filtered_documents,
            content_reduction_percentage=0.0,  # No reduction for first meeting
            original_word_count=total_words,
            filtered_word_count=total_words,
            series_id=series_id,
            previous_meeting_path=None
        )
    
    def _extract_new_content_vs_previous(self, meeting_metadata: Dict, documents: List[Dict],
                                       series_id: str, previous_meeting_path: str) -> FilteringResult:
        """Extract new content by comparing with previous meeting."""
        
        # Load and parse previous meeting
        previous_meeting = self._load_meeting_file(previous_meeting_path)
        previous_docs = self._extract_documents_from_meeting(previous_meeting)
        
        # Classify current documents
        classified_docs = self.classifier.classify_documents(documents)
        
        filtered_documents = []
        original_word_count = 0
        filtered_word_count = 0
        
        for doc_info in classified_docs:
            original_word_count += len(doc_info.content.split())
            
            if doc_info.doc_type == DocumentType.EPHEMERAL:
                # Always include ephemeral content (Gemini notes, transcripts)
                filtered_doc = self._create_ephemeral_filtered_doc(doc_info)
                filtered_documents.append(filtered_doc)
                filtered_word_count += len(filtered_doc.filtered_content.split())
                
            elif doc_info.doc_type == DocumentType.PERSISTENT:
                # Compare with previous version and extract only new parts
                filtered_doc = self._extract_persistent_doc_changes(doc_info, previous_docs)
                
                if filtered_doc and filtered_doc.filtered_content.strip():
                    filtered_documents.append(filtered_doc)
                    filtered_word_count += len(filtered_doc.filtered_content.split())
            
            # Unknown docs: err on side of inclusion
            elif doc_info.doc_type == DocumentType.UNKNOWN:
                filtered_doc = self._create_unknown_filtered_doc(doc_info)
                filtered_documents.append(filtered_doc)
                filtered_word_count += len(filtered_doc.filtered_content.split())
        
        # Calculate content reduction
        reduction_percentage = 0.0
        if original_word_count > 0:
            reduction_percentage = ((original_word_count - filtered_word_count) / original_word_count) * 100
        
        has_new_content = filtered_word_count > 0
        
        return FilteringResult(
            has_new_content=has_new_content,
            filtered_documents=filtered_documents,
            content_reduction_percentage=reduction_percentage,
            original_word_count=original_word_count,
            filtered_word_count=filtered_word_count,
            series_id=series_id,
            previous_meeting_path=previous_meeting_path
        )
    
    def _create_ephemeral_filtered_doc(self, doc_info: DocumentInfo) -> FilteredDocument:
        """Create filtered document for ephemeral content (always included)."""
        word_count = len(doc_info.content.split())
        
        return FilteredDocument(
            title=doc_info.title,
            original_url=doc_info.url,
            filtered_content=doc_info.content,
            change_summary={
                'change_type': 'ephemeral',
                'total_words': word_count,
                'reason': 'Always new per meeting'
            },
            doc_type=doc_info.doc_type
        )
    
    def _create_unknown_filtered_doc(self, doc_info: DocumentInfo) -> FilteredDocument:
        """Create filtered document for unknown type content (include to be safe)."""
        word_count = len(doc_info.content.split())
        
        return FilteredDocument(
            title=f"{doc_info.title} (Unknown Type)",
            original_url=doc_info.url,
            filtered_content=doc_info.content,
            change_summary={
                'change_type': 'unknown',
                'total_words': word_count,
                'reason': 'Included due to uncertain classification'
            },
            doc_type=doc_info.doc_type
        )
    
    def _extract_persistent_doc_changes(self, current_doc: DocumentInfo, 
                                      previous_docs: List[Dict]) -> Optional[FilteredDocument]:
        """Extract changes from a persistent document by comparing with previous version."""
        
        # Find matching document from previous meeting
        previous_doc = self._find_matching_previous_doc(current_doc, previous_docs)
        
        if not previous_doc:
            # Document didn't exist before - entirely new
            word_count = len(current_doc.content.split())
            return FilteredDocument(
                title=f"{current_doc.title} (New Document)",
                original_url=current_doc.url,
                filtered_content=current_doc.content,
                change_summary={
                    'change_type': 'new_document',
                    'total_words': word_count,
                    'reason': 'Document not found in previous meeting'
                },
                doc_type=current_doc.doc_type
            )
        
        # Compare content and extract new sections
        new_sections = self._find_new_content_sections(
            current_doc.content, 
            previous_doc['content']
        )
        
        if not new_sections:
            # No meaningful changes found
            return None
        
        # Build filtered content from new sections
        filtered_content = self._build_filtered_content(new_sections)
        
        if len(filtered_content.split()) < self.min_new_content_words:
            # Too little new content to be meaningful
            return None
        
        return FilteredDocument(
            title=f"{current_doc.title} - New Content",
            original_url=current_doc.url,
            filtered_content=filtered_content,
            change_summary={
                'change_type': 'updated_document',
                'new_sections': len(new_sections),
                'total_words': len(filtered_content.split()),
                'previous_version_words': len(previous_doc['content'].split())
            },
            doc_type=current_doc.doc_type
        )
    
    def _find_matching_previous_doc(self, current_doc: DocumentInfo, 
                                  previous_docs: List[Dict]) -> Optional[Dict]:
        """Find the matching document from the previous meeting."""
        
        # Try URL match first
        for prev_doc in previous_docs:
            if prev_doc['url'] == current_doc.url:
                return prev_doc
        
        # Try title similarity match
        best_match = None
        best_similarity = 0.0
        
        for prev_doc in previous_docs:
            similarity = self._calculate_title_similarity(
                current_doc.title, prev_doc['title']
            )
            
            if similarity > best_similarity and similarity > 0.7:
                best_similarity = similarity
                best_match = prev_doc
        
        return best_match
    
    def _find_new_content_sections(self, current_content: str, 
                                 previous_content: str) -> List[ContentSection]:
        """Find sections that are new or significantly changed."""
        
        current_sections = self._parse_content_sections(current_content)
        previous_sections = self._parse_content_sections(previous_content)
        
        new_sections = []
        
        for current_section in current_sections:
            # Find matching section in previous content
            matching_previous = self._find_matching_section(current_section, previous_sections)
            
            if not matching_previous:
                # Entirely new section
                new_sections.append(current_section)
            else:
                # Check if content changed significantly
                similarity = self._calculate_content_similarity(
                    current_section.content, matching_previous.content
                )
                
                if similarity < (1.0 - self.content_change_threshold):
                    # Content changed significantly - include the new version
                    new_sections.append(current_section)
        
        return new_sections
    
    def _parse_content_sections(self, content: str) -> List[ContentSection]:
        """Parse content into sections based on markdown headers."""
        
        lines = content.split('\n')
        sections = []
        current_section = None
        
        for i, line in enumerate(lines):
            # Check if line is a header
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            
            if header_match:
                # Save previous section if it exists
                if current_section:
                    current_section.end_line = i - 1
                    sections.append(current_section)
                
                # Start new section
                level = len(header_match.group(1))
                title = header_match.group(2)
                
                current_section = ContentSection(
                    title=title,
                    content="",
                    level=level,
                    start_line=i,
                    end_line=i
                )
            
            elif current_section:
                # Add line to current section
                if current_section.content:
                    current_section.content += '\n' + line
                else:
                    current_section.content = line
        
        # Add the last section
        if current_section:
            current_section.end_line = len(lines) - 1
            sections.append(current_section)
        
        # If no sections found, treat entire content as one section
        if not sections and content.strip():
            sections.append(ContentSection(
                title="Content",
                content=content,
                level=1,
                start_line=0,
                end_line=len(lines) - 1
            ))
        
        return sections
    
    def _find_matching_section(self, section: ContentSection, 
                             previous_sections: List[ContentSection]) -> Optional[ContentSection]:
        """Find matching section in previous content."""
        
        best_match = None
        best_similarity = 0.0
        
        for prev_section in previous_sections:
            # Title similarity
            title_similarity = self._calculate_title_similarity(section.title, prev_section.title)
            
            if title_similarity > best_similarity and title_similarity > self.section_similarity_threshold:
                best_similarity = title_similarity
                best_match = prev_section
        
        return best_match
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles."""
        if not title1 or not title2:
            return 0.0 if title1 != title2 else 1.0
        
        # Use sequence matcher for similarity
        return difflib.SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
    
    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two content strings."""
        if not content1 or not content2:
            return 0.0 if content1 != content2 else 1.0
        
        # Use sequence matcher for similarity
        return difflib.SequenceMatcher(None, content1, content2).ratio()
    
    def _build_filtered_content(self, sections: List[ContentSection]) -> str:
        """Build filtered content from new/changed sections."""
        
        content_parts = []
        
        for section in sections:
            # Add section header
            header = '#' * section.level + ' ' + section.title
            content_parts.append(header)
            
            # Add section content
            if section.content.strip():
                content_parts.append(section.content.strip())
            
            content_parts.append("")  # Empty line between sections
        
        return '\n'.join(content_parts).strip()
    
    def _count_sections(self, content: str) -> int:
        """Count the number of sections in content."""
        sections = self._parse_content_sections(content)
        return len(sections)
    
    def _load_meeting_file(self, file_path: str) -> Dict:
        """Load and parse a meeting file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split YAML frontmatter and content
            parts = content.split('---', 2)
            
            if len(parts) >= 3:
                yaml_content = parts[1]
                markdown_content = parts[2]
            else:
                yaml_content = ""
                markdown_content = content
            
            return {
                'yaml_metadata': yaml_content,
                'content': markdown_content,
                'full_content': content
            }
            
        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Error loading meeting file {file_path}: {e}")
            return {}
    
    def _extract_documents_from_meeting(self, meeting_data: Dict) -> List[Dict]:
        """Extract individual documents from a meeting file."""
        
        content = meeting_data.get('content', '')
        if not content:
            return []
        
        documents = []
        
        # Split by document headers
        doc_pattern = r'^## Document \d+\s*$'
        parts = re.split(doc_pattern, content, flags=re.MULTILINE)
        
        if len(parts) <= 1:
            # No document sections found - treat entire content as one document
            documents.append({
                'title': 'Meeting Content',
                'url': '',
                'content': content
            })
        else:
            # Process each document section
            for i, part in enumerate(parts[1:], 1):  # Skip first empty part
                lines = part.strip().split('\n')
                
                # Extract title from first line if it follows pattern
                title = f"Document {i}"
                content_start = 0
                
                if lines and lines[0].startswith('**Title:**'):
                    title = lines[0].replace('**Title:**', '').strip()
                    content_start = 1
                
                # Extract URL if present
                url = ""
                if len(lines) > content_start and 'http' in lines[content_start]:
                    url_match = re.search(r'https?://[^\s\)]+', lines[content_start])
                    if url_match:
                        url = url_match.group(0)
                
                # Get document content
                doc_content = '\n'.join(lines[content_start:]).strip()
                
                documents.append({
                    'title': title,
                    'url': url,
                    'content': doc_content
                })
        
        return documents