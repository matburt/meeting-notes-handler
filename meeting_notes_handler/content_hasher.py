"""Content hashing for meeting notes comparison."""

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class Paragraph:
    """Represents a paragraph with its hash and metadata."""
    hash: str
    content: str
    preview: str
    word_count: int
    position: int
    
    @property
    def is_empty(self) -> bool:
        """Check if paragraph is effectively empty."""
        return self.word_count == 0 or not self.content.strip()


@dataclass
class Section:
    """Represents a section with header and paragraphs."""
    header: str
    header_hash: str
    paragraphs: List[Paragraph]
    position: int
    
    @property
    def content_hash(self) -> str:
        """Generate hash for entire section content."""
        if not self.paragraphs:
            return self.header_hash
        para_hashes = ''.join(p.hash for p in self.paragraphs)
        return hashlib.sha256(f"{self.header_hash}{para_hashes}".encode()).hexdigest()


@dataclass
class ContentSignature:
    """Complete content signature for a meeting."""
    meeting_id: str
    content_version: str = "1.0"
    extracted_at: str = ""
    full_content_hash: str = ""
    sections: List[Section] = None
    total_words: int = 0
    total_paragraphs: int = 0
    
    def __post_init__(self):
        if self.sections is None:
            self.sections = []


class ContentHasher:
    """Extract and hash meeting content for comparison."""
    
    def __init__(self):
        """Initialize the content hasher."""
        # Common section headers
        self.section_patterns = [
            r'^#+\s+(.+)$',  # Markdown headers
            r'^(.+)\n[=-]+$',  # Underline headers
            r'^(?:(?:\d+\.)|(?:[A-Z]\.))\s*(.+)$',  # Numbered/lettered sections
            r'^(?:\*\*|__)(.+?)(?:\*\*|__)(?:\s*:)?$',  # Bold headers
        ]
        
        # Paragraph separators
        self.paragraph_separators = [
            r'\n\n+',  # Double newlines
            r'\n(?=\s*[-*]\s)',  # Before bullet points
            r'\n(?=\s*\d+\.\s)',  # Before numbered lists
        ]
        
    def create_content_signature(self, meeting_id: str, content: str, 
                               extracted_at: str) -> ContentSignature:
        """
        Create a complete content signature for a meeting.
        
        Args:
            meeting_id: Unique meeting identifier
            content: Full meeting content
            extracted_at: ISO timestamp of extraction
            
        Returns:
            ContentSignature with all hashes and metadata
        """
        if not content:
            return ContentSignature(
                meeting_id=meeting_id,
                extracted_at=extracted_at,
                full_content_hash=self._hash_text("")
            )
        
        # Extract sections
        sections = self.extract_sections(content)
        
        # Calculate totals
        total_words = sum(
            sum(p.word_count for p in section.paragraphs)
            for section in sections
        )
        total_paragraphs = sum(len(section.paragraphs) for section in sections)
        
        # Generate full content hash
        full_content_hash = self._hash_text(content)
        
        return ContentSignature(
            meeting_id=meeting_id,
            extracted_at=extracted_at,
            full_content_hash=full_content_hash,
            sections=sections,
            total_words=total_words,
            total_paragraphs=total_paragraphs
        )
    
    def extract_sections(self, content: str) -> List[Section]:
        """
        Extract sections from meeting content.
        
        Args:
            content: Full meeting content
            
        Returns:
            List of Section objects with headers and paragraphs
        """
        if not content:
            return []
        
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Split content into potential sections
        sections = []
        current_section_content = []
        current_header = "Introduction"  # Default header for content before first header
        position = 0
        
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check if this line is a section header
            header = self._extract_header(line, lines[i+1] if i+1 < len(lines) else "")
            
            if header:
                # Process previous section
                if current_section_content:
                    section_text = '\n'.join(current_section_content)
                    section = self._create_section(
                        current_header, section_text, position
                    )
                    if section.paragraphs:  # Only add non-empty sections
                        sections.append(section)
                        position += 1
                
                # Start new section
                current_header = header
                current_section_content = []
                
                # Skip underline if present
                if i+1 < len(lines) and re.match(r'^[=-]+$', lines[i+1]):
                    i += 1
            else:
                current_section_content.append(line)
            
            i += 1
        
        # Process final section
        if current_section_content:
            section_text = '\n'.join(current_section_content)
            section = self._create_section(current_header, section_text, position)
            if section.paragraphs:
                sections.append(section)
        
        return sections
    
    def extract_paragraphs(self, text: str) -> List[Paragraph]:
        """
        Extract paragraphs from section text.
        
        Args:
            text: Section content
            
        Returns:
            List of Paragraph objects
        """
        if not text.strip():
            return []
        
        # Split by paragraph separators
        raw_paragraphs = re.split(r'\n\n+', text)
        
        paragraphs = []
        position = 0
        
        for raw_para in raw_paragraphs:
            # Clean and normalize
            para_text = self._normalize_paragraph(raw_para)
            
            if para_text:
                paragraph = self._create_paragraph(para_text, position)
                if not paragraph.is_empty:
                    paragraphs.append(paragraph)
                    position += 1
        
        return paragraphs
    
    def _extract_header(self, line: str, next_line: str) -> Optional[str]:
        """Extract header from line if it matches header patterns."""
        line = line.strip()
        if not line:
            return None
        
        # Check markdown headers
        match = re.match(r'^#+\s+(.+)$', line)
        if match:
            return match.group(1).strip()
        
        # Check underline headers
        if next_line and re.match(r'^[=-]+$', next_line.strip()):
            return line
        
        # Check bold headers
        match = re.match(r'^(?:\*\*|__)(.+?)(?:\*\*|__)(?:\s*:)?$', line)
        if match:
            return match.group(1).strip()
        
        # Check if line is all caps (likely a header)
        if line.isupper() and len(line.split()) <= 5:
            return line
        
        return None
    
    def _create_section(self, header: str, content: str, position: int) -> Section:
        """Create a Section object from header and content."""
        header = header.strip()
        header_hash = self._hash_text(header)
        
        # Extract paragraphs from section content
        paragraphs = self.extract_paragraphs(content)
        
        return Section(
            header=header,
            header_hash=header_hash,
            paragraphs=paragraphs,
            position=position
        )
    
    def _create_paragraph(self, text: str, position: int) -> Paragraph:
        """Create a Paragraph object from text."""
        # Generate hash
        hash_value = self._hash_text(text)
        
        # Create preview (first 50 chars)
        preview = text[:50] + "..." if len(text) > 50 else text
        
        # Count words
        word_count = len(text.split())
        
        return Paragraph(
            hash=hash_value,
            content=text,
            preview=preview,
            word_count=word_count,
            position=position
        )
    
    def _normalize_paragraph(self, text: str) -> str:
        """Normalize paragraph text for consistent hashing."""
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove zero-width characters
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        
        return text
    
    def _hash_text(self, text: str) -> str:
        """Generate SHA-256 hash for text."""
        # Normalize text before hashing
        normalized = text.strip().lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using word overlap.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0 if text1 != text2 else 1.0
        
        # Simple word-based similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0