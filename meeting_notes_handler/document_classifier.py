"""Document classifier for identifying content types in meeting notes."""

import re
from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Types of documents found in meetings."""
    EPHEMERAL = "ephemeral"      # Always unique per meeting (Gemini notes, transcripts)
    PERSISTENT = "persistent"    # Shared docs that accumulate changes
    UNKNOWN = "unknown"         # Needs further analysis


@dataclass
class DocumentInfo:
    """Information about a processed document."""
    title: str
    url: str
    content: str
    doc_type: DocumentType
    confidence: float
    metadata: Dict
    index: int


class DocumentClassifier:
    """Classifies meeting documents by their persistence and content type."""
    
    def __init__(self):
        """Initialize the document classifier with pattern recognition."""
        
        # Patterns for ephemeral (meeting-specific) documents
        self.ephemeral_patterns = [
            # Gemini-generated content
            r'notes\s+by\s+gemini',
            r'gemini\s+notes',
            r'meeting\s+notes.*gemini',
            r'auto.*generated.*notes',
            
            # Transcripts and recordings
            r'transcript',
            r'meeting\s+transcript',
            r'chat\s+log',
            r'meeting\s+chat',
            r'recording',
            r'meeting\s+recording',
            
            # Date/time specific documents
            r'\d{4}[-/]\d{2}[-/]\d{2}.*(?:notes|transcript|summary)',
            r'(?:meeting|notes).*\d{2}:\d{2}',
            
            # Temporary/session specific
            r'session\s+notes',
            r'meeting\s+summary.*\d+',
        ]
        
        # Patterns for persistent (shared/evolving) documents
        self.persistent_patterns = [
            # Project documentation
            r'project.*(?:plan|doc|spec)',
            r'requirements.*doc',
            r'specification',
            r'design.*doc',
            
            # Planning and tracking
            r'planning.*board',
            r'sprint.*(?:board|backlog)',
            r'backlog',
            r'roadmap',
            r'timeline',
            
            # Collaborative documents
            r'shared.*doc',
            r'team.*doc',
            r'project.*status',
            r'action.*items',
            r'decisions.*log',
        ]
        
        # Content indicators for ephemeral vs persistent
        self.ephemeral_content_indicators = [
            'transcript of meeting',
            'meeting started at',
            'meeting ended at',
            'participants joined',
            'gemini took notes',
            'auto-generated summary',
        ]
        
        self.persistent_content_indicators = [
            'last updated',
            'version history',
            'edit history',
            'contributors:',
            'document owner',
            'shared with',
        ]
    
    def classify_document(self, title: str, url: str = "", content: str = "", 
                         metadata: Optional[Dict] = None) -> Tuple[DocumentType, float]:
        """
        Classify a document as ephemeral or persistent.
        
        Args:
            title: Document title
            url: Document URL (optional)
            content: Document content (optional) 
            metadata: Additional metadata (optional)
            
        Returns:
            Tuple of (DocumentType, confidence_score)
        """
        if metadata is None:
            metadata = {}
            
        title_lower = title.lower()
        content_lower = content.lower() if content else ""
        
        # Check title patterns first (highest confidence)
        ephemeral_score = self._score_patterns(title_lower, self.ephemeral_patterns)
        persistent_score = self._score_patterns(title_lower, self.persistent_patterns)
        
        # Add content-based scoring if available
        if content:
            ephemeral_score += self._score_content_indicators(content_lower, self.ephemeral_content_indicators) * 0.5
            persistent_score += self._score_content_indicators(content_lower, self.persistent_content_indicators) * 0.5
        
        # Add URL-based hints
        if url:
            url_score = self._score_url_patterns(url.lower())
            if url_score != 0:
                if url_score > 0:
                    ephemeral_score += abs(url_score) * 0.3
                else:
                    persistent_score += abs(url_score) * 0.3
        
        # Add metadata-based scoring
        metadata_score = self._score_metadata(metadata)
        if metadata_score != 0:
            if metadata_score > 0:
                ephemeral_score += abs(metadata_score) * 0.2
            else:
                persistent_score += abs(metadata_score) * 0.2
        
        # Determine classification
        total_score = ephemeral_score + persistent_score
        
        if total_score == 0:
            return DocumentType.UNKNOWN, 0.0
        
        if ephemeral_score > persistent_score:
            confidence = ephemeral_score / total_score
            return DocumentType.EPHEMERAL, min(confidence, 1.0)
        else:
            confidence = persistent_score / total_score
            return DocumentType.PERSISTENT, min(confidence, 1.0)
    
    def classify_documents(self, documents: List[Dict]) -> List[DocumentInfo]:
        """
        Classify a list of documents from a meeting.
        
        Args:
            documents: List of document dictionaries with title, url, content, metadata
            
        Returns:
            List of DocumentInfo objects with classifications
        """
        classified_docs = []
        
        for i, doc in enumerate(documents):
            title = doc.get('title', f'Document {i+1}')
            url = doc.get('url', doc.get('doc_url', ''))
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            
            doc_type, confidence = self.classify_document(title, url, content, metadata)
            
            doc_info = DocumentInfo(
                title=title,
                url=url,
                content=content,
                doc_type=doc_type,
                confidence=confidence,
                metadata=metadata,
                index=i
            )
            
            classified_docs.append(doc_info)
            
            logger.debug(f"Classified '{title}' as {doc_type.value} (confidence: {confidence:.2f})")
        
        return classified_docs
    
    def _score_patterns(self, text: str, patterns: List[str]) -> float:
        """Score text against a list of regex patterns."""
        score = 0.0
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Weight by pattern specificity and number of matches
                pattern_score = len(pattern) / 100 * len(matches)
                score += pattern_score
        return score
    
    def _score_content_indicators(self, content: str, indicators: List[str]) -> float:
        """Score content based on presence of type indicators."""
        score = 0.0
        for indicator in indicators:
            if indicator.lower() in content:
                score += 1.0
        return score / len(indicators) if indicators else 0.0
    
    def _score_url_patterns(self, url: str) -> float:
        """
        Score URL patterns for document type hints.
        
        Returns:
            Positive score for ephemeral indicators, negative for persistent
        """
        if not url:
            return 0.0
        
        # Ephemeral URL patterns (positive score)
        if 'meet_tnfm_calendar' in url:  # Gemini notes pattern
            return 2.0
        if 'transcript' in url or 'recording' in url:
            return 1.5
        
        # Persistent URL patterns (negative score) 
        if 'edit' in url and 'sharing' not in url:  # Editable shared docs
            return -1.0
        if 'view' in url and 'usp=sharing' in url:  # Shared view docs
            return -0.5
        
        return 0.0
    
    def _score_metadata(self, metadata: Dict) -> float:
        """
        Score document metadata for type hints.
        
        Returns:
            Positive score for ephemeral indicators, negative for persistent
        """
        score = 0.0
        
        # Check file timestamps and creation patterns
        if 'created' in metadata:
            # Documents created very recently during meeting time might be ephemeral
            pass  # Would need meeting timestamp to compare
        
        # Check document permissions/sharing
        if metadata.get('shared', False):
            score -= 0.5  # Shared docs more likely to be persistent
        
        # Check document size (transcripts tend to be longer)
        content_length = len(metadata.get('content', ''))
        if content_length > 5000:  # Arbitrary threshold
            score += 0.3  # Long docs might be transcripts
        
        return score
    
    def get_classification_summary(self, documents: List[DocumentInfo]) -> Dict:
        """Generate a summary of document classifications."""
        summary = {
            'total_documents': len(documents),
            'ephemeral_count': 0,
            'persistent_count': 0,
            'unknown_count': 0,
            'average_confidence': 0.0,
            'classifications': []
        }
        
        total_confidence = 0.0
        
        for doc in documents:
            if doc.doc_type == DocumentType.EPHEMERAL:
                summary['ephemeral_count'] += 1
            elif doc.doc_type == DocumentType.PERSISTENT:
                summary['persistent_count'] += 1
            else:
                summary['unknown_count'] += 1
            
            total_confidence += doc.confidence
            
            summary['classifications'].append({
                'title': doc.title,
                'type': doc.doc_type.value,
                'confidence': doc.confidence
            })
        
        if documents:
            summary['average_confidence'] = total_confidence / len(documents)
        
        return summary